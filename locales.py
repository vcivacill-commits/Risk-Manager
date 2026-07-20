"""
Localization
============
All user-facing strings for the Telegram bot, in English (en) and
Persian/Farsi (fa). Add a new language by adding a new top-level key to
LOCALES with the same set of message keys.
"""

from typing import Dict

DEFAULT_LANG = "en"
SUPPORTED_LANGS = ("en", "fa")

LANG_NAMES = {
    "en": "English",
    "fa": "فارسی",
}

DIRECTION_LABELS = {
    "en": {"LONG": "LONG", "SHORT": "SHORT"},
    "fa": {"LONG": "لانگ (خرید)", "SHORT": "شورت (فروش)"},
}

LOCALES: Dict[str, Dict[str, str]] = {
    "en": {
        "welcome": (
            "👋 <b>Welcome to the KuCoin Futures Risk Manager!</b>\n\n"
            "I calculate optimal leverage, stop-loss, and take-profit using "
            "ATR-based support/resistance from KuCoin Futures data.\n\n"
            "<b>Formula:</b> <code>Leverage = Risk% / SL Distance%</code>\n\n"
            "Use /newtrade to start.\n"
            "Use /language to switch between English and فارسی."
        ),
        "step1_symbol": (
            "📊 <b>Step 1/5:</b> Enter the cryptocurrency symbol.\n\n"
            "Examples: <code>BTC</code>, <code>ETH</code>, <code>SOL</code>"
        ),
        "current_price": "\n\n📈 Current price: <code>{price:,.8f}</code>",
        "step2_direction": "✅ Symbol: <b>{symbol}</b>{price_text}\n\n📊 <b>Step 2/5:</b> Select direction:",
        "step3_entry": (
            "✅ Direction: <b>{direction}</b>\n\n"
            "📊 <b>Step 3/5:</b> Enter your entry price:\n"
            "(Or type <code>market</code> for current price)"
        ),
        "market_price_fail": "❌ Could not fetch market price. Enter a specific price.",
        "invalid_price": "❌ Invalid price. Enter a numeric value.",
        "step4_balance": (
            "✅ Entry: <code>{entry_price:,.8f}</code>\n\n"
            "📊 <b>Step 4/5:</b> Enter your account balance (USD):\n"
            "(e.g. <code>10000</code>)"
        ),
        "invalid_balance": "❌ Invalid balance. Enter a positive numeric value, e.g. 10000",
        "step5_risk": (
            "✅ Balance: <code>${balance:,.2f}</code>\n\n"
            "📊 <b>Step 5/5:</b> Select risk % per trade:"
        ),
        "custom_risk_prompt": "📊 Enter custom risk % (e.g., <code>7.5</code>):",
        "risk_selected_timeframe": (
            "✅ Risk: <b>{risk}%</b>\n\n"
            "📊 Select timeframe for ATR calculation:"
        ),
        "invalid_risk": "❌ Enter a valid % between 0.1 and 100.",
        "calculating": "⏳ Calculating <b>{symbol}</b> setup ({timeframe})...",
        "calc_error": "❌ <b>Error:</b> <code>{error}</code>\n\nTry /newtrade again.",
        "help_text": (
            "<b>📖 How to use:</b>\n\n"
            "1. /newtrade\n"
            "2. Enter symbol (BTC, ETH, SOL)\n"
            "3. Select LONG or SHORT\n"
            "4. Enter entry price or \"market\"\n"
            "5. Enter account balance\n"
            "6. Select risk %\n"
            "7. Choose timeframe\n\n"
            "<b>🧮 Formula:</b>\n"
            "<code>Leverage = Risk% / SL Distance%</code>\n\n"
            "<b>⚠️ Warning:</b> High leverage increases risk. Always use stop-losses.\n\n"
            "Use /language to switch between English and فارسی."
        ),
        "price_usage": "Usage: /price <symbol>\nExample: /price BTC",
        "price_result": "📊 <b>{symbol}</b> Futures: <code>{price:,.8f}</code> USDT",
        "price_fail": "❌ Could not fetch price for {symbol}",
        "lang_prompt": "🌐 Choose your language / زبان خود را انتخاب کنید:",
        "lang_set": "✅ Language set to English.",
        "risk_custom_btn": "Custom",
        "main_menu_title": "🏠 <b>Main Menu</b>\n\nWhat would you like to do?",
        "btn_new_trade": "📊 New Trade",
        "btn_price_check": "💲 Price Check",
        "btn_help": "❓ Help",
        "btn_language": "🌐 Language",
        "btn_settings": "⚙️ Settings",
        "btn_main_menu": "🏠 Main Menu",
        "btn_calculate_again": "🔁 Calculate Again",
        "btn_cancel": "❌ Cancel",
        "btn_check_another": "🔁 Check Another",
        "persistent_btn_new_trade": "📊 New Trade",
        "persistent_btn_menu": "🏠 Menu",
        "price_check_prompt": "💲 Enter a symbol to check its price:\n\nExamples: <code>BTC</code>, <code>ETH</code>, <code>SOL</code>",
        "price_check_invalid": "❌ Could not find that symbol. Try again, e.g. <code>BTC</code>",
        "recalc_no_previous": "⚠️ No previous trade to recalculate. Start a new one below.",
        "cancelled": "❌ Cancelled.",
        "rec_template": (
            "{emoji} <b>TRADE RECOMMENDATION</b> {emoji}\n\n"
            "<b>Symbol:</b> <code>{symbol}</code>\n"
            "<b>Direction:</b> <code>{direction}</code>\n\n"
            "📊 <b>PRICE LEVELS</b>\n"
            "├─ Entry Price:     <code>{entry_price:,.8f}</code>\n"
            "├─ Stop Loss:       <code>{stop_loss:,.8f}</code>\n"
            "├─ Take Profit:     <code>{take_profit:,.8f}</code>\n"
            "└─ ATR (14):        <code>{atr:,.8f}</code>\n\n"
            "⚡ <b>RISK MANAGEMENT</b>\n"
            "├─ Account Balance: <code>${account_balance:,.2f}</code>\n"
            "├─ Account Risk:    <code>{risk_percent}%</code> (<code>${risk_amount_usd:,.2f}</code>)\n"
            "├─ SL Distance:     <code>{sl_distance_percent:.2f}%</code>\n"
            "├─ Recommended Lev: <code>{leverage}×</code>\n"
            "├─ Position Size:   <code>${position_size_usd:,.2f}</code>\n"
            "├─ Loss if SL hit:  <code>${actual_loss_if_sl_hit:,.2f}</code>\n"
            "└─ R:R Ratio:       <code>1:{rr_ratio:.2f}</code>\n\n"
            "💡 <b>FORMULA USED</b>\n"
            "<code>Leverage = Risk% / SL Distance%</code>\n"
            "<code>{leverage}× = {risk_percent}% / {sl_distance_percent:.2f}%</code>\n"
            "<i>Position uses your full account balance as margin; leverage is rounded down to "
            "the nearest safe tier, so actual loss if stopped out is at or below your target risk.</i>\n\n"
            "⚠️ <i>Always use isolated margin and verify levels before entering.</i>"
        ),
    },
    "fa": {
        "welcome": (
            "👋 <b>به ربات مدیریت ریسک فیوچرز کوکوین خوش آمدید!</b>\n\n"
            "من با استفاده از سطوح حمایت و مقاومت مبتنی بر ATR از داده‌های فیوچرز کوکوین، "
            "اهرم، حد ضرر و حد سود بهینه را محاسبه می‌کنم.\n\n"
            "<b>فرمول:</b> <code>اهرم = درصد ریسک / درصد فاصله حد ضرر</code>\n\n"
            "برای شروع از دستور /newtrade استفاده کنید.\n"
            "برای تغییر زبان از دستور /language استفاده کنید."
        ),
        "step1_symbol": (
            "📊 <b>مرحله ۱ از ۵:</b> نماد ارز دیجیتال را وارد کنید.\n\n"
            "مثال‌ها: <code>BTC</code>، <code>ETH</code>، <code>SOL</code>"
        ),
        "current_price": "\n\n📈 قیمت فعلی: <code>{price:,.8f}</code>",
        "step2_direction": "✅ نماد: <b>{symbol}</b>{price_text}\n\n📊 <b>مرحله ۲ از ۵:</b> جهت معامله را انتخاب کنید:",
        "step3_entry": (
            "✅ جهت: <b>{direction}</b>\n\n"
            "📊 <b>مرحله ۳ از ۵:</b> قیمت ورود را وارد کنید:\n"
            "(یا برای قیمت لحظه‌ای عبارت <code>market</code> را تایپ کنید)"
        ),
        "market_price_fail": "❌ دریافت قیمت لحظه‌ای ممکن نشد. لطفاً یک قیمت مشخص وارد کنید.",
        "invalid_price": "❌ قیمت نامعتبر است. یک عدد وارد کنید.",
        "step4_balance": (
            "✅ قیمت ورود: <code>{entry_price:,.8f}</code>\n\n"
            "📊 <b>مرحله ۴ از ۵:</b> موجودی حساب خود را به دلار وارد کنید:\n"
            "(مثلاً <code>10000</code>)"
        ),
        "invalid_balance": "❌ موجودی نامعتبر است. یک عدد مثبت وارد کنید، مثلاً 10000",
        "step5_risk": (
            "✅ موجودی: <code>${balance:,.2f}</code>\n\n"
            "📊 <b>مرحله ۵ از ۵:</b> درصد ریسک هر معامله را انتخاب کنید:"
        ),
        "custom_risk_prompt": "📊 درصد ریسک دلخواه را وارد کنید (مثلاً <code>7.5</code>):",
        "risk_selected_timeframe": (
            "✅ ریسک: <b>{risk}%</b>\n\n"
            "📊 بازه زمانی برای محاسبه ATR را انتخاب کنید:"
        ),
        "invalid_risk": "❌ یک درصد معتبر بین 0.1 و 100 وارد کنید.",
        "calculating": "⏳ در حال محاسبه تنظیمات <b>{symbol}</b> ({timeframe})...",
        "calc_error": "❌ <b>خطا:</b> <code>{error}</code>\n\nلطفاً دوباره از /newtrade استفاده کنید.",
        "help_text": (
            "<b>📖 راهنمای استفاده:</b>\n\n"
            "۱. /newtrade\n"
            "۲. نماد را وارد کنید (BTC، ETH، SOL)\n"
            "۳. LONG یا SHORT را انتخاب کنید\n"
            "۴. قیمت ورود یا «market» را وارد کنید\n"
            "۵. موجودی حساب را وارد کنید\n"
            "۶. درصد ریسک را انتخاب کنید\n"
            "۷. بازه زمانی را انتخاب کنید\n\n"
            "<b>🧮 فرمول:</b>\n"
            "<code>اهرم = درصد ریسک / درصد فاصله حد ضرر</code>\n\n"
            "<b>⚠️ هشدار:</b> اهرم بالا ریسک را افزایش می‌دهد. همیشه از حد ضرر استفاده کنید.\n\n"
            "برای تغییر زبان از دستور /language استفاده کنید."
        ),
        "price_usage": "روش استفاده: /price <نماد>\nمثال: /price BTC",
        "price_result": "📊 فیوچرز <b>{symbol}</b>: <code>{price:,.8f}</code> USDT",
        "price_fail": "❌ دریافت قیمت برای {symbol} ممکن نشد",
        "lang_prompt": "🌐 Choose your language / زبان خود را انتخاب کنید:",
        "lang_set": "✅ زبان به فارسی تغییر یافت.",
        "risk_custom_btn": "دلخواه",
        "main_menu_title": "🏠 <b>منوی اصلی</b>\n\nچه کاری می‌خواهید انجام دهید؟",
        "btn_new_trade": "📊 معامله جدید",
        "btn_price_check": "💲 بررسی قیمت",
        "btn_help": "❓ راهنما",
        "btn_language": "🌐 زبان",
        "btn_settings": "⚙️ تنظیمات",
        "btn_main_menu": "🏠 منوی اصلی",
        "btn_calculate_again": "🔁 محاسبه مجدد",
        "btn_cancel": "❌ لغو",
        "btn_check_another": "🔁 بررسی نماد دیگر",
        "persistent_btn_new_trade": "📊 معامله جدید",
        "persistent_btn_menu": "🏠 منو",
        "price_check_prompt": "💲 نماد مورد نظر برای بررسی قیمت را وارد کنید:\n\nمثال‌ها: <code>BTC</code>، <code>ETH</code>، <code>SOL</code>",
        "price_check_invalid": "❌ این نماد یافت نشد. دوباره تلاش کنید، مثلاً <code>BTC</code>",
        "recalc_no_previous": "⚠️ معامله قبلی برای محاسبه مجدد وجود ندارد. یک معامله جدید را از پایین شروع کنید.",
        "cancelled": "❌ لغو شد.",
        "rec_template": (
            "{emoji} <b>پیشنهاد معامله</b> {emoji}\n\n"
            "<b>نماد:</b> <code>{symbol}</code>\n"
            "<b>جهت:</b> <code>{direction}</code>\n\n"
            "📊 <b>سطوح قیمتی</b>\n"
            "├─ قیمت ورود:                 <code>{entry_price:,.8f}</code>\n"
            "├─ حد ضرر:                    <code>{stop_loss:,.8f}</code>\n"
            "├─ حد سود:                    <code>{take_profit:,.8f}</code>\n"
            "└─ ATR (۱۴):                  <code>{atr:,.8f}</code>\n\n"
            "⚡ <b>مدیریت ریسک</b>\n"
            "├─ موجودی حساب:               <code>${account_balance:,.2f}</code>\n"
            "├─ ریسک حساب:                 <code>{risk_percent}%</code> (<code>${risk_amount_usd:,.2f}</code>)\n"
            "├─ فاصله حد ضرر:              <code>{sl_distance_percent:.2f}%</code>\n"
            "├─ اهرم پیشنهادی:             <code>{leverage}×</code>\n"
            "├─ حجم پوزیشن:                <code>${position_size_usd:,.2f}</code>\n"
            "├─ زیان در صورت خوردن حد ضرر: <code>${actual_loss_if_sl_hit:,.2f}</code>\n"
            "└─ نسبت ریسک به ریوارد:       <code>1:{rr_ratio:.2f}</code>\n\n"
            "💡 <b>فرمول استفاده‌شده</b>\n"
            "<code>اهرم = درصد ریسک / درصد فاصله حد ضرر</code>\n"
            "<code>{leverage}× = {risk_percent}% / {sl_distance_percent:.2f}%</code>\n"
            "<i>این محاسبه بر اساس استفاده از کل موجودی حساب به‌عنوان مارجین است؛ اهرم به نزدیک‌ترین "
            "سطح مجاز به‌سمت پایین گرد می‌شود، بنابراین زیان واقعی در صورت فعال شدن حد ضرر برابر یا "
            "کمتر از هدف ریسک شماست.</i>\n\n"
            "⚠️ <i>همیشه از مارجین ایزوله استفاده کنید و سطوح را پیش از ورود بررسی کنید.</i>"
        ),
    },
}


def t(lang: str, key: str, **kwargs) -> str:
    """Look up a localized string and format it with the given kwargs."""
    lang = lang if lang in LOCALES else DEFAULT_LANG
    template = LOCALES[lang].get(key) or LOCALES[DEFAULT_LANG][key]
    return template.format(**kwargs) if kwargs else template


def direction_label(lang: str, direction: str) -> str:
    lang = lang if lang in DIRECTION_LABELS else DEFAULT_LANG
    return DIRECTION_LABELS[lang].get(direction, direction)
