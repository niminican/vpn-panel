from sqlalchemy import String, Integer, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class UserWhitelist(Base):
    __tablename__ = "user_whitelist"
    __table_args__ = (
        UniqueConstraint("user_id", "address", "port", "protocol", name="uq_whitelist_entry"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    address: Mapped[str] = mapped_column(String(255), nullable=False)  # IP, CIDR, or domain
    port: Mapped[int | None] = mapped_column(Integer)
    protocol: Mapped[str] = mapped_column(String(10), default="any")  # tcp, udp, any
    description: Mapped[str | None] = mapped_column(String(255))

    user: Mapped["User"] = relationship("User", back_populates="whitelist_entries")
