"""
Database module for users, monitored wallets, and address remarks.
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
                    CREATE TABLE IF NOT EXISTS users (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        name TEXT NOT NULL,
                        telegram_chat_id INTEGER NOT NULL UNIQUE,
                        notify_chat_id INTEGER,
                        is_active INTEGER DEFAULT 1,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS wallets (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        address TEXT NOT NULL,
                        label TEXT NOT NULL,
                        user_id INTEGER,
                        chat_id INTEGER NOT NULL,
                        notify_chat_id INTEGER,
                        last_tx_timestamp INTEGER DEFAULT 0,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        UNIQUE (address, chat_id)
                    )
                """)
                self._ensure_column(conn, "wallets", "notify_chat_id", "INTEGER")
                self._ensure_column(conn, "wallets", "user_id", "INTEGER")
                conn.execute(
                    "UPDATE wallets SET notify_chat_id = chat_id WHERE notify_chat_id IS NULL"
                )
                conn.execute("""
                    INSERT OR IGNORE INTO users (name, telegram_chat_id, notify_chat_id)
                    SELECT 'TG ' || chat_id, chat_id, COALESCE(MAX(notify_chat_id), chat_id)
                    FROM wallets
                    GROUP BY chat_id
                """)
                conn.execute("""
                    UPDATE wallets
                    SET user_id = (
                        SELECT users.id
                        FROM users
                        WHERE users.telegram_chat_id = wallets.chat_id
                    )
                    WHERE user_id IS NULL
                """)
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS address_labels (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id INTEGER NOT NULL,
                        address TEXT NOT NULL,
                        label TEXT NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        UNIQUE (user_id, address)
                    )
                """)
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

    def ensure_user_for_chat(
        self, chat_id: int, name: str | None = None, notify_chat_id: int | None = None
    ) -> dict:
        display_name = name or f"TG {chat_id}"
        if notify_chat_id is None:
            notify_chat_id = chat_id

        with self._lock:
            conn = self._get_conn()
            try:
                row = conn.execute(
                    """
                    SELECT id, name, telegram_chat_id, notify_chat_id, is_active
                    FROM users
                    WHERE telegram_chat_id = ?
                    """,
                    (chat_id,),
                ).fetchone()
                if row:
                    return dict(row)

                cursor = conn.execute(
                    """
                    INSERT INTO users (name, telegram_chat_id, notify_chat_id)
                    VALUES (?, ?, ?)
                    """,
                    (display_name, chat_id, notify_chat_id),
                )
                conn.commit()
                return {
                    "id": cursor.lastrowid,
                    "name": display_name,
                    "telegram_chat_id": chat_id,
                    "notify_chat_id": notify_chat_id,
                    "is_active": 1,
                }
            finally:
                conn.close()

    def list_users(self) -> list[dict]:
        with self._lock:
            conn = self._get_conn()
            try:
                rows = conn.execute(
                    """
                    SELECT users.id, users.name, users.telegram_chat_id,
                           users.notify_chat_id, users.is_active,
                           COUNT(wallets.id) AS wallet_count
                    FROM users
                    LEFT JOIN wallets ON wallets.user_id = users.id
                    GROUP BY users.id
                    ORDER BY users.id DESC
                    """
                ).fetchall()
                return [dict(row) for row in rows]
            finally:
                conn.close()

    def get_user(self, user_id: int) -> Optional[dict]:
        with self._lock:
            conn = self._get_conn()
            try:
                row = conn.execute(
                    """
                    SELECT id, name, telegram_chat_id, notify_chat_id, is_active
                    FROM users
                    WHERE id = ?
                    """,
                    (user_id,),
                ).fetchone()
                return dict(row) if row else None
            finally:
                conn.close()

    def upsert_user(
        self,
        name: str,
        telegram_chat_id: int,
        notify_chat_id: int | None = None,
        is_active: int = 1,
    ) -> bool:
        if notify_chat_id is None:
            notify_chat_id = telegram_chat_id

        with self._lock:
            conn = self._get_conn()
            try:
                conn.execute(
                    """
                    INSERT INTO users (name, telegram_chat_id, notify_chat_id, is_active)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(telegram_chat_id) DO UPDATE SET
                        name = excluded.name,
                        notify_chat_id = excluded.notify_chat_id,
                        is_active = excluded.is_active
                    """,
                    (name, telegram_chat_id, notify_chat_id, 1 if is_active else 0),
                )
                conn.commit()
                return True
            finally:
                conn.close()

    def set_user_active(self, user_id: int, is_active: int) -> bool:
        with self._lock:
            conn = self._get_conn()
            try:
                cursor = conn.execute(
                    "UPDATE users SET is_active = ? WHERE id = ?",
                    (1 if is_active else 0, user_id),
                )
                conn.commit()
                return cursor.rowcount > 0
            finally:
                conn.close()

    def add_wallet(
        self, address: str, label: str, chat_id: int, notify_chat_id: int | None = None
    ) -> bool:
        user = self.ensure_user_for_chat(chat_id, notify_chat_id=notify_chat_id)
        if notify_chat_id is None:
            notify_chat_id = user.get("notify_chat_id") or chat_id

        with self._lock:
            conn = self._get_conn()
            try:
                conn.execute(
                    """
                    INSERT INTO wallets (address, label, user_id, chat_id, notify_chat_id)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (address, label, user["id"], chat_id, notify_chat_id),
                )
                conn.commit()
                return True
            except sqlite3.IntegrityError:
                return False
            finally:
                conn.close()

    def add_wallet_for_user(
        self,
        user_id: int,
        address: str,
        label: str,
        notify_chat_id: int | None = None,
    ) -> bool:
        user = self.get_user(user_id)
        if not user:
            return False

        chat_id = user["telegram_chat_id"]
        if notify_chat_id is None:
            notify_chat_id = user.get("notify_chat_id") or chat_id

        with self._lock:
            conn = self._get_conn()
            try:
                conn.execute(
                    """
                    INSERT INTO wallets (address, label, user_id, chat_id, notify_chat_id)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (address, label, user_id, chat_id, notify_chat_id),
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

    def remove_wallet_by_id(self, wallet_id: int) -> bool:
        with self._lock:
            conn = self._get_conn()
            try:
                cursor = conn.execute("DELETE FROM wallets WHERE id = ?", (wallet_id,))
                conn.commit()
                return cursor.rowcount > 0
            finally:
                conn.close()

    def get_wallets(self, chat_id: int) -> list[dict]:
        with self._lock:
            conn = self._get_conn()
            try:
                rows = conn.execute(
                    """
                    SELECT wallets.id, wallets.address, wallets.label, wallets.user_id,
                           wallets.chat_id, wallets.notify_chat_id,
                           wallets.last_tx_timestamp
                    FROM wallets
                    LEFT JOIN users ON users.id = wallets.user_id
                    WHERE wallets.chat_id = ?
                      AND COALESCE(users.is_active, 1) = 1
                    ORDER BY wallets.id DESC
                    """,
                    (chat_id,),
                ).fetchall()
                return [dict(row) for row in rows]
            finally:
                conn.close()

    def get_wallets_by_user(self, user_id: int) -> list[dict]:
        with self._lock:
            conn = self._get_conn()
            try:
                rows = conn.execute(
                    """
                    SELECT id, address, label, user_id, chat_id, notify_chat_id,
                           last_tx_timestamp
                    FROM wallets
                    WHERE user_id = ?
                    ORDER BY id DESC
                    """,
                    (user_id,),
                ).fetchall()
                return [dict(row) for row in rows]
            finally:
                conn.close()

    def get_all_wallets(self) -> list[dict]:
        with self._lock:
            conn = self._get_conn()
            try:
                rows = conn.execute(
                    """
                    SELECT
                        wallets.id,
                        wallets.address,
                        wallets.label,
                        wallets.user_id,
                        wallets.chat_id,
                        COALESCE(wallets.notify_chat_id, wallets.chat_id) AS notify_chat_id,
                        wallets.last_tx_timestamp
                    FROM wallets
                    LEFT JOIN users ON users.id = wallets.user_id
                    WHERE COALESCE(users.is_active, 1) = 1
                    """
                ).fetchall()
                return [dict(row) for row in rows]
            finally:
                conn.close()

    def update_last_tx_timestamp(self, address: str, timestamp: int):
        with self._lock:
            conn = self._get_conn()
            try:
                conn.execute(
                    "UPDATE wallets SET last_tx_timestamp = ? WHERE address = ?",
                    (timestamp, address),
                )
                conn.commit()
            finally:
                conn.close()

    def reset_all_timestamps(self, timestamp: int):
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

    def get_wallet_by_address(self, address: str) -> Optional[dict]:
        with self._lock:
            conn = self._get_conn()
            try:
                row = conn.execute(
                    """
                    SELECT address, label, chat_id, notify_chat_id,
                           last_tx_timestamp, user_id
                    FROM wallets
                    WHERE address = ?
                    """,
                    (address,),
                ).fetchone()
                return dict(row) if row else None
            finally:
                conn.close()

    def get_wallet(self, address: str, chat_id: int) -> Optional[dict]:
        with self._lock:
            conn = self._get_conn()
            try:
                row = conn.execute(
                    """
                    SELECT address, label, chat_id, notify_chat_id,
                           last_tx_timestamp, user_id
                    FROM wallets
                    WHERE address = ? AND chat_id = ?
                    """,
                    (address, chat_id),
                ).fetchone()
                return dict(row) if row else None
            finally:
                conn.close()

    def upsert_address_label(self, user_id: int, address: str, label: str) -> bool:
        with self._lock:
            conn = self._get_conn()
            try:
                conn.execute(
                    """
                    INSERT INTO address_labels (user_id, address, label)
                    VALUES (?, ?, ?)
                    ON CONFLICT(user_id, address) DO UPDATE SET
                        label = excluded.label
                    """,
                    (user_id, address, label),
                )
                conn.commit()
                return True
            finally:
                conn.close()

    def get_address_label(self, user_id: int | None, address: str) -> Optional[str]:
        if user_id is None:
            return None

        with self._lock:
            conn = self._get_conn()
            try:
                row = conn.execute(
                    """
                    SELECT label
                    FROM address_labels
                    WHERE user_id = ? AND UPPER(address) = UPPER(?)
                    """,
                    (user_id, address),
                ).fetchone()
                return row["label"] if row else None
            finally:
                conn.close()

    def get_address_labels(self, user_id: int | None = None) -> list[dict]:
        with self._lock:
            conn = self._get_conn()
            try:
                if user_id is None:
                    rows = conn.execute(
                        """
                        SELECT address_labels.id, address_labels.user_id,
                               users.name AS user_name, address_labels.address,
                               address_labels.label
                        FROM address_labels
                        LEFT JOIN users ON users.id = address_labels.user_id
                        ORDER BY address_labels.id DESC
                        """
                    ).fetchall()
                else:
                    rows = conn.execute(
                        """
                        SELECT address_labels.id, address_labels.user_id,
                               users.name AS user_name, address_labels.address,
                               address_labels.label
                        FROM address_labels
                        LEFT JOIN users ON users.id = address_labels.user_id
                        WHERE address_labels.user_id = ?
                        ORDER BY address_labels.id DESC
                        """,
                        (user_id,),
                    ).fetchall()
                return [dict(row) for row in rows]
            finally:
                conn.close()

    def remove_address_label(self, label_id: int) -> bool:
        with self._lock:
            conn = self._get_conn()
            try:
                cursor = conn.execute(
                    "DELETE FROM address_labels WHERE id = ?",
                    (label_id,),
                )
                conn.commit()
                return cursor.rowcount > 0
            finally:
                conn.close()
