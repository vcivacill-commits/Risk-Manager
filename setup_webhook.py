"""
Setup Webhook Script
====================
Run this locally after deploying to Vercel to register the webhook URL with Telegram.

Usage:
    python setup_webhook.py https://your-project.vercel.app
"""

import sys
import os
import asyncio
from aiogram import Bot

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "")

async def main():
    if len(sys.argv) < 2:
        print("Usage: python setup_webhook.py <your-vercel-url>")
        print("Example: python setup_webhook.py https://kucoin-risk-bot.vercel.app")
        sys.exit(1)
    
    base_url = sys.argv[1].rstrip("/")
    webhook_url = f"{base_url}/webhook"
    
    if not TELEGRAM_BOT_TOKEN:
        print("❌ Error: TELEGRAM_BOT_TOKEN not set in environment.")
        print("Set it with: set TELEGRAM_BOT_TOKEN=your_token  (Windows)")
        print("Or:         export TELEGRAM_BOT_TOKEN=your_token  (Mac/Linux)")
        sys.exit(1)
    
    bot = Bot(token=TELEGRAM_BOT_TOKEN)
    print(f"🔗 Setting webhook to: {webhook_url}")
    
    try:
        await bot.set_webhook(
            url=webhook_url,
            secret_token=WEBHOOK_SECRET if WEBHOOK_SECRET else None,
            drop_pending_updates=True
        )
        
        info = await bot.get_webhook_info()
        print(f"✅ Webhook set successfully!")
        print(f"   URL: {info.url}")
        print(f"   Pending updates: {info.pending_update_count}")
        
    except Exception as e:
        print(f"❌ Failed to set webhook: {e}")
    finally:
        await bot.session.close()

if __name__ == "__main__":
    asyncio.run(main())
