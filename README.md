# 🔗 WalletMonitor - 链上钱包交易监控机器人

<div align="center">

![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)
![Telegram Bot API](https://img.shields.io/badge/Telegram%20Bot%20API-v21-blue.svg)
![License](https://img.shields.io/badge/License-MIT-green.svg)
![TRON](https://img.shields.io/badge/TRON-TRC20-red.svg)

**一款基于 Telegram Bot 的 TRX (TRC20) 链上钱包交易实时监控工具**

</div>

---

## 📖 功能特性

| 功能 | 说明 |
|------|------|
| 📡 **添加监听** | 添加 TRX (TRC20) 钱包地址，支持自定义备注 |
| 📋 **监听列表** | 查看当前所有已监控的钱包地址 |
| 🗑 **删除监听** | 一键选择并删除已监控的地址 |
| 👤 **查用户ID** | 快速获取你的 Telegram 用户 ID |
| 📢 **查频道ID** | 转发频道消息即可获取频道 ID |
| 👥 **查群组ID** | 在群组中发送即可获取群组 ID |
| 🔎 **域名检测** | 添加域名持续检测，可注册时自动提醒添加者 |
| 🟢🔴 **实时通知** | 收到转账绿色通知，支出红色通知 |
| 🔗 **交易详情** | 通知内附跳转 TronScan 查看交易详情按钮 |
| 💰 **多币种支持** | 支持 USDT、USDC、TRX 等 TRC20 代币监控 |

## 📸 效果预览

### 交易通知示例

```
🟢新交易  #多钱888888
交易金额: +1,059.00 USDT
交易币种: #USDT
交易类型: #转入

出账地址:
TMvZZSWN4TZ4moeRNYWyDJhRyAAAAAAAAA

入账地址: [监听地址]↓
TPbsMyr7KsvdidADDC8k2345552223dddd

交易时间: 2026-03-22 22:35:18
通知时间: 2026-03-22 22:35:19
交易哈希:
4fb59c5d26db6cacaec4da1271d4b2447f15fb10de8caaaaddddadddd

[🔗 查看交易详情]
```
<img width="584" height="547" alt="image" src="https://github.com/user-attachments/assets/db988be5-4b16-43ff-a292-1725a09a0708" />

<img width="584" height="213" alt="image" src="https://github.com/user-attachments/assets/f853ce18-27c6-44e4-8a73-e17100e4a4e9" />


## 🛠 环境要求

- **Python** >= 3.10
- **Telegram Bot Token** (通过 [@BotFather](https://t.me/BotFather) 创建)
- **TronScan API Key** (在 [TronScan](https://tronscan.org/) 获取)

## 🚀 快速开始

### 1. 克隆项目

```bash
git clone https://github.com/your-username/WalletMonitor.git
cd WalletMonitor
```

### 2. 安装依赖

```bash
# 推荐使用虚拟环境
python3 -m venv venv
source venv/bin/activate  # macOS/Linux
# venv\Scripts\activate   # Windows

pip install -r requirements.txt
```

### 3. 配置环境变量

```bash
cp .env.example .env
```

编辑 `.env` 文件，填写以下配置：

```env
# Telegram Bot Token (必填)
BOT_TOKEN=your_telegram_bot_token_here

# TronScan API Key (必填)
TRONSCAN_API_KEY=your_tronscan_api_key_here

# 监控轮询间隔，单位：秒 (默认10秒)
POLL_INTERVAL=10

# 额外通知 Chat ID (可选，填写后交易通知会额外发送到指定聊天)
NOTIFY_CHAT_ID=

# 数据库文件路径 (默认 wallets.db)
DB_PATH=wallets.db

# 日志级别 (DEBUG, INFO, WARNING, ERROR)
LOG_LEVEL=INFO

# Spaceship 域名检测 API
SPACESHIP_API_KEY=your_spaceship_api_key_here
SPACESHIP_API_SECRET=your_spaceship_api_secret_here
SPACESHIP_API_BASE=https://spaceship.dev/api/v1
DOMAIN_CHECK_INTERVAL=300
DOMAIN_CHECK_START=01:40
DOMAIN_CHECK_END=03:30
DOMAIN_NOTIFY_COUNT=5
DOMAIN_NOTIFY_INTERVAL=10
```

### 4. 启动机器人

```bash
python bot.py
```

## ⚙️ 配置说明

| 配置项 | 必填 | 默认值 | 说明 |
|--------|------|--------|------|
| `BOT_TOKEN` | ✅ | - | Telegram Bot Token，通过 @BotFather 获取 |
| `TRONSCAN_API_KEY` | ✅ | - | TronScan API Key，[注册获取](https://tronscan.org/) |
| `POLL_INTERVAL` | ❌ | `10` | 链上交易轮询间隔（秒） |
| `NOTIFY_CHAT_ID` | ❌ | - | 额外通知接收的 Chat ID |
| `DB_PATH` | ❌ | `wallets.db` | SQLite 数据库文件路径 |
| `LOG_LEVEL` | ❌ | `INFO` | 日志级别 |
| `SPACESHIP_API_KEY` | ❌ | - | Spaceship API Key，用于域名可注册检测 |
| `SPACESHIP_API_SECRET` | ❌ | - | Spaceship API Secret，用于域名可注册检测 |
| `SPACESHIP_API_BASE` | ❌ | `https://spaceship.dev/api/v1` | Spaceship API 基础地址 |
| `DOMAIN_CHECK_INTERVAL` | ❌ | `300` | 域名后台检测间隔（秒） |
| `DOMAIN_CHECK_START` | ❌ | `01:40` | 每日域名检测开始时间 |
| `DOMAIN_CHECK_END` | ❌ | `03:30` | 每日域名检测结束时间 |
| `DOMAIN_NOTIFY_COUNT` | ❌ | `5` | 域名可注册提醒次数 |
| `DOMAIN_NOTIFY_INTERVAL` | ❌ | `10` | 域名可注册提醒间隔（秒） |

### 获取 Bot Token

1. 在 Telegram 中搜索 [@BotFather](https://t.me/BotFather)
2. 发送 `/newbot` 创建新机器人
3. 按提示设置名称和用户名
4. 获取 Bot Token 并填入 `.env`

### 获取 Spaceship API Key

1. 登录 [Spaceship](https://www.spaceship.com/)
2. 进入 API Manager
3. 生成 API Key 和 API Secret，并填入 `.env`

### 获取 TronScan API Key

1. 访问 [TronScan](https://tronscan.org/)
2. 注册并登录
3. 创建新项目获取 API Key
4. 填入 `.env` 的 `TRONSCAN_API_KEY`

## 📁 项目结构

```
WalletMonitor/
├── bot.py              # 主入口 - Telegram Bot 命令处理与调度
├── monitor.py          # 区块链监控模块 - TronScan API 交互与交易解析
├── database.py         # 数据库模块 - SQLite 地址存储管理
├── requirements.txt    # Python 依赖
├── .env.example        # 环境变量配置模板
├── .env                # 环境变量配置 (需自建)
└── README.md           # 项目文档
```

## 🤖 Bot 命令

| 命令/按钮 | 说明 |
|-----------|------|
| `/start` | 启动机器人，显示主菜单 |
| `/help` | 查看使用帮助 |
| `/cancel` | 取消当前操作 |
| 📡 添加监听 | 输入 TRX 地址 + 备注名称 |
| 📋 监听列表 | 查看所有已监控地址 |
| 🗑 删除监听 | 选择并删除监控地址 |
| 👤 查用户ID | 获取你的 Telegram 用户 ID |
| 📢 查频道ID | 转发频道消息获取频道 ID |
| 👥 查群组ID | 在群组中使用获取群组 ID |
| 🔎 域名检测 | 输入多个域名，持续检测并在可注册时提醒 |

## 🔍 工作原理

```
┌──────────────┐    轮询     ┌──────────────┐
│  TronScan    │◄───────────│  Monitor     │
│  API         │───────────►│  (monitor.py)│
└──────────────┘   交易数据   └──────┬───────┘
                                     │ 新交易
                                     ▼
┌──────────────┐            ┌──────────────┐
│  SQLite DB   │◄──────────►│  Bot         │
│  (database)  │  地址管理   │  (bot.py)    │
└──────────────┘            └──────┬───────┘
                                     │ 通知
                                     ▼
                             ┌──────────────┐
                             │  Telegram    │
                             │  用户/群组    │
                             └──────────────┘
```

1. **Bot 启动** → 加载所有监听地址
2. **定时轮询** → 通过 TronScan API 查询每个地址的新交易
3. **交易解析** → 解析 TRC20/TRX 交易数据，判断转入/转出
4. **推送通知** → 格式化消息通过 Telegram Bot 发送给用户

## 🐳 Docker 部署（可选）

```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
CMD ["python", "bot.py"]
```

```bash
docker build -t wallet-monitor .
docker run -d --name wallet-monitor --env-file .env wallet-monitor
```

## ❓ 常见问题

**Q: 为什么收不到交易通知？**
- 检查 `BOT_TOKEN` 和 `TRONSCAN_API_KEY` 是否正确配置
- 确认机器人已启动且无报错
- 检查是否已正确添加监听地址
- 新添加的地址只会监控添加之后的新交易

**Q: 支持哪些代币？**
- 支持所有 TRC20 代币（USDT、USDC 等）
- 支持 TRX 原生转账
- 自动识别代币名称和精度

**Q: 轮询间隔设置多少合适？**
- 默认 10 秒，适合大多数场景
- 最低建议 5 秒，避免 API 限流
- 监听地址较多时建议适当增大间隔

**Q: 如何在群组中使用？**
- 将机器人添加到群组中
- 在群组内使用菜单按钮操作
- 交易通知会发送到添加监听时所在的聊天

## 📄 License

MIT License - 详见 [LICENSE](LICENSE) 文件

## ⭐ Star History

如果这个项目对你有帮助，欢迎给个 Star ⭐
