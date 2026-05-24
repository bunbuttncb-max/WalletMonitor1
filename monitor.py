"""
区块链监控模块 - 监控 TRX (TRC20) 链上交易
通过 TronScan API 轮询监听钱包地址的 TRC20/TRX 转账
"""

from __future__ import annotations

import asyncio
import logging
import ssl
from datetime import datetime, timezone, timedelta

import aiohttp
import certifi

logger = logging.getLogger(__name__)

# TRC20 USDT 合约地址
USDT_CONTRACT = "TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t"

# 常见 TRC20 代币合约映射
TRC20_TOKENS = {
    "TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t": {"symbol": "USDT", "decimals": 6},
    "TEkxiTehnzSmSe2XqrBj4w32RUN966rdz8": {"symbol": "USDC", "decimals": 6},
    "TN3W4H6rK2ce4vX9YnFQHwKENnHjoxb3m9": {"symbol": "BTC", "decimals": 8},
    "THb4CqiFdwNHsWsQCs4JhzwjMWys4aqCbF": {"symbol": "ETH", "decimals": 18},
    "TNUC9Qb1rRpS5CbWLmNMxXBjyFoydXjWFR": {"symbol": "WTRX", "decimals": 6},
}

# 中国时区 UTC+8
CST = timezone(timedelta(hours=8))


class TronMonitor:
    def __init__(self, api_key: str, poll_interval: int = 10, proxy: str = ""):
        self.api_key = api_key
        self.poll_interval = poll_interval
        self.base_url = "https://apilist.tronscanapi.com"
        self.proxy = proxy or None
        self._session: aiohttp.ClientSession | None = None
        self._ssl_ctx = ssl.create_default_context(cafile=certifi.where())

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            connector = aiohttp.TCPConnector(ssl=self._ssl_ctx)
            self._session = aiohttp.ClientSession(
                connector=connector,
                headers={"TRON-PRO-API-KEY": self.api_key},
            )
        return self._session

    async def close(self):
        if self._session and not self._session.closed:
            await self._session.close()

    async def get_trc20_transactions(
        self, address: str, min_timestamp: int = 0, limit: int = 50
    ) -> list[dict]:
        session = await self._get_session()
        url = f"{self.base_url}/api/token_trc20/transfers"
        params = {
            "start": 0,
            "limit": limit,
            "relatedAddress": address,
            "start_timestamp": min_timestamp,
            "end_timestamp": int(datetime.now(tz=timezone.utc).timestamp() * 1000),
            "confirm": 0,
            "filterTokenValue": 0,
        }

        try:
            async with session.get(url, params=params, proxy=self.proxy, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data.get("token_transfers", [])
                text = await resp.text()
                logger.error(f"TronScan API 错误: {resp.status} - {text}")
                return []
        except asyncio.TimeoutError:
            logger.error(f"TronScan API 超时: {address}")
            return []
        except Exception as e:
            logger.error(f"TronScan API 异常: {e}")
            return []

    async def get_trx_transactions(
        self, address: str, min_timestamp: int = 0, limit: int = 50
    ) -> list[dict]:
        session = await self._get_session()
        url = f"{self.base_url}/api/transfer"
        params = {
            "start": 0,
            "limit": limit,
            "sort": "-timestamp",
            "count": "true",
            "address": address,
            "direction": "all",
            "start_timestamp": min_timestamp,
            "end_timestamp": int(datetime.now(tz=timezone.utc).timestamp() * 1000),
            "confirm": 0,
            "token": "_",
            "filterTokenValue": 0,
        }

        try:
            async with session.get(url, params=params, proxy=self.proxy, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data.get("data", [])
                text = await resp.text()
                logger.error(f"TronScan API 错误 (TRX): {resp.status} - {text}")
                return []
        except asyncio.TimeoutError:
            logger.error(f"TronScan API 超时 (TRX): {address}")
            return []
        except Exception as e:
            logger.error(f"TronScan API 异常 (TRX): {e}")
            return []

    def parse_trc20_transaction(self, tx: dict, monitored_address: str) -> dict | None:
        try:
            token_info = tx.get("token_info", {})
            if not token_info:
                token_info = tx.get("tokenInfo", {})

            symbol = (
                token_info.get("symbol")
                or token_info.get("tokenAbbr")
                or token_info.get("tokenName")
                or "UNKNOWN"
            )
            decimals = int(
                token_info.get("decimals")
                or token_info.get("tokenDecimal")
                or tx.get("decimals")
                or 6
            )

            from_addr = tx.get("from") or tx.get("from_address", "")
            to_addr = tx.get("to") or tx.get("to_address", "")
            value_raw = int(tx.get("value") or tx.get("quant") or tx.get("amount") or "0")
            value = value_raw / (10 ** decimals)
            tx_id = tx.get("transaction_id") or tx.get("hash", "")
            block_timestamp = tx.get("block_timestamp") or tx.get("block_ts") or tx.get("timestamp") or 0

            monitored_upper = monitored_address.upper()
            is_incoming = to_addr.upper() == monitored_upper
            is_outgoing = from_addr.upper() == monitored_upper

            if not is_incoming and not is_outgoing:
                return None

            tx_time = datetime.fromtimestamp(
                block_timestamp / 1000, tz=CST
            ).strftime("%Y-%m-%d %H:%M:%S")

            notify_time = datetime.now(CST).strftime("%Y-%m-%d %H:%M:%S")

            return {
                "tx_id": tx_id,
                "from_addr": from_addr,
                "to_addr": to_addr,
                "value": value,
                "sign": "+" if is_incoming else "-",
                "symbol": symbol,
                "tx_type": "转入" if is_incoming else "转出",
                "is_incoming": is_incoming,
                "tx_time": tx_time,
                "notify_time": notify_time,
                "block_timestamp": block_timestamp,
            }
        except Exception as e:
            logger.error(f"解析 TRC20 交易失败: {e}")
            return None

    def parse_trx_transaction(self, tx: dict, monitored_address: str) -> dict | None:
        try:
            if "transactionHash" in tx or "transferFromAddress" in tx:
                from_addr = tx.get("transferFromAddress", "")
                to_addr = tx.get("transferToAddress", "")
                value = int(tx.get("amount", 0)) / 1_000_000
                tx_id = tx.get("transactionHash", "")
                block_timestamp = tx.get("timestamp", 0)
                contract_ret = tx.get("contractRet") or tx.get("contract_ret")
                if contract_ret and contract_ret != "SUCCESS":
                    return None

                monitored_upper = monitored_address.upper()
                is_incoming = to_addr.upper() == monitored_upper
                is_outgoing = from_addr.upper() == monitored_upper

                if not is_incoming and not is_outgoing:
                    return None
                if value == 0:
                    return None

                tx_time = datetime.fromtimestamp(
                    block_timestamp / 1000, tz=CST
                ).strftime("%Y-%m-%d %H:%M:%S")

                notify_time = datetime.now(CST).strftime("%Y-%m-%d %H:%M:%S")

                return {
                    "tx_id": tx_id,
                    "from_addr": from_addr,
                    "to_addr": to_addr,
                    "value": value,
                    "sign": "+" if is_incoming else "-",
                    "symbol": "TRX",
                    "tx_type": "转入" if is_incoming else "转出",
                    "is_incoming": is_incoming,
                    "tx_time": tx_time,
                    "notify_time": notify_time,
                    "block_timestamp": block_timestamp,
                }

            raw_data = tx.get("raw_data", {})
            contract_list = raw_data.get("contract", [])
            if not contract_list:
                return None

            contract = contract_list[0]
            contract_type = contract.get("type", "")
            if contract_type != "TransferContract":
                return None

            param = contract.get("parameter", {}).get("value", {})
            from_addr = self._hex_to_base58(param.get("owner_address", ""))
            to_addr = self._hex_to_base58(param.get("to_address", ""))
            amount_sun = param.get("amount", 0)

            if not from_addr or not to_addr:
                return None

            value = amount_sun / 1_000_000
            if value == 0:
                return None

            tx_id = tx.get("txID", "")
            block_timestamp = tx.get("block_timestamp", 0)
            monitored_upper = monitored_address.upper()
            is_incoming = to_addr.upper() == monitored_upper
            is_outgoing = from_addr.upper() == monitored_upper

            if not is_incoming and not is_outgoing:
                return None

            tx_time = datetime.fromtimestamp(
                block_timestamp / 1000, tz=CST
            ).strftime("%Y-%m-%d %H:%M:%S")

            notify_time = datetime.now(CST).strftime("%Y-%m-%d %H:%M:%S")

            return {
                "tx_id": tx_id,
                "from_addr": from_addr,
                "to_addr": to_addr,
                "value": value,
                "sign": "+" if is_incoming else "-",
                "symbol": "TRX",
                "tx_type": "转入" if is_incoming else "转出",
                "is_incoming": is_incoming,
                "tx_time": tx_time,
                "notify_time": notify_time,
                "block_timestamp": block_timestamp,
            }
        except Exception as e:
            logger.error(f"解析 TRX 交易失败: {e}")
            return None

    @staticmethod
    def _hex_to_base58(hex_addr: str) -> str | None:
        try:
            import base58
            import hashlib

            if not hex_addr:
                return None
            if hex_addr.startswith("0x"):
                hex_addr = "41" + hex_addr[2:]
            elif not hex_addr.startswith("41"):
                return hex_addr

            addr_bytes = bytes.fromhex(hex_addr)
            hash1 = hashlib.sha256(addr_bytes).digest()
            hash2 = hashlib.sha256(hash1).digest()
            checksum = hash2[:4]
            return base58.b58encode(addr_bytes + checksum).decode()
        except Exception:
            return None

    @staticmethod
    def is_valid_tron_address(address: str) -> bool:
        if not address or not isinstance(address, str):
            return False
        if not address.startswith("T"):
            return False
        if len(address) != 34:
            return False
        try:
            import base58
            decoded = base58.b58decode(address)
            return len(decoded) == 25
        except Exception:
            return False

    def format_notification(
        self, tx_info: dict, label: str, address_labels: dict | None = None
    ) -> str:
        emoji = "🟢" if tx_info["is_incoming"] else "🔴"
        tx_type_tag = "转入" if tx_info["is_incoming"] else "转出"

        address_labels = address_labels or {}
        from_label = ""
        to_label = ""
        if tx_info["is_incoming"]:
            to_label = " [监听地址]↓"
        else:
            from_label = " [监听地址]↓"

        if address_labels.get("from_addr"):
            from_label += f" [{address_labels['from_addr']}]"
        if address_labels.get("to_addr"):
            to_label += f" [{address_labels['to_addr']}]"

        value_str = f"{tx_info['value']:,.2f}" if tx_info['value'] >= 0.01 else f"{tx_info['value']}"

        message = (
            f"{emoji}<b>新交易</b>  #{label}\n"
            f"<b>交易金额:</b> <b>{tx_info['sign']}{value_str} {tx_info['symbol']}</b>\n"
            f"<b>交易币种:</b> #{tx_info['symbol']}\n"
            f"<b>交易类型:</b> #{tx_type_tag}\n\n"
            f"<b>出账地址:</b>{from_label}\n"
            f"<code>{tx_info['from_addr']}</code>\n\n"
            f"<b>入账地址:</b>{to_label}\n"
            f"<code>{tx_info['to_addr']}</code>\n\n"
            f"<b>交易时间:</b> {tx_info['tx_time']}\n"
            f"<b>通知时间:</b> {tx_info['notify_time']}\n"
            f"<b>交易哈希:</b>\n"
            f"<code>{tx_info['tx_id']}</code>"
        )
        return message
