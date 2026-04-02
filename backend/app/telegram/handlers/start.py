from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from app.database import SessionLocal
from app.models.user import User

router = Router()


@router.message(Command("start"))
async def cmd_start(message: Message):
    args = message.text.split(maxsplit=1)

    if len(args) > 1:
        # Deep link with connection code: /start <code>
        code = args[1].strip()
        db = SessionLocal()
        try:
            user = db.query(User).filter(User.telegram_link_code == code).first()
            if user:
                user.telegram_chat_id = message.chat.id
                user.telegram_username = message.from_user.username or message.from_user.first_name
                db.commit()
                await message.answer(
                    f"Account linked successfully!\n\n"
                    f"Username: <b>{user.username}</b>\n"
                    f"IP: <code>{user.assigned_ip}</code>\n\n"
                    f"Use /usage to check your bandwidth.\n"
                    f"Use /status to check connection status.\n"
                    f"Use /packages to view available plans.",
                    parse_mode="HTML",
                )
            else:
                await message.answer(
                    "Invalid connection code. Please check with your admin."
                )
        finally:
            db.close()
    else:
        await message.answer(
            "Welcome to VPN Panel Bot!\n\n"
            "To link your account, use the connection code from your admin:\n"
            "/start YOUR_CODE\n\n"
            "Commands:\n"
            "/usage - Check bandwidth usage\n"
            "/status - Connection status\n"
            "/packages - Available plans\n"
            "/help - Show help"
        )


@router.message(Command("help"))
async def cmd_help(message: Message):
    await message.answer(
        "VPN Panel Bot Commands:\n\n"
        "/usage - Check your bandwidth usage\n"
        "/status - Check your connection status\n"
        "/packages - View available plans\n"
        "/help - Show this help message"
    )
