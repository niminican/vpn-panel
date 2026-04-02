"""
Telegram Bot

aiogram 3.x bot with webhook mode, integrated into FastAPI.
Commands:
  /start - Register and link account
  /usage - Check bandwidth usage
  /status - Check VPN connection status
  /packages - View available packages
  /help - List commands
"""
import logging

from aiogram import Bot, Dispatcher, Router
from aiogram.types import Update
from fastapi import APIRouter, Request

from app.config import settings
from app.telegram.handlers import start, usage, packages

logger = logging.getLogger(__name__)

bot: Bot | None = None
dp: Dispatcher | None = None
webhook_router = APIRouter()


def create_bot() -> tuple[Bot, Dispatcher] | None:
    """Create and configure the Telegram bot."""
    global bot, dp

    if not settings.telegram_bot_token:
        logger.info("Telegram bot token not configured, skipping bot setup")
        return None

    bot = Bot(token=settings.telegram_bot_token)
    dp = Dispatcher()

    # Register handlers
    main_router = Router()
    main_router.include_router(start.router)
    main_router.include_router(usage.router)
    main_router.include_router(packages.router)
    dp.include_router(main_router)

    logger.info("Telegram bot created")
    return bot, dp


@webhook_router.post("/api/telegram/webhook")
async def telegram_webhook(request: Request):
    """Handle incoming Telegram webhook updates."""
    if not bot or not dp:
        return {"ok": False, "error": "Bot not configured"}

    data = await request.json()
    update = Update.model_validate(data, context={"bot": bot})
    await dp.feed_update(bot=bot, update=update)
    return {"ok": True}


async def setup_webhook():
    """Set up Telegram webhook URL."""
    if not bot or not settings.telegram_webhook_url:
        return

    webhook_url = f"{settings.telegram_webhook_url}/api/telegram/webhook"
    await bot.set_webhook(webhook_url)
    logger.info(f"Telegram webhook set to {webhook_url}")


async def shutdown_bot():
    """Clean up bot on shutdown."""
    if bot:
        await bot.delete_webhook()
        await bot.session.close()
