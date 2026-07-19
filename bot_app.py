"""
Bot Application Logic
=====================
Contains all handlers, risk engine, KuCoin client, and state management.
"""

import os
import logging
from dataclasses import dataclass
from typing import Dict, Any

import numpy as np
import pandas as pd
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage

from kucoin_futures.client import Market as FuturesMarket

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
DEFAULT_RISK_PERCENT = 5.0
DEFAULT_ATR_MULTIPLIER_SL = 1.5
DEFAULT_ATR_MULTIPLIER_TP = 3.0
MIN_RR_RATIO = 1.5
MAX_LEVERAGE = 125


@dataclass
class TradeSetup:
    symbol: str
    direction: str
    entry_price: float
    stop_loss: float
    take_profit: float
    atr: float
    risk_percent: float
    leverage: int
    position_size_usd: float
    rr_ratio: float
    sl_distance_percent: float

    def format_recommendation(self) -> str:
        emoji = "🟢" if self.direction == "LONG" else "🔴"
        return f"""{emoji} <b>TRADE RECOMMENDATION</b> {emoji}

<b>Symbol:</b> <code>{self.symbol}</code>
<b>Direction:</b> <code>{self.direction}</code>

📊 <b>PRICE LEVELS</b>
├─ Entry Price:     <code>{self.entry_price:,.8f}</code>
├─ Stop Loss:       <code>{self.stop_loss:,.8f}</code>
├─ Take Profit:     <code>{self.take_profit:,.8f}</code>
└─ ATR (14):        <code>{self.atr:,.8f}</code>

⚡ <b>RISK MANAGEMENT</b>
├─ Account Risk:    <code>{self.risk_percent}%</code>
├─ SL Distance:     <code>{self.sl_distance_percent:.2f}%</code>
├─ Recommended Lev: <code>{self.leverage}×</code>
├─ Position Size:   <code>${self.position_size_usd:,.2f}</code>
└─ R:R Ratio:       <code>1:{self.rr_ratio:.2f}</code>

💡 <b>FORMULA USED</b>
<code>Leverage = Risk% / SL Distance%</code>
<code>{self.leverage}× = {self.risk_percent}% / {self.sl_distance_percent:.2f}%</code>

⚠️ <i>Always use isolated margin and verify levels before entering.</i>"""


class KuCoinFuturesData:
    def __init__(self):
        self.client = FuturesMarket()

    def get_klines(self, symbol: str, granularity: int = 3600, limit: int = 100) -> pd.DataFrame:
        kucoin_symbol = self._normalize_symbol(symbol)
        candles = self.client.get_kline_data(
            symbol=kucoin_symbol, granularity=granularity, begin=None, end=None
        )
        df = pd.DataFrame(candles, columns=["timestamp", "open", "close", "high", "low", "volume"])
        df = df.astype(float)
        df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
        return df.sort_values("timestamp").reset_index(drop=True)

    def _normalize_symbol(self, symbol: str) -> str:
        symbol = symbol.upper().replace("/", "").replace("-", "")
        mappings = {
            "BTC": "XBTUSDM", "ETH": "ETHUSDM", "SOL": "SOLUSDM",
            "XRP": "XRPUSDM", "DOGE": "DOGEUSDM", "ADA": "ADAUSDM",
            "AVAX": "AVAXUSDM", "LINK": "LINKUSDM", "MATIC": "MATICUSDM",
            "DOT": "DOTUSDM",
        }
        if symbol.endswith("USDM") or symbol.endswith("USDTM"):
            return symbol
        base = symbol.replace("USDT", "").replace("USD", "")
        return mappings.get(base, f"{base}USDM")

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
        risk_percent: float = DEFAULT_RISK_PERCENT,
        timeframe: str = "1h",
    ) -> TradeSetup:
        tf_map = {"1m": 60, "5m": 300, "15m": 900, "1h": 3600, "4h": 14400, "1d": 86400}
        granularity = tf_map.get(timeframe, 3600)

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

        account_size = 10000
        position_size_multiplier = risk_percent / (sl_distance_percent * leverage)
        position_size_usd = account_size * position_size_multiplier

        tp_distance = abs(take_profit - entry_price)
        rr_ratio = tp_distance / sl_distance if sl_distance > 0 else 0

        return TradeSetup(
            symbol=symbol.upper(),
            direction=direction,
            entry_price=round(entry_price, 8),
            stop_loss=round(stop_loss, 8),
            take_profit=round(take_profit, 8),
            atr=round(atr, 8),
            risk_percent=risk_percent,
            leverage=leverage,
            position_size_usd=round(position_size_usd, 2),
            rr_ratio=round(rr_ratio, 2),
            sl_distance_percent=round(sl_distance_percent, 4),
        )


storage = MemoryStorage()
dp = Dispatcher(storage=storage)
risk_engine = RiskEngine()


def create_bot() -> Bot:
    return Bot(token=TELEGRAM_BOT_TOKEN)


def get_direction_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🟢 BUY / LONG", callback_data="dir:LONG"),
            InlineKeyboardButton(text="🔴 SELL / SHORT", callback_data="dir:SHORT"),
        ]
    ])


def get_risk_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="1%", callback_data="risk:1"),
            InlineKeyboardButton(text="2%", callback_data="risk:2"),
            InlineKeyboardButton(text="3%", callback_data="risk:3"),
        ],
        [
            InlineKeyboardButton(text="5%", callback_data="risk:5"),
            InlineKeyboardButton(text="10%", callback_data="risk:10"),
            InlineKeyboardButton(text="Custom", callback_data="risk:custom"),
        ]
    ])


def get_timeframe_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="15m", callback_data="tf:15m"),
            InlineKeyboardButton(text="1h", callback_data="tf:1h"),
            InlineKeyboardButton(text="4h", callback_data="tf:4h"),
        ],
        [
            InlineKeyboardButton(text="1d", callback_data="tf:1d"),
        ]
    ])


class TradeStates(StatesGroup):
    waiting_for_symbol = State()
    waiting_for_entry = State()
    waiting_for_risk = State()


def register_handlers():
    @dp.message(Command("start"))
    async def cmd_start(message: Message, state: FSMContext):
        await state.clear()
        await message.answer(
            "👋 <b>Welcome to the KuCoin Futures Risk Manager!</b>\n\n"
            "I calculate optimal leverage, stop-loss, and take-profit using "
            "ATR-based support/resistance from KuCoin Futures data.\n\n"
            "<b>Formula:</b> <code>Leverage = Risk% / SL Distance%</code>\n\n"
            "Use /newtrade to start.",
            parse_mode="HTML"
        )

    @dp.message(Command("newtrade"))
    async def cmd_newtrade(message: Message, state: FSMContext):
        await state.clear()
        await state.set_state(TradeStates.waiting_for_symbol)
        await message.answer(
            "📊 <b>Step 1/4:</b> Enter the cryptocurrency symbol.\n\n"
            "Examples: <code>BTC</code>, <code>ETH</code>, <code>SOL</code>",
            parse_mode="HTML"
        )

    @dp.message(TradeStates.waiting_for_symbol)
    async def process_symbol(message: Message, state: FSMContext):
        symbol = message.text.strip().upper()
        await state.update_data(symbol=symbol)
        await state.set_state(TradeStates.waiting_for_entry)
        try:
            ticker = risk_engine.kucoin.get_ticker(symbol)
            current_price = float(ticker.get("price", 0))
            price_text = f"\n\n📈 Current price: <code>{current_price:,.8f}</code>"
        except Exception:
            price_text = ""
        await message.answer(
            f"✅ Symbol: <b>{symbol}</b>{price_text}\n\n"
            f"📊 <b>Step 2/4:</b> Select direction:",
            parse_mode="HTML",
            reply_markup=get_direction_keyboard()
        )

    @dp.callback_query(F.data.startswith("dir:"))
    async def process_direction(callback: CallbackQuery, state: FSMContext):
        direction = callback.data.split(":")[1]
        await state.update_data(direction=direction)
        await state.set_state(TradeStates.waiting_for_entry)
        await callback.message.edit_text(
            f"✅ Direction: <b>{direction}</b>\n\n"
            f"📊 <b>Step 3/4:</b> Enter your entry price:\n"
            f"(Or type <code>market</code> for current price)",
            parse_mode="HTML"
        )
        await callback.answer()

    @dp.message(TradeStates.waiting_for_entry)
    async def process_entry(message: Message, state: FSMContext):
        entry_text = message.text.strip().lower()
        data = await state.get_data()
        symbol = data["symbol"]
        if entry_text == "market":
            try:
                ticker = risk_engine.kucoin.get_ticker(symbol)
                entry_price = float(ticker.get("price", 0))
            except:
                await message.answer("❌ Could not fetch market price. Enter a specific price.")
                return
        else:
            try:
                entry_price = float(entry_text)
            except ValueError:
                await message.answer("❌ Invalid price. Enter a numeric value.")
                return
        await state.update_data(entry_price=entry_price)
        await state.set_state(TradeStates.waiting_for_risk)
        await message.answer(
            f"✅ Entry: <code>{entry_price:,.8f}</code>\n\n"
            f"📊 <b>Step 4/4:</b> Select risk % per trade:",
            parse_mode="HTML",
            reply_markup=get_risk_keyboard()
        )

    @dp.callback_query(F.data.startswith("risk:"))
    async def process_risk(callback: CallbackQuery, state: FSMContext):
        risk_input = callback.data.split(":")[1]
        if risk_input == "custom":
            await callback.message.edit_text(
                "📊 Enter custom risk % (e.g., <code>7.5</code>):",
                parse_mode="HTML"
            )
            await callback.answer()
            return
        risk_percent = float(risk_input)
        await state.update_data(risk_percent=risk_percent)
        await callback.message.edit_text(
            f"✅ Risk: <b>{risk_percent}%</b>\n\n"
            f"📊 Select timeframe for ATR calculation:",
            parse_mode="HTML",
            reply_markup=get_timeframe_keyboard()
        )
        await callback.answer()

    @dp.message(TradeStates.waiting_for_risk)
    async def process_custom_risk(message: Message, state: FSMContext):
        try:
            risk_percent = float(message.text.strip())
            if not (0.1 <= risk_percent <= 100):
                raise ValueError
        except ValueError:
            await message.answer("❌ Enter a valid % between 0.1 and 100.")
            return
        await state.update_data(risk_percent=risk_percent)
        await message.answer(
            f"✅ Risk: <b>{risk_percent}%</b>\n\n"
            f"📊 Select timeframe for ATR calculation:",
            parse_mode="HTML",
            reply_markup=get_timeframe_keyboard()
        )

    @dp.callback_query(F.data.startswith("tf:"))
    async def process_timeframe(callback: CallbackQuery, state: FSMContext):
        timeframe = callback.data.split(":")[1]
        data = await state.get_data()
        loading = await callback.message.edit_text(
            f"⏳ Calculating <b>{data['symbol']}</b> setup ({timeframe})...",
            parse_mode="HTML"
        )
        try:
            setup = risk_engine.calculate_setup(
                symbol=data["symbol"],
                direction=data["direction"],
                entry_price=data["entry_price"],
                risk_percent=data["risk_percent"],
                timeframe=timeframe,
            )
            await loading.edit_text(setup.format_recommendation(), parse_mode="HTML")
        except Exception as e:
            logger.error(f"Calculation error: {e}")
            await loading.edit_text(
                f"❌ <b>Error:</b> <code>{str(e)}</code>\n\nTry /newtrade again.",
                parse_mode="HTML"
            )
        await state.clear()
        await callback.answer()

    @dp.message(Command("help"))
    async def cmd_help(message: Message):
        await message.answer(
            "<b>📖 How to use:</b>\n\n"
            "1. /newtrade\n"
            "2. Enter symbol (BTC, ETH, SOL)\n"
            "3. Select LONG or SHORT\n"
            "4. Enter entry price or \"market\"\n"
            "5. Select risk %\n"
            "6. Choose timeframe\n\n"
            "<b>🧮 Formula:</b>\n"
            "<code>Leverage = Risk% / SL Distance%</code>\n\n"
            "<b>⚠️ Warning:</b> High leverage increases risk. Always use stop-losses.",
            parse_mode="HTML"
        )

    @dp.message(Command("price"))
    async def cmd_price(message: Message):
        args = message.text.split()
        if len(args) < 2:
            await message.answer("Usage: /price <symbol>\nExample: /price BTC")
            return
        try:
            ticker = risk_engine.kucoin.get_ticker(args[1].upper())
            price = float(ticker.get("price", 0))
            await message.answer(
                f"📊 <b>{args[1].upper()}</b> Futures: <code>{price:,.8f}</code> USDT",
                parse_mode="HTML"
            )
        except Exception:
            await message.answer(f"❌ Could not fetch price for {args[1].upper()}")
