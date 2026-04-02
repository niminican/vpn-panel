from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class BandwidthHistory(Base):
    __tablename__ = "bandwidth_history"
    __table_args__ = (
        Index("idx_bw_user_ts", "user_id", "timestamp"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    bytes_up: Mapped[int] = mapped_column(BigInteger, nullable=False)
    bytes_down: Mapped[int] = mapped_column(BigInteger, nullable=False)
