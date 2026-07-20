"""
Bot Application Logic
=====================
Contains all handlers, risk engine, KuCoin client, and state management.
"""

import os
import logging
from dataclasses import dataclass
from typing import Dict, Any, Optional

import numpy as np
import pandas as pd
from aiogram import Bot, Dispatcher, F
from aiogram.types import (
    Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardMarkup, KeyboardButton, BotCommand, BotCommandScopeDefault,
)
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage

from kucoin_futures.client import Market as FuturesMarket

from locales import t, direction_label, DEFAULT_LANG, SUPPORTED_LANGS, LANG_NAMES

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
DEFAULT_RISK_PERCENT = 5.0
DEFAULT_ATR_MULTIPLIER_SL = 1.5
DEFAULT_ATR_MULTIPLIER_TP = 3.0
MIN_RR_RATIO = 1.5
MAX_LEVERAGE = 125

# Per-user language preference and last-used trade params. Kept separate from
# the trade FSM state so they survive state.clear() calls (e.g. /start,
# /newtrade, Cancel). Note: like the trade flow's own FSM storage, these are
# in-memory only and reset on a serverless cold start; there's no persistent
# DB in this project yet.
user_languages: Dict[int, str] = {}
last_trade_params: Dict[int, dict] = {}


def get_lang(user_id: int) -> str:
    return user_languages.get(user_id, DEFAULT_LANG)


@dataclass
class TradeSetup:
    symbol: str
    direction: str
    entry_price: float
    stop_loss: float
    take_profit: float
    atr: float
    account_balance: float
    risk_percent: float
    risk_amount_usd: float
    leverage: int
    position_size_usd: float
    actual_loss_if_sl_hit: float
    rr_ratio: float
    sl_distance_percent: float

    def format_recommendation(self, lang: str = DEFAULT_LANG) -> str:
        emoji = "🟢" if self.direction == "LONG" else "🔴"
        return t(
            lang, "rec_template",
            emoji=emoji,
            symbol=self.symbol,
            direction=direction_label(lang, self.direction),
            entry_price=self.entry_price,
            stop_loss=self.stop_loss,
            take_profit=self.take_profit,
            atr=self.atr,
            account_balance=self.account_balance,
            risk_percent=self.risk_percent,
            risk_amount_usd=self.risk_amount_usd,
            sl_distance_percent=self.sl_distance_percent,
            leverage=self.leverage,
            position_size_usd=self.position_size_usd,
            actual_loss_if_sl_hit=self.actual_loss_if_sl_hit,
            rr_ratio=self.rr_ratio,
        )


class KuCoinFuturesData:
    def __init__(self):
        self.client = FuturesMarket()

    def get_klines(self, symbol: str, granularity: int = 3600, limit: int = 100) -> pd.DataFrame:
        kucoin_symbol = self._normalize_symbol(symbol)
        candles = self.client.get_kline_data(
            symbol=kucoin_symbol, granularity=granularity, begin_t=None, end_t=None
        )
        df = pd.DataFrame(candles, columns=["timestamp", "open", "high", "low", "close", "volume", "turnover"])
        df = df.astype(float)
        df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
        return df.sort_values("timestamp").reset_index(drop=True)

    def _normalize_symbol(self, symbol: str) -> str:
        symbol = symbol.upper().replace("/", "").replace("-", "")
        mappings = {
            "BTC": "XBTUSDTM", "ETH": "ETHUSDTM", "SOL": "SOLUSDTM",
            "XRP": "XRPUSDTM", "DOGE": "DOGEUSDTM", "ADA": "ADAUSDTM",
            "AVAX": "AVAXUSDTM", "LINK": "LINKUSDTM", "MATIC": "MATICUSDTM",
            "DOT": "DOTUSDTM",
        }
        if symbol.endswith("USDM") or symbol.endswith("USDTM"):
            return symbol
        base = symbol.replace("USDT", "").replace("USD", "")
        return mappings.get(base, f"{base}USDTM")

    def get_ticker(self, symbol: str) -> Dict[str, Any]:
        return self.client.get_ticker(self._normalize_symbol(symbol))


class TechnicalAnalyzer:
    @staticmethod
    def calculate_atr(df: pd.DataFrame, period: int = 14) -> float:
        high, low, close = df["high"], df["low"], df["close"]
        tr1 = high - low
        tr2 = abs(high - close.shift(1))
        tr3 = abs(low - close.shift(1))
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        return float(tr.rolling(window=period).mean().iloc[-1])

    @staticmethod
    def find_support_resistance(df: pd.DataFrame, lookback: int = 20) -> tuple:
        recent = df.tail(lookback)
        return float(recent["low"].min()), float(recent["high"].max())


class RiskEngine:
    def __init__(self):
        self.kucoin = KuCoinFuturesData()
        self.analyzer = TechnicalAnalyzer()

    def calculate_setup(
        self,
        symbol: str,
        direction: str,
        entry_price: float,
        account_balance: float,
        risk_percent: float = DEFAULT_RISK_PERCENT,
        timeframe: str = "1h",
    ) -> TradeSetup:
        tf_map = {"1m": 1, "5m": 5, "15m": 15, "1h": 60, "4h": 240, "1d": 1440}
        granularity = tf_map.get(timeframe, 60)

        df = self.kucoin.get_klines(symbol, granularity=granularity, limit=100)
        atr = self.analyzer.calculate_atr(df, period=14)
        support, resistance = self.analyzer.find_support_resistance(df, lookback=20)

        if direction == "LONG":
            atr_sl = entry_price - (atr * DEFAULT_ATR_MULTIPLIER_SL)
            support_sl = support * 0.999
            stop_loss = max(atr_sl, support_sl)
            if stop_loss >= entry_price:
                stop_loss = entry_price * 0.99
        else:
            atr_sl = entry_price + (atr * DEFAULT_ATR_MULTIPLIER_SL)
            resistance_sl = resistance * 1.001
            stop_loss = min(atr_sl, resistance_sl)
            if stop_loss <= entry_price:
                stop_loss = entry_price * 1.01

        sl_distance = abs(entry_price - stop_loss)

        if direction == "LONG":
            atr_tp = entry_price + (atr * DEFAULT_ATR_MULTIPLIER_TP)
            resistance_tp = resistance * 0.999
            take_profit = min(atr_tp, resistance_tp)
            min_tp = entry_price + (sl_distance * MIN_RR_RATIO)
            if take_profit < min_tp:
                take_profit = min_tp
        else:
            atr_tp = entry_price - (atr * DEFAULT_ATR_MULTIPLIER_TP)
            support_tp = support * 1.001
            take_profit = max(atr_tp, support_tp)
            min_tp = entry_price - (sl_distance * MIN_RR_RATIO)
            if take_profit > min_tp:
                take_profit = min_tp

        sl_distance_percent = (sl_distance / entry_price) * 100
        raw_leverage = risk_percent / sl_distance_percent
        leverage = int(min(raw_leverage, MAX_LEVERAGE))
        safe_leverages = [1, 2, 3, 5, 10, 15, 20, 25, 30, 50, 75, 100, 125]
        leverage = max([l for l in safe_leverages if l <= leverage], default=1)

        # Position sizing: with the full account balance used as margin, this
        # leverage is exactly the one that makes a stop-loss hit cost precisely
        # `risk_percent` of the account. Notional exposure = balance × leverage.
        risk_amount_usd = account_balance * (risk_percent / 100)
        position_size_usd = account_balance * leverage
        actual_loss_if_sl_hit = position_size_usd * (sl_distance_percent / 100)

        tp_distance = abs(take_profit - entry_price)
        rr_ratio = tp_distance / sl_distance if sl_distance > 0 else 0

        return TradeSetup(
            symbol=symbol.upper(),
            direction=direction,
            entry_price=round(entry_price, 8),
            stop_loss=round(stop_loss, 8),
            take_profit=round(take_profit, 8),
            atr=round(atr, 8),
            account_balance=round(account_balance, 2),
            risk_percent=risk_percent,
            risk_amount_usd=round(risk_amount_usd, 2),
            leverage=leverage,
            position_size_usd=round(position_size_usd, 2),
            actual_loss_if_sl_hit=round(actual_loss_if_sl_hit, 2),
            rr_ratio=round(rr_ratio, 2),
            sl_distance_percent=round(sl_distance_percent, 4),
        )


storage = MemoryStorage()
dp = Dispatcher(storage=storage)
risk_engine = RiskEngine()


def create_bot() -> Bot:
    return Bot(token=TELEGRAM_BOT_TOKEN)


async def set_bot_commands(bot: Bot):
    """Populate Telegram's native '/' command list (in addition to the button UI)."""
    commands_en = [
        BotCommand(command="start", description="Open main menu"),
        BotCommand(command="newtrade", description="Start a new trade calculation"),
        BotCommand(command="price", description="Check a futures price"),
        BotCommand(command="language", description="Switch language"),
        BotCommand(command="help", description="How to use this bot"),
    ]
    commands_fa = [
        BotCommand(command="start", description="باز کردن منوی اصلی"),
        BotCommand(command="newtrade", description="شروع محاسبه معامله جدید"),
        BotCommand(command="price", description="بررسی قیمت فیوچرز"),
        BotCommand(command="language", description="تغییر زبان"),
        BotCommand(command="help", description="راهنمای استفاده از ربات"),
    ]
    await bot.set_my_commands(commands_en, scope=BotCommandScopeDefault())
    await bot.set_my_commands(commands_fa, scope=BotCommandScopeDefault(), language_code="fa")


# ---------------------------------------------------------------------------
# Keyboards
# ---------------------------------------------------------------------------

def get_persistent_keyboard(lang: str) -> ReplyKeyboardMarkup:
    """Bottom-row buttons that stay visible at all times, regardless of
    scroll position, so the user never has to type a command."""
    return ReplyKeyboardMarkup(
        keyboard=[[
            KeyboardButton(text=t(lang, "persistent_btn_new_trade")),
            KeyboardButton(text=t(lang, "persistent_btn_menu")),
        ]],
        resize_keyboard=True,
        is_persistent=True,
    )


def get_main_menu_keyboard(lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t(lang, "btn_new_trade"), callback_data="menu:newtrade")],
        [InlineKeyboardButton(text=t(lang, "btn_price_check"), callback_data="menu:price")],
        [
            InlineKeyboardButton(text=t(lang, "btn_help"), callback_data="menu:help"),
            InlineKeyboardButton(text=t(lang, "btn_language"), callback_data="menu:language"),
        ],
    ])


def get_cancel_keyboard(lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t(lang, "btn_cancel"), callback_data="menu:cancel")]
    ])


def get_language_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🇬🇧 English", callback_data="lang:en"),
            InlineKeyboardButton(text="🇮🇷 فارسی", callback_data="lang:fa"),
        ]
    ])


def get_direction_keyboard(lang: str) -> InlineKeyboardMarkup:
    long_label = direction_label(lang, "LONG")
    short_label = direction_label(lang, "SHORT")
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text=f"🟢 {long_label}", callback_data="dir:LONG"),
            InlineKeyboardButton(text=f"🔴 {short_label}", callback_data="dir:SHORT"),
        ],
        [InlineKeyboardButton(text=t(lang, "btn_cancel"), callback_data="menu:cancel")],
    ])


def get_risk_keyboard(lang: str) -> InlineKeyboardMarkup:
    custom_label = t(lang, "risk_custom_btn")
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="1%", callback_data="risk:1"),
            InlineKeyboardButton(text="2%", callback_data="risk:2"),
            InlineKeyboardButton(text="3%", callback_data="risk:3"),
        ],
        [
            InlineKeyboardButton(text="5%", callback_data="risk:5"),
            InlineKeyboardButton(text="10%", callback_data="risk:10"),
            InlineKeyboardButton(text=custom_label, callback_data="risk:custom"),
        ],
        [InlineKeyboardButton(text=t(lang, "btn_cancel"), callback_data="menu:cancel")],
    ])


def get_timeframe_keyboard(lang: str) -> InlineKeyboardMarkup:
    # Timeframe abbreviations (15m/1h/4h/1d) are standard trading shorthand
    # and are kept the same across languages.
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="15m", callback_data="tf:15m"),
            InlineKeyboardButton(text="1h", callback_data="tf:1h"),
            InlineKeyboardButton(text="4h", callback_data="tf:4h"),
        ],
        [InlineKeyboardButton(text="1d", callback_data="tf:1d")],
        [InlineKeyboardButton(text=t(lang, "btn_cancel"), callback_data="menu:cancel")],
    ])


def get_post_result_keyboard(lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text=t(lang, "btn_new_trade"), callback_data="menu:newtrade"),
            InlineKeyboardButton(text=t(lang, "btn_calculate_again"), callback_data="trade:recalc"),
        ],
        [
            InlineKeyboardButton(text=t(lang, "btn_settings"), callback_data="menu:language"),
            InlineKeyboardButton(text=t(lang, "btn_main_menu"), callback_data="menu:main"),
        ],
    ])


def get_price_result_keyboard(lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text=t(lang, "btn_check_another"), callback_data="menu:price"),
            InlineKeyboardButton(text=t(lang, "btn_main_menu"), callback_data="menu:main"),
        ],
    ])


def get_back_to_menu_keyboard(lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t(lang, "btn_main_menu"), callback_data="menu:main")]
    ])


class TradeStates(StatesGroup):
    waiting_for_symbol = State()
    waiting_for_entry = State()
    waiting_for_balance = State()
    waiting_for_risk = State()


class PriceCheckStates(StatesGroup):
    waiting_for_symbol = State()


# Persistent reply-keyboard button labels, in every supported language, mapped
# to the action they trigger. Checked ahead of any state-specific handler so
# they work as a global escape hatch no matter where the user is in a flow.
def _persistent_button_map(key: str) -> Dict[str, str]:
    return {t(lang, key): lang for lang in SUPPORTED_LANGS}


def register_handlers():
    new_trade_labels = set(_persistent_button_map("persistent_btn_new_trade").keys())
    menu_labels = set(_persistent_button_map("persistent_btn_menu").keys())

    async def show_main_menu(target_user_id: int, send):
        lang = get_lang(target_user_id)
        await send(t(lang, "main_menu_title"), parse_mode="HTML", reply_markup=get_main_menu_keyboard(lang))

    @dp.message(F.text.in_(new_trade_labels))
    async def persistent_new_trade(message: Message, state: FSMContext):
        await start_new_trade(message, state)

    @dp.message(F.text.in_(menu_labels))
    async def persistent_main_menu(message: Message, state: FSMContext):
        await state.clear()
        await show_main_menu(message.from_user.id, message.answer)

    @dp.message(Command("language"))
    async def cmd_language(message: Message):
        lang = get_lang(message.from_user.id)
        await message.answer(t(lang, "lang_prompt"), reply_markup=get_language_keyboard())

    @dp.callback_query(F.data.startswith("lang:"))
    async def process_language(callback: CallbackQuery):
        lang = callback.data.split(":")[1]
        if lang not in SUPPORTED_LANGS:
            lang = DEFAULT_LANG
        user_languages[callback.from_user.id] = lang
        await callback.message.edit_text(t(lang, "lang_set"), parse_mode="HTML")
        await callback.message.answer(
            t(lang, "main_menu_title"), parse_mode="HTML",
            reply_markup=get_main_menu_keyboard(lang)
        )
        await callback.message.answer(".", reply_markup=get_persistent_keyboard(lang))
        await callback.answer()

    @dp.message(Command("start"))
    async def cmd_start(message: Message, state: FSMContext):
        await state.clear()
        lang = get_lang(message.from_user.id)
        await message.answer(t(lang, "welcome"), parse_mode="HTML", reply_markup=get_persistent_keyboard(lang))
        await message.answer(t(lang, "main_menu_title"), parse_mode="HTML", reply_markup=get_main_menu_keyboard(lang))

    async def start_new_trade(message: Message, state: FSMContext):
        await state.clear()
        lang = get_lang(message.from_user.id)
        await state.set_state(TradeStates.waiting_for_symbol)
        await message.answer(t(lang, "step1_symbol"), parse_mode="HTML", reply_markup=get_cancel_keyboard(lang))

    @dp.message(Command("newtrade"))
    async def cmd_newtrade(message: Message, state: FSMContext):
        await start_new_trade(message, state)

    @dp.callback_query(F.data == "menu:newtrade")
    async def cb_new_trade(callback: CallbackQuery, state: FSMContext):
        await state.clear()
        lang = get_lang(callback.from_user.id)
        await state.set_state(TradeStates.waiting_for_symbol)
        await callback.message.edit_text(t(lang, "step1_symbol"), parse_mode="HTML", reply_markup=get_cancel_keyboard(lang))
        await callback.answer()

    @dp.callback_query(F.data == "menu:main")
    async def cb_main_menu(callback: CallbackQuery, state: FSMContext):
        await state.clear()
        lang = get_lang(callback.from_user.id)
        await callback.message.edit_text(
            t(lang, "main_menu_title"), parse_mode="HTML", reply_markup=get_main_menu_keyboard(lang)
        )
        await callback.answer()

    @dp.callback_query(F.data == "menu:cancel")
    async def cb_cancel(callback: CallbackQuery, state: FSMContext):
        await state.clear()
        lang = get_lang(callback.from_user.id)
        await callback.message.edit_text(
            t(lang, "cancelled") + "\n\n" + t(lang, "main_menu_title"),
            parse_mode="HTML", reply_markup=get_main_menu_keyboard(lang)
        )
        await callback.answer()

    @dp.callback_query(F.data == "menu:help")
    async def cb_help(callback: CallbackQuery):
        lang = get_lang(callback.from_user.id)
        await callback.message.edit_text(
            t(lang, "help_text"), parse_mode="HTML", reply_markup=get_back_to_menu_keyboard(lang)
        )
        await callback.answer()

    @dp.callback_query(F.data == "menu:language")
    async def cb_language(callback: CallbackQuery):
        lang = get_lang(callback.from_user.id)
        await callback.message.edit_text(t(lang, "lang_prompt"), reply_markup=get_language_keyboard())
        await callback.answer()

    @dp.callback_query(F.data == "menu:price")
    async def cb_price_check(callback: CallbackQuery, state: FSMContext):
        await state.clear()
        lang = get_lang(callback.from_user.id)
        await state.set_state(PriceCheckStates.waiting_for_symbol)
        await callback.message.edit_text(
            t(lang, "price_check_prompt"), parse_mode="HTML", reply_markup=get_cancel_keyboard(lang)
        )
        await callback.answer()

    @dp.message(PriceCheckStates.waiting_for_symbol)
    async def process_price_check(message: Message, state: FSMContext):
        lang = get_lang(message.from_user.id)
        symbol = message.text.strip().upper()
        try:
            ticker = risk_engine.kucoin.get_ticker(symbol)
            price = float(ticker.get("price", 0))
            if not price:
                raise ValueError
            await message.answer(
                t(lang, "price_result", symbol=symbol, price=price),
                parse_mode="HTML", reply_markup=get_price_result_keyboard(lang)
            )
            await state.clear()
        except Exception:
            await message.answer(
                t(lang, "price_check_invalid"), parse_mode="HTML", reply_markup=get_cancel_keyboard(lang)
            )

    @dp.message(TradeStates.waiting_for_symbol)
    async def process_symbol(message: Message, state: FSMContext):
        lang = get_lang(message.from_user.id)
        symbol = message.text.strip().upper()
        await state.update_data(symbol=symbol)
        await state.set_state(TradeStates.waiting_for_entry)
        try:
            ticker = risk_engine.kucoin.get_ticker(symbol)
            current_price = float(ticker.get("price", 0))
            price_text = t(lang, "current_price", price=current_price)
        except Exception:
            price_text = ""
        await message.answer(
            t(lang, "step2_direction", symbol=symbol, price_text=price_text),
            parse_mode="HTML",
            reply_markup=get_direction_keyboard(lang)
        )

    @dp.callback_query(F.data.startswith("dir:"))
    async def process_direction(callback: CallbackQuery, state: FSMContext):
        lang = get_lang(callback.from_user.id)
        direction = callback.data.split(":")[1]
        await state.update_data(direction=direction)
        await state.set_state(TradeStates.waiting_for_entry)
        await callback.message.edit_text(
            t(lang, "step3_entry", direction=direction_label(lang, direction)),
            parse_mode="HTML",
            reply_markup=get_cancel_keyboard(lang)
        )
        await callback.answer()

    @dp.message(TradeStates.waiting_for_entry)
    async def process_entry(message: Message, state: FSMContext):
        lang = get_lang(message.from_user.id)
        entry_text = message.text.strip().lower()
        data = await state.get_data()
        symbol = data["symbol"]
        if entry_text == "market":
            try:
                ticker = risk_engine.kucoin.get_ticker(symbol)
                entry_price = float(ticker.get("price", 0))
            except:
                await message.answer(t(lang, "market_price_fail"), parse_mode="HTML", reply_markup=get_cancel_keyboard(lang))
                return
        else:
            try:
                entry_price = float(entry_text)
            except ValueError:
                await message.answer(t(lang, "invalid_price"), parse_mode="HTML", reply_markup=get_cancel_keyboard(lang))
                return
        await state.update_data(entry_price=entry_price)
        await state.set_state(TradeStates.waiting_for_balance)
        await message.answer(
            t(lang, "step4_balance", entry_price=entry_price),
            parse_mode="HTML",
            reply_markup=get_cancel_keyboard(lang)
        )

    @dp.message(TradeStates.waiting_for_balance)
    async def process_balance(message: Message, state: FSMContext):
        lang = get_lang(message.from_user.id)
        try:
            account_balance = float(message.text.strip().replace(",", ""))
            if account_balance <= 0:
                raise ValueError
        except ValueError:
            await message.answer(t(lang, "invalid_balance"), parse_mode="HTML", reply_markup=get_cancel_keyboard(lang))
            return
        await state.update_data(account_balance=account_balance)
        await state.set_state(TradeStates.waiting_for_risk)
        await message.answer(
            t(lang, "step5_risk", balance=account_balance),
            parse_mode="HTML",
            reply_markup=get_risk_keyboard(lang)
        )

    @dp.callback_query(F.data.startswith("risk:"))
    async def process_risk(callback: CallbackQuery, state: FSMContext):
        lang = get_lang(callback.from_user.id)
        risk_input = callback.data.split(":")[1]
        if risk_input == "custom":
            await callback.message.edit_text(
                t(lang, "custom_risk_prompt"), parse_mode="HTML", reply_markup=get_cancel_keyboard(lang)
            )
            await callback.answer()
            return
        risk_percent = float(risk_input)
        await state.update_data(risk_percent=risk_percent)
        await callback.message.edit_text(
            t(lang, "risk_selected_timeframe", risk=risk_percent),
            parse_mode="HTML",
            reply_markup=get_timeframe_keyboard(lang)
        )
        await callback.answer()

    @dp.message(TradeStates.waiting_for_risk)
    async def process_custom_risk(message: Message, state: FSMContext):
        lang = get_lang(message.from_user.id)
        try:
            risk_percent = float(message.text.strip())
            if not (0.1 <= risk_percent <= 100):
                raise ValueError
        except ValueError:
            await message.answer(t(lang, "invalid_risk"), parse_mode="HTML", reply_markup=get_cancel_keyboard(lang))
            return
        await state.update_data(risk_percent=risk_percent)
        await message.answer(
            t(lang, "risk_selected_timeframe", risk=risk_percent),
            parse_mode="HTML",
            reply_markup=get_timeframe_keyboard(lang)
        )

    async def run_calculation(user_id: int, data: dict, lang: str, edit_target):
        try:
            setup = risk_engine.calculate_setup(
                symbol=data["symbol"],
                direction=data["direction"],
                entry_price=data["entry_price"],
                account_balance=data["account_balance"],
                risk_percent=data["risk_percent"],
                timeframe=data["timeframe"],
            )
            last_trade_params[user_id] = dict(data)
            await edit_target(setup.format_recommendation(lang), parse_mode="HTML", reply_markup=get_post_result_keyboard(lang))
        except Exception as e:
            logger.error(f"Calculation error: {e}")
            await edit_target(t(lang, "calc_error", error=str(e)), parse_mode="HTML", reply_markup=get_back_to_menu_keyboard(lang))

    @dp.callback_query(F.data.startswith("tf:"))
    async def process_timeframe(callback: CallbackQuery, state: FSMContext):
        lang = get_lang(callback.from_user.id)
        timeframe = callback.data.split(":")[1]
        data = await state.get_data()
        data["timeframe"] = timeframe
        loading = await callback.message.edit_text(
            t(lang, "calculating", symbol=data["symbol"], timeframe=timeframe), parse_mode="HTML"
        )
        await run_calculation(callback.from_user.id, data, lang, loading.edit_text)
        await state.clear()
        await callback.answer()

    @dp.callback_query(F.data == "trade:recalc")
    async def cb_recalc(callback: CallbackQuery, state: FSMContext):
        lang = get_lang(callback.from_user.id)
        data = last_trade_params.get(callback.from_user.id)
        if not data:
            await callback.message.edit_text(
                t(lang, "recalc_no_previous"), parse_mode="HTML", reply_markup=get_main_menu_keyboard(lang)
            )
            await callback.answer()
            return
        loading = await callback.message.edit_text(
            t(lang, "calculating", symbol=data["symbol"], timeframe=data["timeframe"]), parse_mode="HTML"
        )
        await run_calculation(callback.from_user.id, data, lang, loading.edit_text)
        await callback.answer()

    @dp.message(Command("help"))
    async def cmd_help(message: Message):
        lang = get_lang(message.from_user.id)
        await message.answer(t(lang, "help_text"), parse_mode="HTML", reply_markup=get_back_to_menu_keyboard(lang))

    @dp.message(Command("price"))
    async def cmd_price(message: Message):
        lang = get_lang(message.from_user.id)
        args = message.text.split()
        if len(args) < 2:
            await message.answer(t(lang, "price_usage"), parse_mode="HTML")
            return
        symbol = args[1].upper()
        try:
            ticker = risk_engine.kucoin.get_ticker(symbol)
            price = float(ticker.get("price", 0))
            await message.answer(
                t(lang, "price_result", symbol=symbol, price=price),
                parse_mode="HTML", reply_markup=get_price_result_keyboard(lang)
            )
        except Exception:
            await message.answer(t(lang, "price_fail", symbol=symbol), parse_mode="HTML")
