"""SQLite storage for monitored wallet addresses."""

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

    def _init_db(self) -> None:
        with self._lock:
            conn = self._get_conn()
            try:
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS wallets (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        address TEXT NOT NULL,
                        label TEXT NOT NULL,
                        chat_id INTEGER NOT NULL,
                        last_tx_timestamp INTEGER DEFAULT 0,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        UNIQUE (address, chat_id)
                    )
                    """
                )
                conn.commit()
            finally:
                conn.close()

    def add_wallet(self, address: str, label: str, chat_id: int) -> bool:
        with self._lock:
            conn = self._get_conn()
            try:
                conn.execute(
                    "INSERT INTO wallets (address, label, chat_id) VALUES (?, ?, ?)",
                    (address, label, chat_id),
                )
                conn.commit()
                return True
            except sqlite3.IntegrityError:
                return False
            finally:
                conn.close()

    def remove_wallet(self, address: str, chat_id: int) -> bool:
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
        with self._lock:
            conn = self._get_conn()
            try:
                rows = conn.execute(
                    "SELECT address, label, last_tx_timestamp FROM wallets WHERE chat_id = ? ORDER BY id",
                    (chat_id,),
                ).fetchall()
                return [dict(row) for row in rows]
            finally:
                conn.close()

    def get_all_wallets(self) -> list[dict]:
        with self._lock:
            conn = self._get_conn()
            try:
                rows = conn.execute(
                    "SELECT address, label, chat_id, last_tx_timestamp FROM wallets ORDER BY id"
                ).fetchall()
                return [dict(row) for row in rows]
            finally:
                conn.close()

    def update_last_tx_timestamp(self, address: str, timestamp: int, chat_id: Optional[int] = None) -> None:
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
                        "UPDATE wallets SET last_tx_timestamp = ? WHERE address = ? AND chat_id = ?",
                        (timestamp, address, chat_id),
                    )
                conn.commit()
            finally:
                conn.close()

    def reset_all_timestamps(self, timestamp: int) -> None:
        with self._lock:
            conn = self._get_conn()
            try:
                conn.execute("UPDATE wallets SET last_tx_timestamp = ?", (timestamp,))
                conn.commit()
            finally:
                conn.close()

    def get_wallet_by_address(self, address: str, chat_id: Optional[int] = None) -> Optional[dict]:
        with self._lock:
            conn = self._get_conn()
            try:
                if chat_id is None:
                    row = conn.execute(
                        "SELECT address, label, chat_id, last_tx_timestamp FROM wallets WHERE address = ?",
                        (address,),
                    ).fetchone()
                else:
                    row = conn.execute(
                        "SELECT address, label, chat_id, last_tx_timestamp FROM wallets WHERE address = ? AND chat_id = ?",
                        (address, chat_id),
                    ).fetchone()
                return dict(row) if row else None
            finally:
                conn.close()
