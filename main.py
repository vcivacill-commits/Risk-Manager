"""
Vercel Serverless Entry Point
=============================
FastAPI ASGI app that handles Telegram webhook updates.
Optimized for Vercel serverless deployment.
"""

import os
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "")

logger.info(f"TELEGRAM_BOT_TOKEN set: {bool(TELEGRAM_BOT_TOKEN)}")

from bot_app import dp, create_bot, register_handlers, set_bot_commands
logger.info("bot_app imported successfully")

from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse
from aiogram.types import Update

app = FastAPI()

logger.info("Registering handlers...")
register_handlers()
logger.info("Handlers registered")

@app.get("/")
async def root():
    return {
        "status": "ok",
        "service": "KuCoin Futures Risk Bot",
        "mode": "webhook",
        "token_set": bool(TELEGRAM_BOT_TOKEN)
    }

@app.get("/health")
async def health():
    return {"status": "healthy"}

@app.post("/webhook")
async def telegram_webhook(request: Request):
    try:
        data = await request.json()
        logger.info(f"Received webhook update: {data.get('update_id', 'unknown')}")
        
        update = Update.model_validate(data)
        bot = create_bot()
        
        await dp.feed_update(bot, update)
        return Response(status_code=200)
    
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return JSONResponse(
            status_code=200,
            content={"ok": False, "error": str(e)}
        )

@app.post("/setup-webhook")
async def setup_webhook(request: Request):
    if not TELEGRAM_BOT_TOKEN:
        return JSONResponse(
            status_code=500,
            content={"ok": False, "error": "TELEGRAM_BOT_TOKEN not set"}
        )
    
    try:
        bot = create_bot()
        host = request.headers.get("host", "")
        scheme = request.headers.get("x-forwarded-proto", "https")
        webhook_url = f"{scheme}://{host}/webhook"
        
        logger.info(f"Setting webhook to: {webhook_url}")
        
        await bot.set_webhook(
            url=webhook_url,
            secret_token=WEBHOOK_SECRET if WEBHOOK_SECRET else None,
            drop_pending_updates=True
        )
        await set_bot_commands(bot)
        
        info = await bot.get_webhook_info()
        logger.info(f"Webhook info: {info}")
        
        return {
            "ok": True,
            "webhook_url": webhook_url,
            "telegram_webhook": str(info)
        }
    
    except Exception as e:
        logger.error(f"Setup webhook error: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return JSONResponse(status_code=500, content={"ok": False, "error": str(e)})
