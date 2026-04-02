from datetime import datetime, timezone

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from app.database import SessionLocal
from app.models.user import User

router = Router()


def _format_bytes(b: int) -> str:
    if b == 0:
        return "0 B"
    units = ["B", "KB", "MB", "GB", "TB"]
    k = 1024
    i = 0
    while b >= k and i < len(units) - 1:
        b /= k
        i += 1
    return f"{b:.2f} {units[i]}"


def _progress_bar(used: int, limit: int | None, width: int = 20) -> str:
    if not limit:
        return "Unlimited"
    pct = min(100, int((used / limit) * 100))
    filled = int(width * pct / 100)
    bar = "█" * filled + "░" * (width - filled)
    return f"{bar} {pct}%"


@router.message(Command("usage"))
async def cmd_usage(message: Message):
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.telegram_chat_id == message.chat.id).first()
        if not user:
            await message.answer(
                "Your account is not linked.\n"
                "Use /start YOUR_CODE to link your account."
            )
            return

        # Build usage message
        text = f"📊 <b>Usage Report - {user.username}</b>\n\n"

        # Download
        text += f"⬇️ Download: {_format_bytes(user.bandwidth_used_down)}"
        if user.bandwidth_limit_down:
            text += f" / {_format_bytes(user.bandwidth_limit_down)}\n"
            text += f"   {_progress_bar(user.bandwidth_used_down, user.bandwidth_limit_down)}\n"
        else:
            text += " (Unlimited)\n"

        # Upload
        text += f"\n⬆️ Upload: {_format_bytes(user.bandwidth_used_up)}"
        if user.bandwidth_limit_up:
            text += f" / {_format_bytes(user.bandwidth_limit_up)}\n"
            text += f"   {_progress_bar(user.bandwidth_used_up, user.bandwidth_limit_up)}\n"
        else:
            text += " (Unlimited)\n"

        # Expiry
        if user.expiry_date:
            now = datetime.now(timezone.utc)
            if user.expiry_date > now:
                days_left = (user.expiry_date - now).days
                text += f"\n📅 Expires in: <b>{days_left} days</b>"
            else:
                text += "\n📅 Status: <b>Expired</b>"
        else:
            text += "\n📅 Expiry: No expiry set"

        # Status
        text += f"\n🔌 Account: {'✅ Active' if user.enabled else '❌ Disabled'}"

        await message.answer(text, parse_mode="HTML")
    finally:
        db.close()


@router.message(Command("status"))
async def cmd_status(message: Message):
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.telegram_chat_id == message.chat.id).first()
        if not user:
            await message.answer(
                "Your account is not linked.\n"
                "Use /start YOUR_CODE to link your account."
            )
            return

        from app.services.wireguard import get_peers_status

        peers = get_peers_status()
        is_online = False
        endpoint = None
        last_handshake = None

        for peer in peers:
            if peer["public_key"] == user.wg_public_key:
                if peer["latest_handshake"]:
                    now = datetime.now(timezone.utc).timestamp()
                    if now - peer["latest_handshake"] < 180:
                        is_online = True
                    last_handshake = datetime.fromtimestamp(
                        peer["latest_handshake"], tz=timezone.utc
                    ).strftime("%Y-%m-%d %H:%M:%S UTC")
                endpoint = peer["endpoint"]
                break

        text = f"🔌 <b>Connection Status - {user.username}</b>\n\n"
        text += f"Status: {'🟢 Online' if is_online else '🔴 Offline'}\n"
        text += f"Account: {'✅ Active' if user.enabled else '❌ Disabled'}\n"

        if endpoint:
            text += f"Endpoint: <code>{endpoint}</code>\n"
        if last_handshake:
            text += f"Last Handshake: {last_handshake}\n"

        text += f"IP: <code>{user.assigned_ip}</code>"

        await message.answer(text, parse_mode="HTML")
    finally:
        db.close()
