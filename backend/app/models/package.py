from sqlalchemy import String, Text, Integer, BigInteger, Boolean, Numeric, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Package(Base):
    __tablename__ = "packages"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    bandwidth_limit: Mapped[int | None] = mapped_column(BigInteger)  # bytes
    speed_limit: Mapped[int | None] = mapped_column(Integer)  # kbps
    duration_days: Mapped[int] = mapped_column(Integer, nullable=False)
    max_connections: Mapped[int] = mapped_column(Integer, default=1)
    price: Mapped[float | None] = mapped_column(Numeric(10, 2))
    currency: Mapped[str] = mapped_column(String(10), default="IRR")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    destination_vpn_id: Mapped[int | None] = mapped_column(ForeignKey("destination_vpns.id", ondelete="SET NULL"))
    destination_vpn: Mapped["DestinationVPN | None"] = relationship("DestinationVPN")
