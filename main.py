"""
Vercel Serverless Entry Point
==============================
FastAPI ASGI app that handles Telegram webhook updates.
"""

import os
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse
from aiogram import Bot
from aiogram.types import Update

from bot_app import dp, create_bot, register_handlers

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "")

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting up bot...")
    register_handlers()
    yield
    logger.info("Shutting down bot...")

app = FastAPI(lifespan=lifespan)

@app.get("/")
async def root():
    return {
        "status": "ok",
        "service": "KuCoin Futures Risk Bot",
        "mode": "webhook"
    }

@app.get("/health")
async def health():
    return {"status": "healthy"}

@app.post("/webhook")
async def telegram_webhook(request: Request):
    """
    Receive updates from Telegram.
    Telegram sends a POST request here every time a user interacts with the bot.
    """
    try:
        data = await request.json()
        update = Update.model_validate(data)
        bot = create_bot()
        await dp.feed_update(bot, update)
        return Response(status_code=200)
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        return JSONResponse(
            status_code=200,
            content={"ok": False, "error": str(e)}
        )

@app.post("/setup-webhook")
async def setup_webhook(request: Request):
    """
    Call this endpoint once after deployment to register the webhook with Telegram.
    """
    try:
        bot = create_bot()
        host = request.headers.get("host", "")
        scheme = request.headers.get("x-forwarded-proto", "https")
        webhook_url = f"{scheme}://{host}/webhook"
        
        await bot.set_webhook(
            url=webhook_url,
            secret_token=WEBHOOK_SECRET if WEBHOOK_SECRET else None,
            drop_pending_updates=True
        )
        
        info = await bot.get_webhook_info()
        return {
            "ok": True,
            "webhook_url": webhook_url,
            "telegram_webhook": info.model_dump() if hasattr(info, "model_dump") else str(info)
        }
    except Exception as e:
        logger.error(f"Setup webhook error: {e}")
        return JSONResponse(status_code=500, content={"ok": False, "error": str(e)})
