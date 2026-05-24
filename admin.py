"""
Simple web admin for WalletMonitor.

Run:
    python admin.py
"""

from __future__ import annotations

import hmac
import os
import time
from html import escape
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlencode, urlparse

from database import Database


def load_env(path: str = ".env"):
    if not os.path.exists(path):
        return
    with open(path, "r", encoding="utf-8") as file:
        for line in file:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip("'\""))


load_env()

DB_PATH = os.getenv("DB_PATH", "wallets.db")
ADMIN_HOST = os.getenv("ADMIN_HOST", "127.0.0.1")
ADMIN_PORT = int(os.getenv("ADMIN_PORT", "8080"))
ADMIN_TOKEN = os.getenv("ADMIN_TOKEN", "")

db = Database(DB_PATH)


def is_valid_tron_address(address: str) -> bool:
    if not address or not address.startswith("T") or len(address) != 34:
        return False
    try:
        import base58

        return len(base58.b58decode(address)) == 25
    except Exception:
        return True


def _url(path: str = "/", token: str = "") -> str:
    if not token:
        return path
    sep = "&" if "?" in path else "?"
    return f"{path}{sep}{urlencode({'token': token})}"


def _option(value: int, label: str, selected: int | None = None) -> str:
    flag = " selected" if selected == value else ""
    return f'<option value="{value}"{flag}>{escape(label)}</option>'


def _layout(content: str) -> bytes:
    html = f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>WalletMonitor Admin</title>
  <style>
    :root {{
      color-scheme: light;
      --bg: #f4f6f8;
      --panel: #ffffff;
      --line: #d9e0e7;
      --text: #1f2933;
      --muted: #65758b;
      --accent: #0f766e;
      --danger: #b42318;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      background: var(--bg);
      color: var(--text);
      font-family: Arial, "Microsoft YaHei", sans-serif;
      font-size: 14px;
    }}
    header {{ background: #102a43; color: white; padding: 18px 28px; }}
    header h1 {{ margin: 0; font-size: 20px; letter-spacing: 0; }}
    main {{ max-width: 1180px; margin: 0 auto; padding: 22px; }}
    section {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      margin-bottom: 18px;
      padding: 16px;
    }}
    h2 {{ margin: 0 0 14px; font-size: 17px; }}
    form.grid {{
      display: grid;
      grid-template-columns: repeat(5, minmax(120px, 1fr));
      gap: 10px;
      align-items: end;
      margin-bottom: 14px;
    }}
    label {{ display: grid; gap: 5px; color: var(--muted); font-size: 12px; }}
    input, select {{
      width: 100%;
      min-height: 36px;
      border: 1px solid #cbd5df;
      border-radius: 6px;
      padding: 7px 9px;
      color: var(--text);
      background: white;
      font: inherit;
    }}
    button {{
      min-height: 36px;
      border: 0;
      border-radius: 6px;
      padding: 8px 12px;
      color: white;
      background: var(--accent);
      cursor: pointer;
      font: inherit;
      white-space: nowrap;
    }}
    button.secondary {{ background: #486581; }}
    button.danger {{ background: var(--danger); }}
    table {{ width: 100%; border-collapse: collapse; background: white; }}
    th, td {{
      border-top: 1px solid var(--line);
      padding: 9px 8px;
      text-align: left;
      vertical-align: top;
    }}
    th {{ color: var(--muted); font-size: 12px; font-weight: 600; }}
    code {{ font-family: Consolas, monospace; font-size: 12px; overflow-wrap: anywhere; }}
    .muted {{ color: var(--muted); }}
    .status-on {{ color: var(--accent); font-weight: 700; }}
    .status-off {{ color: var(--danger); font-weight: 700; }}
    @media (max-width: 820px) {{
      main {{ padding: 12px; }}
      form.grid {{ grid-template-columns: 1fr; }}
      table, thead, tbody, tr, th, td {{ display: block; }}
      thead {{ display: none; }}
      tr {{ border-top: 1px solid var(--line); padding: 8px 0; }}
      td {{ border: 0; padding: 5px 0; }}
      td::before {{
        content: attr(data-label);
        display: block;
        color: var(--muted);
        font-size: 12px;
      }}
    }}
  </style>
</head>
<body>
  <header><h1>WalletMonitor 后台管理</h1></header>
  <main>{content}</main>
</body>
</html>"""
    return html.encode("utf-8")


def _users_table(users: list[dict], token: str) -> str:
    rows = []
    for user in users:
        active = int(user.get("is_active") or 0)
        status = (
            '<span class="status-on">启用</span>'
            if active
            else '<span class="status-off">停用</span>'
        )
        next_active = 0 if active else 1
        rows.append(f"""
          <tr>
            <td data-label="ID">{user["id"]}</td>
            <td data-label="用户">{escape(user["name"])}</td>
            <td data-label="Telegram Chat ID"><code>{user["telegram_chat_id"]}</code></td>
            <td data-label="通知 Chat ID"><code>{user.get("notify_chat_id") or ""}</code></td>
            <td data-label="监听数">{user.get("wallet_count", 0)}</td>
            <td data-label="状态">{status}</td>
            <td data-label="操作">
              <form method="post" action="{_url('/toggle-user', token)}">
                <input type="hidden" name="user_id" value="{user["id"]}">
                <input type="hidden" name="is_active" value="{next_active}">
                <button class="secondary" type="submit">{"停用" if active else "启用"}</button>
              </form>
            </td>
          </tr>
        """)
    return "\n".join(rows) or '<tr><td colspan="7" class="muted">暂无用户</td></tr>'


def _wallets_table(wallets: list[dict], users_by_id: dict[int, dict], token: str) -> str:
    rows = []
    for wallet in wallets:
        user = users_by_id.get(wallet.get("user_id"))
        rows.append(f"""
          <tr>
            <td data-label="ID">{wallet["id"]}</td>
            <td data-label="用户">{escape(user["name"]) if user else "-"}</td>
            <td data-label="备注">{escape(wallet["label"])}</td>
            <td data-label="地址"><code>{escape(wallet["address"])}</code></td>
            <td data-label="通知 Chat ID"><code>{wallet.get("notify_chat_id") or ""}</code></td>
            <td data-label="操作">
              <form method="post" action="{_url('/delete-wallet', token)}">
                <input type="hidden" name="wallet_id" value="{wallet["id"]}">
                <button class="danger" type="submit">删除</button>
              </form>
            </td>
          </tr>
        """)
    return "\n".join(rows) or '<tr><td colspan="6" class="muted">暂无监听地址</td></tr>'


def _labels_table(labels: list[dict], token: str) -> str:
    rows = []
    for item in labels:
        rows.append(f"""
          <tr>
            <td data-label="ID">{item["id"]}</td>
            <td data-label="用户">{escape(item.get("user_name") or "-")}</td>
            <td data-label="备注">{escape(item["label"])}</td>
            <td data-label="地址"><code>{escape(item["address"])}</code></td>
            <td data-label="操作">
              <form method="post" action="{_url('/delete-label', token)}">
                <input type="hidden" name="label_id" value="{item["id"]}">
                <button class="danger" type="submit">删除</button>
              </form>
            </td>
          </tr>
        """)
    return "\n".join(rows) or '<tr><td colspan="5" class="muted">暂无地址备注</td></tr>'


def render_index(token: str) -> bytes:
    users = db.list_users()
    users_by_id = {user["id"]: user for user in users}
    wallets = db.get_all_wallets()
    labels = db.get_address_labels()
    user_options = "\n".join(
        _option(user["id"], f'{user["name"]} / {user["telegram_chat_id"]}')
        for user in users
    )

    content = f"""
<section>
  <h2>用户管理</h2>
  <form class="grid" method="post" action="{_url('/save-user', token)}">
    <label>用户名<input name="name" placeholder="客户A" required></label>
    <label>Telegram Chat ID<input name="telegram_chat_id" placeholder="-100..." required></label>
    <label>默认通知 Chat ID<input name="notify_chat_id" placeholder="不填则使用 Telegram Chat ID"></label>
    <label>状态
      <select name="is_active">
        <option value="1">启用</option>
        <option value="0">停用</option>
      </select>
    </label>
    <button type="submit">保存用户</button>
  </form>
  <table>
    <thead><tr><th>ID</th><th>用户</th><th>Telegram Chat ID</th><th>通知 Chat ID</th><th>监听数</th><th>状态</th><th>操作</th></tr></thead>
    <tbody>{_users_table(users, token)}</tbody>
  </table>
</section>

<section>
  <h2>监听地址</h2>
  <form class="grid" method="post" action="{_url('/save-wallet', token)}">
    <label>用户<select name="user_id" required>{user_options}</select></label>
    <label>钱包地址<input name="address" placeholder="T..." required></label>
    <label>监听备注<input name="label" placeholder="热钱包 / 客户地址" required></label>
    <label>通知 Chat ID<input name="notify_chat_id" placeholder="不填则用用户默认值"></label>
    <button type="submit">添加监听</button>
  </form>
  <table>
    <thead><tr><th>ID</th><th>用户</th><th>备注</th><th>地址</th><th>通知 Chat ID</th><th>操作</th></tr></thead>
    <tbody>{_wallets_table(wallets, users_by_id, token)}</tbody>
  </table>
</section>

<section>
  <h2>出入账地址备注</h2>
  <form class="grid" method="post" action="{_url('/save-label', token)}">
    <label>用户<select name="user_id" required>{user_options}</select></label>
    <label>地址<input name="address" placeholder="T..." required></label>
    <label>备注<input name="label" placeholder="交易所 / 客户B / 收款方" required></label>
    <button type="submit">保存备注</button>
  </form>
  <table>
    <thead><tr><th>ID</th><th>用户</th><th>备注</th><th>地址</th><th>操作</th></tr></thead>
    <tbody>{_labels_table(labels, token)}</tbody>
  </table>
</section>
"""
    return _layout(content)


class AdminHandler(BaseHTTPRequestHandler):
    def _query(self) -> dict:
        return {k: v[0] for k, v in parse_qs(urlparse(self.path).query).items()}

    def _form(self) -> dict:
        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length).decode("utf-8")
        return {k: v[0] for k, v in parse_qs(body).items()}

    def _token(self, data: dict | None = None) -> str:
        data = data or {}
        return (
            data.get("token")
            or self._query().get("token")
            or self.headers.get("X-Admin-Token", "")
        )

    def _check_auth(self, data: dict | None = None) -> bool:
        if not ADMIN_TOKEN:
            return True
        return hmac.compare_digest(self._token(data), ADMIN_TOKEN)

    def _redirect(self, path: str = "/"):
        token = self._token()
        self.send_response(303)
        self.send_header("Location", _url(path, token))
        self.end_headers()

    def _send_html(self, body: bytes):
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path != "/":
            self.send_error(404)
            return
        if not self._check_auth():
            self.send_error(403, "Invalid admin token")
            return
        self._send_html(render_index(self._token()))

    def do_POST(self):
        data = self._form()
        if not self._check_auth(data):
            self.send_error(403, "Invalid admin token")
            return

        parsed = urlparse(self.path)
        try:
            if parsed.path == "/save-user":
                name = data.get("name", "").strip()
                telegram_chat_id = int(data.get("telegram_chat_id", "").strip())
                notify_raw = data.get("notify_chat_id", "").strip()
                notify_chat_id = int(notify_raw) if notify_raw else telegram_chat_id
                is_active = int(data.get("is_active", "1"))
                if not name:
                    raise ValueError("Name is required")
                db.upsert_user(name, telegram_chat_id, notify_chat_id, is_active)
            elif parsed.path == "/toggle-user":
                db.set_user_active(int(data["user_id"]), int(data["is_active"]))
            elif parsed.path == "/save-wallet":
                user_id = int(data["user_id"])
                address = data.get("address", "").strip()
                label = data.get("label", "").strip()
                notify_raw = data.get("notify_chat_id", "").strip()
                notify_chat_id = int(notify_raw) if notify_raw else None
                if not is_valid_tron_address(address):
                    raise ValueError("Invalid TRON address")
                if not label:
                    raise ValueError("Wallet label is required")
                if not db.add_wallet_for_user(user_id, address, label, notify_chat_id):
                    raise ValueError("Wallet already exists or user is missing")
                db.update_last_tx_timestamp(address, int(time.time() * 1000))
            elif parsed.path == "/delete-wallet":
                db.remove_wallet_by_id(int(data["wallet_id"]))
            elif parsed.path == "/save-label":
                user_id = int(data["user_id"])
                address = data.get("address", "").strip()
                label = data.get("label", "").strip()
                if not is_valid_tron_address(address):
                    raise ValueError("Invalid TRON address")
                if not label:
                    raise ValueError("Address remark is required")
                db.upsert_address_label(user_id, address, label)
            elif parsed.path == "/delete-label":
                db.remove_address_label(int(data["label_id"]))
            else:
                self.send_error(404)
                return
        except Exception as exc:
            self.send_error(400, str(exc))
            return

        self._redirect("/")

    def log_message(self, format: str, *args):
        print("%s - %s" % (self.address_string(), format % args))


if __name__ == "__main__":
    print(f"Admin running on http://{ADMIN_HOST}:{ADMIN_PORT}")
    if not ADMIN_TOKEN:
        print("Warning: ADMIN_TOKEN is empty; admin page is open on the bind host.")
    ThreadingHTTPServer((ADMIN_HOST, ADMIN_PORT), AdminHandler).serve_forever()
