from datetime import datetime

from sqlalchemy import String, Text, DateTime, Boolean, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class DestinationVPN(Base):
    __tablename__ = "destination_vpns"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    protocol: Mapped[str] = mapped_column(String(20), nullable=False)  # wireguard, openvpn
    interface_name: Mapped[str] = mapped_column(String(20), nullable=False)  # e.g. wg1, tun0
    config_text: Mapped[str | None] = mapped_column(Text)
    config_file_path: Mapped[str | None] = mapped_column(String(500))
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    is_running: Mapped[bool] = mapped_column(Boolean, default=False)
    # Start mode: manual (default), on_demand (start when user connects, stop after idle),
    # auto_restart (restart automatically if stopped unexpectedly)
    start_mode: Mapped[str] = mapped_column(String(20), default="manual")  # manual, on_demand, auto_restart
    manually_stopped: Mapped[bool] = mapped_column(Boolean, default=False)  # track manual vs unexpected stop
    routing_table: Mapped[int] = mapped_column(Integer, default=100)  # ip rule table number
    fwmark: Mapped[int] = mapped_column(Integer, default=100)  # iptables mark

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    users: Mapped[list["User"]] = relationship("User", back_populates="destination_vpn")
