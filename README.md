# WalletMonitor

Telegram bot for monitoring TRON wallet transfers. It stores watched addresses in SQLite, polls TronScan API for TRC20 and native TRX transfers, and sends Telegram notifications when new transfers are found.

## Features

- Add TRON wallet addresses with custom labels
- Manage users, watched wallets, and address remarks from a local web admin panel
- List and delete watched wallets
- Monitor TRC20 token transfers and native TRX transfers
- Show configured sender/receiver address remarks in transaction notifications
- Send Telegram notifications with a TronScan transaction link
- Query Telegram user, group, and channel IDs
- Optional USDT/CNY price lookup and quick `100u` conversion

## Requirements

- Python 3.10+
- Telegram Bot Token from [@BotFather](https://t.me/BotFather)
- TronScan API Key from [TronScan](https://tronscan.org/)

## Setup

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python bot.py
```

On Windows:

```powershell
python -m venv venv
.\venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
python bot.py
```

## Admin Panel

The admin panel lets you manage users, monitored wallet addresses, and sender/receiver address remarks.

```bash
python admin.py
```

Default local URL:

```text
http://127.0.0.1:8080/?token=change_this_admin_token
```

Set a strong `ADMIN_TOKEN` in `.env` before exposing the panel beyond localhost.

## Environment

```env
BOT_TOKEN=your_telegram_bot_token_here
TRONSCAN_API_KEY=your_tronscan_api_key_here
POLL_INTERVAL=10
NOTIFY_CHAT_ID=
DB_PATH=wallets.db
LOG_LEVEL=INFO
PROXY_URL=
ENERGY_TRX_ADDRESS=
TG_PREMIUM_URL=
ADMIN_HOST=127.0.0.1
ADMIN_PORT=8080
ADMIN_TOKEN=change_this_admin_token
```

## Project Files

- `bot.py` - Telegram bot commands and background monitor task
- `monitor.py` - TronScan API client and transaction parsing
- `database.py` - SQLite storage for users, watched wallets, and address remarks
- `admin.py` - local web admin panel
- `ADMIN.md` - admin panel usage notes
- `requirements.txt` - Python dependencies
- `.env.example` - configuration template

## Notes

Do not commit `.env`, database files, or real API keys. The repository intentionally includes only `.env.example` with placeholder values.
