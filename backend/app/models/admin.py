from datetime import datetime

from sqlalchemy import String, DateTime, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Admin(Base):
    __tablename__ = "admins"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    totp_secret: Mapped[str | None] = mapped_column(String(32))
    role: Mapped[str] = mapped_column(String(20), default="super_admin")  # super_admin, admin
    permissions: Mapped[str | None] = mapped_column(Text)  # JSON: list of permission strings
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    @property
    def is_super_admin(self) -> bool:
        return self.role == "super_admin"

    def get_permissions(self) -> list[str]:
        if self.is_super_admin:
            return ALL_PERMISSIONS
        if not self.permissions:
            return []
        import json
        try:
            return json.loads(self.permissions)
        except (json.JSONDecodeError, TypeError):
            return []

    def has_permission(self, perm: str) -> bool:
        if self.is_super_admin:
            return True
        return perm in self.get_permissions()


# All available permissions
ALL_PERMISSIONS = [
    "users.view",
    "users.create",
    "users.edit",
    "users.delete",
    "destinations.view",
    "destinations.manage",
    "logs.view",
    "packages.manage",
    "settings.manage",
    "alerts.view",
]
