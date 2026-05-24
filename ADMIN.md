# WalletMonitor 后台管理

现在可以通过 Web 后台管理用户、监听地址和出入账地址备注。

## 启动

```bash
python admin.py
```

默认地址：

```text
http://127.0.0.1:8080/?token=change_this_admin_token
```

## 配置

```env
ADMIN_HOST=127.0.0.1
ADMIN_PORT=8080
ADMIN_TOKEN=change_this_admin_token
```

## 功能

- 用户管理：新增/更新用户，配置 Telegram Chat ID、默认通知 Chat ID，启用或停用用户。
- 监听地址：按用户添加和删除 TRON 监听地址。
- 地址备注：按用户维护出账/入账地址备注，交易通知里会显示对应备注。
