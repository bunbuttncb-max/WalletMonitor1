"""TronScan API client and transaction parser for TRON wallet monitoring."""

from __future__ import annotations

import asyncio
import hashlib
import logging
import ssl
from datetime import datetime, timedelta, timezone

import aiohttp
import base58
import certifi

logger = logging.getLogger(__name__)

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

    async def close(self) -> None:
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
            timeout = aiohttp.ClientTimeout(total=30)
            async with session.get(url, params=params, proxy=self.proxy, timeout=timeout) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data.get("token_transfers", [])
                text = await resp.text()
                logger.error("TronScan API error: %s - %s", resp.status, text)
        except asyncio.TimeoutError:
            logger.error("TronScan API timeout: %s", address)
        except Exception as exc:
            logger.error("TronScan API exception: %s", exc)
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
            timeout = aiohttp.ClientTimeout(total=30)
            async with session.get(url, params=params, proxy=self.proxy, timeout=timeout) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data.get("data", [])
                text = await resp.text()
                logger.error("TronScan API error (TRX): %s - %s", resp.status, text)
        except asyncio.TimeoutError:
            logger.error("TronScan API timeout (TRX): %s", address)
        except Exception as exc:
            logger.error("TronScan API exception (TRX): %s", exc)
        return []

    def parse_trc20_transaction(self, tx: dict, monitored_address: str) -> dict | None:
        try:
            token_info = tx.get("token_info") or tx.get("tokenInfo") or {}
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
            value = value_raw / (10**decimals)
            tx_id = tx.get("transaction_id") or tx.get("hash", "")
            block_timestamp = (
                tx.get("block_timestamp") or tx.get("block_ts") or tx.get("timestamp") or 0
            )

            return self._build_tx_info(
                monitored_address=monitored_address,
                from_addr=from_addr,
                to_addr=to_addr,
                value=value,
                symbol=symbol,
                tx_id=tx_id,
                block_timestamp=block_timestamp,
            )
        except Exception as exc:
            logger.error("Failed to parse TRC20 transaction: %s", exc)
            return None

    def parse_trx_transaction(self, tx: dict, monitored_address: str) -> dict | None:
        try:
            if "transactionHash" in tx or "transferFromAddress" in tx:
                contract_ret = tx.get("contractRet") or tx.get("contract_ret")
                if contract_ret and contract_ret != "SUCCESS":
                    return None
                return self._build_tx_info(
                    monitored_address=monitored_address,
                    from_addr=tx.get("transferFromAddress", ""),
                    to_addr=tx.get("transferToAddress", ""),
                    value=int(tx.get("amount", 0)) / 1_000_000,
                    symbol="TRX",
                    tx_id=tx.get("transactionHash", ""),
                    block_timestamp=tx.get("timestamp", 0),
                )

            raw_data = tx.get("raw_data", {})
            contract_list = raw_data.get("contract", [])
            if not contract_list:
                return None

            contract = contract_list[0]
            if contract.get("type") != "TransferContract":
                return None

            value = contract.get("parameter", {}).get("value", {})
            from_addr = self._hex_to_base58(value.get("owner_address", ""))
            to_addr = self._hex_to_base58(value.get("to_address", ""))
            if not from_addr or not to_addr:
                return None

            return self._build_tx_info(
                monitored_address=monitored_address,
                from_addr=from_addr,
                to_addr=to_addr,
                value=int(value.get("amount", 0)) / 1_000_000,
                symbol="TRX",
                tx_id=tx.get("txID", ""),
                block_timestamp=tx.get("block_timestamp", 0),
            )
        except Exception as exc:
            logger.error("Failed to parse TRX transaction: %s", exc)
            return None

    def _build_tx_info(
        self,
        monitored_address: str,
        from_addr: str,
        to_addr: str,
        value: float,
        symbol: str,
        tx_id: str,
        block_timestamp: int,
    ) -> dict | None:
        if value == 0:
            return None

        monitored_upper = monitored_address.upper()
        is_incoming = to_addr.upper() == monitored_upper
        is_outgoing = from_addr.upper() == monitored_upper
        if not is_incoming and not is_outgoing:
            return None

        tx_time = datetime.fromtimestamp(block_timestamp / 1000, tz=CST).strftime(
            "%Y-%m-%d %H:%M:%S"
        )
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

    @staticmethod
    def _hex_to_base58(hex_addr: str) -> str | None:
        try:
            if not hex_addr:
                return None
            if hex_addr.startswith("0x"):
                hex_addr = "41" + hex_addr[2:]
            elif not hex_addr.startswith("41"):
                return hex_addr

            addr_bytes = bytes.fromhex(hex_addr)
            checksum = hashlib.sha256(hashlib.sha256(addr_bytes).digest()).digest()[:4]
            return base58.b58encode(addr_bytes + checksum).decode()
        except Exception:
            return None

    @staticmethod
    def is_valid_tron_address(address: str) -> bool:
        if not address or not isinstance(address, str):
            return False
        if not address.startswith("T") or len(address) != 34:
            return False
        try:
            decoded = base58.b58decode(address)
            if len(decoded) != 25:
                return False
            payload, checksum = decoded[:-4], decoded[-4:]
            expected = hashlib.sha256(hashlib.sha256(payload).digest()).digest()[:4]
            return checksum == expected
        except Exception:
            return False

    def format_notification(self, tx_info: dict, label: str) -> str:
        import html

        label = html.escape(label)
        from_addr = html.escape(tx_info["from_addr"])
        to_addr = html.escape(tx_info["to_addr"])
        symbol = html.escape(tx_info["symbol"])
        tx_type_tag = "转入" if tx_info["is_incoming"] else "转出"
        emoji = "🟢" if tx_info["is_incoming"] else "🔴"
        from_label = " [监听地址]→" if not tx_info["is_incoming"] else ""
        to_label = " [监听地址]→" if tx_info["is_incoming"] else ""
        value = tx_info["value"]
        value_str = f"{value:,.2f}" if value >= 0.01 else str(value)

        return (
            f"{emoji}<b>新交易</b> #{label}\n"
            f"<b>交易金额:</b> <b>{tx_info['sign']}{value_str} {symbol}</b>\n"
            f"<b>交易币种:</b> #{symbol}\n"
            f"<b>交易类型:</b> #{tx_type_tag}\n\n"
            f"<b>出账地址:</b>{from_label}\n<code>{from_addr}</code>\n\n"
            f"<b>入账地址:</b>{to_label}\n<code>{to_addr}</code>\n\n"
            f"<b>交易时间:</b> {tx_info['tx_time']}\n"
            f"<b>通知时间:</b> {tx_info['notify_time']}\n"
            f"<b>交易哈希:</b>\n<code>{html.escape(tx_info['tx_id'])}</code>"
        )
