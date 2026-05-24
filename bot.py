"""WalletMonitor Telegram bot entrypoint."""

import asyncio
import logging
import os
import sys
import time

from dotenv import load_dotenv
from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    KeyboardButtonRequestChat,
    ReplyKeyboardMarkup,
    Update,
)
from telegram.constants import ParseMode
from telegram.error import NetworkError, TimedOut
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)
from telegram.request import HTTPXRequest

from database import Database
from monitor import TronMonitor

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
TRONSCAN_API_KEY = os.getenv("TRONSCAN_API_KEY", os.getenv("TRONGRID_API_KEY", ""))
POLL_INTERVAL = int(os.getenv("POLL_INTERVAL", "10"))
NOTIFY_CHAT_ID = os.getenv("NOTIFY_CHAT_ID", "")
DB_PATH = os.getenv("DB_PATH", "wallets.db")
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
PROXY_URL = os.getenv("PROXY_URL", "")
ENERGY_TRX_ADDRESS = os.getenv("ENERGY_TRX_ADDRESS", "")
TG_PREMIUM_URL = os.getenv("TG_PREMIUM_URL", "")

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=getattr(logging, LOG_LEVEL.upper(), logging.INFO),
)
logger = logging.getLogger(__name__)

STATE_WAIT_ADDRESS = 1
STATE_WAIT_LABEL = 2

db = Database(DB_PATH)
tron_monitor = TronMonitor(
    api_key=TRONSCAN_API_KEY,
    poll_interval=POLL_INTERVAL,
    proxy=PROXY_URL,
)

MAIN_KEYBOARD = ReplyKeyboardMarkup(
    [
        ["📥 添加监听", "📋 监听列表", "🗑 删除监听"],
        ["⚡ 能量租赁", "🌟 电报会员", "💰 实时U价"],
        ["👤 查用户ID", "📢 查频道ID", "👥 查群组ID"],
    ],
    resize_keyboard=True,
)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🔗 <b>WalletMonitor - 链上钱包监控机器人</b>\n\n"
        "支持监控 TRX/TRC20 链上交易，发现新转账后实时推送通知。\n\n"
        "请选择下方菜单操作。",
        parse_mode=ParseMode.HTML,
        reply_markup=MAIN_KEYBOARD,
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📖 <b>使用帮助</b>\n\n"
        "📥 <b>添加监听</b> - 添加 TRON 钱包地址\n"
        "📋 <b>监听列表</b> - 查看当前监听地址\n"
        "🗑 <b>删除监听</b> - 删除已添加地址\n"
        "👤 <b>查用户ID</b> - 查看你的 Telegram 用户 ID\n"
        "📢 <b>查频道ID</b> - 选择频道并查看 ID\n"
        "👥 <b>查群组ID</b> - 选择群组并查看 ID\n\n"
        "监控到新交易后会实时发送通知。",
        parse_mode=ParseMode.HTML,
        reply_markup=MAIN_KEYBOARD,
    )


async def add_monitor_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📥 <b>添加监听地址</b>\n\n"
        "请输入要监听的 TRON 钱包地址。\n\n"
        "输入 /cancel 取消操作。",
        parse_mode=ParseMode.HTML,
    )
    return STATE_WAIT_ADDRESS


async def add_monitor_address(update: Update, context: ContextTypes.DEFAULT_TYPE):
    address = update.message.text.strip()
    if not TronMonitor.is_valid_tron_address(address):
        await update.message.reply_text(
            "❌ 地址格式无效，请输入正确的 TRON 地址。\n"
            "TRON 地址通常以 T 开头，长度为 34 个字符。",
            reply_markup=MAIN_KEYBOARD,
        )
        return STATE_WAIT_ADDRESS

    chat_id = update.effective_chat.id
    for wallet in db.get_wallets(chat_id):
        if wallet["address"].upper() == address.upper():
            await update.message.reply_text("⚠️ 该地址已经在监听列表中。", reply_markup=MAIN_KEYBOARD)
            return ConversationHandler.END

    context.user_data["pending_address"] = address
    await update.message.reply_text(
        f"✅ 地址已确认：\n<code>{address}</code>\n\n请输入备注名称：",
        parse_mode=ParseMode.HTML,
    )
    return STATE_WAIT_LABEL


async def add_monitor_label(update: Update, context: ContextTypes.DEFAULT_TYPE):
    label = update.message.text.strip()
    if len(label) > 50:
        await update.message.reply_text("❌ 备注名称过长，请控制在 50 个字符以内。")
        return STATE_WAIT_LABEL

    address = context.user_data.get("pending_address", "")
    if not address:
        await update.message.reply_text("❌ 操作已过期，请重新添加。", reply_markup=MAIN_KEYBOARD)
        return ConversationHandler.END

    chat_id = update.effective_chat.id
    success = db.add_wallet(address, label, chat_id)
    if success:
        db.update_last_tx_timestamp(address, int(time.time() * 1000), chat_id)
        await update.message.reply_text(
            f"✅ <b>监听添加成功</b>\n\n备注: <b>{label}</b>\n地址: <code>{address}</code>",
            parse_mode=ParseMode.HTML,
            reply_markup=MAIN_KEYBOARD,
        )
    else:
        await update.message.reply_text("❌ 添加失败，该地址可能已经存在。", reply_markup=MAIN_KEYBOARD)

    context.user_data.pop("pending_address", None)
    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.pop("pending_address", None)
    await update.message.reply_text("已取消。", reply_markup=MAIN_KEYBOARD)
    return ConversationHandler.END


async def list_monitors(update: Update, context: ContextTypes.DEFAULT_TYPE):
    wallets = db.get_wallets(update.effective_chat.id)
    if not wallets:
        await update.message.reply_text("📋 监听列表为空。", reply_markup=MAIN_KEYBOARD)
        return

    text = "📋 <b>监听列表</b>\n\n"
    for index, wallet in enumerate(wallets, 1):
        text += f"<b>{index}.</b> {wallet['label']}\n<code>{wallet['address']}</code>\n\n"
    await update.message.reply_text(text, parse_mode=ParseMode.HTML, reply_markup=MAIN_KEYBOARD)


async def delete_monitor(update: Update, context: ContextTypes.DEFAULT_TYPE):
    wallets = db.get_wallets(update.effective_chat.id)
    if not wallets:
        await update.message.reply_text("📋 监听列表为空，没有可删除的地址。", reply_markup=MAIN_KEYBOARD)
        return

    keyboard = []
    for wallet in wallets:
        address = wallet["address"]
        short_addr = f"{address[:8]}...{address[-10:]}"
        keyboard.append(
            [InlineKeyboardButton(f"🗑 {wallet['label']} | {short_addr}", callback_data=f"del:{address}")]
        )
    keyboard.append([InlineKeyboardButton("关闭", callback_data="del:cancel")])
    await update.message.reply_text(
        "请选择要删除的监听地址：",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def delete_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    if not data.startswith("del:"):
        return

    address = data[4:]
    if address == "cancel":
        await query.message.edit_text("已关闭删除面板。")
        return

    chat_id = query.message.chat_id
    wallet = db.get_wallet_by_address(address, chat_id)
    success = db.remove_wallet(address, chat_id)
    if success:
        label = wallet["label"] if wallet else "未知"
        await query.message.edit_text(
            f"✅ 已删除监听\n\n备注: {label}\n地址: <code>{address}</code>",
            parse_mode=ParseMode.HTML,
        )
    else:
        await query.message.edit_text("❌ 删除失败，地址可能已被移除。")


async def get_user_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    await update.message.reply_text(
        f"👤 <b>用户信息</b>\n\n用户ID: <code>{user.id}</code>\n用户名: @{user.username or '无'}\n名称: {user.full_name}",
        parse_mode=ParseMode.HTML,
        reply_markup=MAIN_KEYBOARD,
    )


async def get_channel_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = ReplyKeyboardMarkup(
        [[KeyboardButton("📢 选择频道", request_chat=KeyboardButtonRequestChat(request_id=1, chat_is_channel=True))], [KeyboardButton("取消")]],
        resize_keyboard=True,
        one_time_keyboard=True,
    )
    await update.message.reply_text("请选择要查询的频道。", reply_markup=keyboard)


async def get_group_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = ReplyKeyboardMarkup(
        [[KeyboardButton("👥 选择群组", request_chat=KeyboardButtonRequestChat(request_id=2, chat_is_channel=False))], [KeyboardButton("取消")]],
        resize_keyboard=True,
        one_time_keyboard=True,
    )
    await update.message.reply_text("请选择要查询的群组。", reply_markup=keyboard)


async def handle_chat_shared(update: Update, context: ContextTypes.DEFAULT_TYPE):
    shared = update.message.chat_shared
    label = "频道" if shared.request_id == 1 else "群组"
    title = f"\n名称: {shared.title}" if shared.title else ""
    await update.message.reply_text(
        f"<b>{label} ID</b>\n\n{label}ID: <code>{shared.chat_id}</code>{title}",
        parse_mode=ParseMode.HTML,
        reply_markup=MAIN_KEYBOARD,
    )


async def handle_cancel_keyboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("已取消。", reply_markup=MAIN_KEYBOARD)


async def energy_rental(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not ENERGY_TRX_ADDRESS:
        await update.message.reply_text("❌ 未配置 ENERGY_TRX_ADDRESS。", reply_markup=MAIN_KEYBOARD)
        return
    await update.message.reply_text(
        f"⚡ <b>能量租赁</b>\n\n请向以下地址转入 TRX：\n<code>{ENERGY_TRX_ADDRESS}</code>",
        parse_mode=ParseMode.HTML,
        reply_markup=MAIN_KEYBOARD,
    )


async def tg_premium(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not TG_PREMIUM_URL:
        await update.message.reply_text("❌ 未配置 TG_PREMIUM_URL。", reply_markup=MAIN_KEYBOARD)
        return
    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🌟 前往开通", url=TG_PREMIUM_URL)]])
    await update.message.reply_text("🌟 <b>电报会员</b>", parse_mode=ParseMode.HTML, reply_markup=keyboard)


async def usdt_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("💰 正在查询实时 USDT/CNY 汇率，请稍候...")
    try:
        import httpx

        url = "https://p2p.binance.com/bapi/c2c/v2/friendly/c2c/adv/search"
        headers = {"User-Agent": "Mozilla/5.0"}
        results = {}
        async with httpx.AsyncClient(timeout=15, headers=headers) as client:
            for trade_type, key in [("SELL", "buy"), ("BUY", "sell")]:
                resp = await client.post(
                    url,
                    json={
                        "fiat": "CNY",
                        "page": 1,
                        "rows": 10,
                        "tradeType": trade_type,
                        "asset": "USDT",
                        "countries": [],
                        "proMerchantAds": False,
                        "publisherType": None,
                        "payTypes": [],
                    },
                )
                results[key] = resp.json().get("data", [])

        text = "[ 实时报价 - USDT/CNY ]\n\n"
        sell_orders = results.get("buy", [])
        buy_orders = results.get("sell", [])
        if sell_orders:
            text += "<b>买入U（商户出售）</b>\n"
            for order in sell_orders[:5]:
                text += f"<b>{order.get('adv', {}).get('price', '--')}</b>    <code>{order.get('advertiser', {}).get('nickName', '未知')}</code>\n"
        if buy_orders:
            text += "\n<b>卖出U（商户收购）</b>\n"
            for order in buy_orders[:5]:
                text += f"<b>{order.get('adv', {}).get('price', '--')}</b>    <code>{order.get('advertiser', {}).get('nickName', '未知')}</code>\n"
        text += "\n数据来源: Binance C2C"
        await update.message.reply_text(text, parse_mode=ParseMode.HTML, reply_markup=MAIN_KEYBOARD)
    except Exception as exc:
        logger.error("USDT price query failed: %s", exc)
        await update.message.reply_text("❌ 查询失败，请稍后再试。", reply_markup=MAIN_KEYBOARD)


_rate_cache: dict = {"rate": None, "ts": 0}


async def _get_usdt_rate() -> float | None:
    now = time.time()
    if _rate_cache["rate"] and now - _rate_cache["ts"] < 60:
        return _rate_cache["rate"]
    try:
        import httpx

        async with httpx.AsyncClient(timeout=10, headers={"User-Agent": "Mozilla/5.0"}) as client:
            resp = await client.post(
                "https://p2p.binance.com/bapi/c2c/v2/friendly/c2c/adv/search",
                json={
                    "fiat": "CNY",
                    "page": 1,
                    "rows": 5,
                    "tradeType": "SELL",
                    "asset": "USDT",
                    "countries": [],
                    "proMerchantAds": False,
                    "publisherType": None,
                    "payTypes": [],
                },
            )
        items = resp.json().get("data", [])
        prices = [float(item["adv"]["price"]) for item in items[:3] if item.get("adv", {}).get("price")]
        if not prices:
            return None
        rate = round(sum(prices) / len(prices), 4)
        _rate_cache.update({"rate": rate, "ts": now})
        return rate
    except Exception:
        return None


async def handle_usdt_calc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    import re

    text = update.message.text.strip()
    match = re.match(r"^([\d]+\.?[\d]*)\s*[uU]$", text)
    if not match:
        return
    amount = float(match.group(1))
    rate = await _get_usdt_rate()
    if rate is None:
        await update.message.reply_text("❌ 获取汇率失败，请稍后再试。")
        return
    await update.message.reply_text(
        f"💱 <b>{amount:g} USDT</b> ≈ <b>{amount * rate:,.2f} CNY</b>\n"
        f"<i>当前汇率: 1 USDT = {rate} CNY</i>",
        parse_mode=ParseMode.HTML,
    )


async def monitor_task(application: Application):
    logger.info("Monitor task started")
    while True:
        try:
            wallets = db.get_all_wallets()
            for wallet in wallets:
                address = wallet["address"]
                label = wallet["label"]
                chat_id = wallet["chat_id"]
                last_ts = wallet["last_tx_timestamp"]

                if last_ts == 0:
                    db.update_last_tx_timestamp(address, int(time.time() * 1000), chat_id)
                    continue

                min_ts = last_ts + 1
                trc20_txs = await tron_monitor.get_trc20_transactions(address, min_timestamp=min_ts)
                trx_txs = await tron_monitor.get_trx_transactions(address, min_timestamp=min_ts)
                new_max_ts = last_ts

                for tx in reversed(trc20_txs):
                    tx_info = tron_monitor.parse_trc20_transaction(tx, address)
                    if not tx_info or tx_info["block_timestamp"] <= last_ts:
                        continue
                    new_max_ts = max(new_max_ts, tx_info["block_timestamp"])
                    await send_tx_notification(application, chat_id, tx_info, label)

                for tx in reversed(trx_txs):
                    tx_info = tron_monitor.parse_trx_transaction(tx, address)
                    if not tx_info or tx_info["block_timestamp"] <= last_ts:
                        continue
                    new_max_ts = max(new_max_ts, tx_info["block_timestamp"])
                    await send_tx_notification(application, chat_id, tx_info, label)

                if new_max_ts > last_ts:
                    db.update_last_tx_timestamp(address, new_max_ts, chat_id)
                await asyncio.sleep(1)
        except Exception as exc:
            logger.error("Monitor task error: %s", exc, exc_info=True)

        await asyncio.sleep(POLL_INTERVAL)


async def send_tx_notification(application: Application, chat_id: int, tx_info: dict, label: str):
    message = tron_monitor.format_notification(tx_info, label)
    tx_url = f"https://tronscan.org/#/transaction/{tx_info['tx_id']}"
    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🔗 查看交易详情", url=tx_url)]])
    targets = [chat_id]
    if NOTIFY_CHAT_ID:
        try:
            extra_chat_id = int(NOTIFY_CHAT_ID)
            if extra_chat_id not in targets:
                targets.append(extra_chat_id)
        except ValueError:
            logger.warning("Invalid NOTIFY_CHAT_ID: %s", NOTIFY_CHAT_ID)

    for target in targets:
        try:
            await application.bot.send_message(
                chat_id=target,
                text=message,
                parse_mode=ParseMode.HTML,
                reply_markup=keyboard,
                disable_web_page_preview=True,
            )
        except Exception as exc:
            logger.error("Failed to send notification to %s: %s", target, exc)


async def post_init(application: Application):
    db.reset_all_timestamps(int(time.time() * 1000))
    asyncio.create_task(monitor_task(application))
    logger.info("WalletMonitor Bot started")


def _make_fallback(handler_func):
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        context.user_data.pop("pending_address", None)
        await handler_func(update, context)
        return ConversationHandler.END

    return wrapper


def main():
    if not BOT_TOKEN:
        logger.error("BOT_TOKEN is not configured")
        sys.exit(1)
    if not TRONSCAN_API_KEY:
        logger.warning("TRONSCAN_API_KEY is not configured; API rate limits may apply")

    builder = Application.builder().token(BOT_TOKEN).post_init(post_init)
    if PROXY_URL:
        request = HTTPXRequest(
            proxy=PROXY_URL,
            connect_timeout=30.0,
            read_timeout=30.0,
            write_timeout=30.0,
        )
        builder = builder.request(request)
    application = builder.build()

    menu_fallback_handlers = [
        MessageHandler(filters.Regex(r"^📥 添加监听$"), add_monitor_start),
        MessageHandler(filters.Regex(r"^📋 监听列表$"), _make_fallback(list_monitors)),
        MessageHandler(filters.Regex(r"^🗑 删除监听$"), _make_fallback(delete_monitor)),
        MessageHandler(filters.Regex(r"^👤 查用户ID$"), _make_fallback(get_user_id)),
        MessageHandler(filters.Regex(r"^📢 查频道ID$"), _make_fallback(get_channel_id)),
        MessageHandler(filters.Regex(r"^👥 查群组ID$"), _make_fallback(get_group_id)),
        MessageHandler(filters.Regex(r"^⚡ 能量租赁$"), _make_fallback(energy_rental)),
        MessageHandler(filters.Regex(r"^🌟 电报会员$"), _make_fallback(tg_premium)),
        MessageHandler(filters.Regex(r"^💰 实时U价$"), _make_fallback(usdt_price)),
    ]

    conv_handler = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex(r"^📥 添加监听$"), add_monitor_start)],
        states={
            STATE_WAIT_ADDRESS: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_monitor_address)],
            STATE_WAIT_LABEL: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_monitor_label)],
        },
        fallbacks=[CommandHandler("cancel", cancel), *menu_fallback_handlers],
    )

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(conv_handler)
    application.add_handler(MessageHandler(filters.Regex(r"^📋 监听列表$"), list_monitors))
    application.add_handler(MessageHandler(filters.Regex(r"^🗑 删除监听$"), delete_monitor))
    application.add_handler(MessageHandler(filters.Regex(r"^👤 查用户ID$"), get_user_id))
    application.add_handler(MessageHandler(filters.Regex(r"^📢 查频道ID$"), get_channel_id))
    application.add_handler(MessageHandler(filters.Regex(r"^👥 查群组ID$"), get_group_id))
    application.add_handler(MessageHandler(filters.Regex(r"^⚡ 能量租赁$"), energy_rental))
    application.add_handler(MessageHandler(filters.Regex(r"^🌟 电报会员$"), tg_premium))
    application.add_handler(MessageHandler(filters.Regex(r"^💰 实时U价$"), usdt_price))
    application.add_handler(CallbackQueryHandler(delete_callback, pattern=r"^del:"))
    application.add_handler(MessageHandler(filters.StatusUpdate.CHAT_SHARED, handle_chat_shared))
    application.add_handler(MessageHandler(filters.Regex(r"^取消$"), handle_cancel_keyboard))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_usdt_calc))

    async def _handle_network_error(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
        if isinstance(context.error, (NetworkError, TimedOut)):
            logger.debug("Network fluctuation: %s", context.error)
        else:
            raise context.error

    application.add_error_handler(_handle_network_error)
    application.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
