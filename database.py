"""
数据库模块 - 管理监听钱包地址的存储
使用 SQLite 实现轻量级持久化存储
"""

import sqlite3
import threading
from typing import Optional


class Database:
    def __init__(self, db_path: str = "wallets.db"):
        self.db_path = db_path
        self._lock = threading.Lock()
        self._init_db()

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        with self._lock:
            conn = self._get_conn()
            try:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS wallets (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        address TEXT NOT NULL,
                        label TEXT NOT NULL,
                        chat_id INTEGER NOT NULL,
                        notify_chat_id INTEGER,
                        last_tx_timestamp INTEGER DEFAULT 0,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        UNIQUE (address, chat_id)
                    )
                """)
                self._ensure_column(conn, "wallets", "notify_chat_id", "INTEGER")
                conn.execute(
                    "UPDATE wallets SET notify_chat_id = chat_id WHERE notify_chat_id IS NULL"
                )
                conn.commit()
            finally:
                conn.close()

    def _ensure_column(
        self, conn: sqlite3.Connection, table: str, column: str, definition: str
    ):
        columns = {
            row["name"]
            for row in conn.execute(f"PRAGMA table_info({table})").fetchall()
        }
        if column not in columns:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")

    def add_wallet(
        self, address: str, label: str, chat_id: int, notify_chat_id: int | None = None
    ) -> bool:
        """添加监听钱包地址，成功返回 True，地址已存在返回 False"""
        if notify_chat_id is None:
            notify_chat_id = chat_id

        with self._lock:
            conn = self._get_conn()
            try:
                conn.execute(
                    """
                    INSERT INTO wallets (address, label, chat_id, notify_chat_id)
                    VALUES (?, ?, ?, ?)
                    """,
                    (address, label, chat_id, notify_chat_id),
                )
                conn.commit()
                return True
            except sqlite3.IntegrityError:
                return False
            finally:
                conn.close()

    def remove_wallet(self, address: str, chat_id: int) -> bool:
        """删除监听钱包地址，成功返回 True"""
        with self._lock:
            conn = self._get_conn()
            try:
                cursor = conn.execute(
                    "DELETE FROM wallets WHERE address = ? AND chat_id = ?",
                    (address, chat_id),
                )
                conn.commit()
                return cursor.rowcount > 0
            finally:
                conn.close()

    def get_wallets(self, chat_id: int) -> list[dict]:
        """获取指定 chat_id 的所有监听钱包"""
        with self._lock:
            conn = self._get_conn()
            try:
                rows = conn.execute(
                    """
                    SELECT address, label, chat_id, notify_chat_id, last_tx_timestamp
                    FROM wallets
                    WHERE chat_id = ?
                    """,
                    (chat_id,),
                ).fetchall()
                return [dict(row) for row in rows]
            finally:
                conn.close()

    def get_all_wallets(self) -> list[dict]:
        """获取所有监听钱包"""
        with self._lock:
            conn = self._get_conn()
            try:
                rows = conn.execute(
                    """
                    SELECT
                        address,
                        label,
                        chat_id,
                        COALESCE(notify_chat_id, chat_id) AS notify_chat_id,
                        last_tx_timestamp
                    FROM wallets
                    """
                ).fetchall()
                return [dict(row) for row in rows]
            finally:
                conn.close()

    def update_last_tx_timestamp(
        self, address: str, timestamp: int, chat_id: int | None = None
    ):
        """更新钱包的最后交易时间戳"""
        with self._lock:
            conn = self._get_conn()
            try:
                if chat_id is None:
                    conn.execute(
                        "UPDATE wallets SET last_tx_timestamp = ? WHERE address = ?",
                        (timestamp, address),
                    )
                else:
                    conn.execute(
                        """
                        UPDATE wallets
                        SET last_tx_timestamp = ?
                        WHERE address = ? AND chat_id = ?
                        """,
                        (timestamp, address, chat_id),
                    )
                conn.commit()
            finally:
                conn.close()

    def reset_all_timestamps(self, timestamp: int):
        """重置所有钱包的时间戳为指定值（用于机器人启动时）"""
        with self._lock:
            conn = self._get_conn()
            try:
                conn.execute(
                    "UPDATE wallets SET last_tx_timestamp = ?",
                    (timestamp,),
                )
                conn.commit()
            finally:
                conn.close()

    def get_wallet_by_address(
        self, address: str, chat_id: int | None = None
    ) -> Optional[dict]:
        """根据地址获取钱包信息"""
        with self._lock:
            conn = self._get_conn()
            try:
                if chat_id is None:
                    row = conn.execute(
                        """
                        SELECT address, label, chat_id, notify_chat_id, last_tx_timestamp
                        FROM wallets
                        WHERE address = ?
                        """,
                        (address,),
                    ).fetchone()
                else:
                    row = conn.execute(
                        """
                        SELECT address, label, chat_id, notify_chat_id, last_tx_timestamp
                        FROM wallets
                        WHERE address = ? AND chat_id = ?
                        """,
                        (address, chat_id),
                    ).fetchone()
                return dict(row) if row else None
            finally:
                conn.close()

    def get_wallet(self, address: str, chat_id: int) -> Optional[dict]:
        """根据地址和管理会话 ID 获取钱包信息"""
        return self.get_wallet_by_address(address, chat_id)
