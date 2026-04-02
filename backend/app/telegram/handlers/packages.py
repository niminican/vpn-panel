from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from app.database import SessionLocal
from app.models.package import Package

router = Router()


def _format_bytes(b: int) -> str:
    if b == 0:
        return "0 B"
    units = ["B", "KB", "MB", "GB", "TB"]
    k = 1024
    i = 0
    val = float(b)
    while val >= k and i < len(units) - 1:
        val /= k
        i += 1
    return f"{val:.0f} {units[i]}"


@router.message(Command("packages"))
async def cmd_packages(message: Message):
    db = SessionLocal()
    try:
        pkgs = db.query(Package).filter(Package.enabled == True).all()  # noqa: E712

        if not pkgs:
            await message.answer("No packages available at the moment.")
            return

        text = "📦 <b>Available Packages</b>\n\n"

        for pkg in pkgs:
            text += f"━━━━━━━━━━━━━━━━━━\n"
            text += f"📋 <b>{pkg.name}</b>\n"
            if pkg.description:
                text += f"   {pkg.description}\n"

            if pkg.bandwidth_limit:
                text += f"   📊 Traffic: {_format_bytes(pkg.bandwidth_limit)}\n"
            else:
                text += f"   📊 Traffic: Unlimited\n"

            if pkg.speed_limit:
                text += f"   🚀 Speed: {pkg.speed_limit} Kbps\n"

            text += f"   📅 Duration: {pkg.duration_days} days\n"
            text += f"   👥 Connections: {pkg.max_connections}\n"

            if pkg.price:
                text += f"   💰 Price: {pkg.price:,.0f} {pkg.currency}\n"

        text += f"\n━━━━━━━━━━━━━━━━━━\n"
        text += "To purchase, contact your admin."

        await message.answer(text, parse_mode="HTML")
    finally:
        db.close()
