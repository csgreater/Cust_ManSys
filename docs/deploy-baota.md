# 宝塔线上部署说明

## 1. 拉取代码

```bash
cd /www/wwwroot
git clone https://github.com/csgreater/Cust_ManSys.git
cd Cust_ManSys
```

后续更新使用：

```bash
cd /www/wwwroot/Cust_ManSys
git pull
```

## 2. 创建 Python 环境

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## 3. 配置 `.env`

```bash
cp .env.example .env
```

线上至少需要改这些值：

```ini
APP_ENV=production
DATABASE_URL=mysql+pymysql://order_app:strong_password@127.0.0.1:3306/order_manager?charset=utf8mb4
APP_SECRET_KEY=replace-with-a-random-string-longer-than-32-chars
APP_SECURE_COOKIES=true
ADMIN_PASSWORD=replace_admin_password
IMPORTER_PASSWORD=replace_importer_password
ANALYST_PASSWORD=replace_analyst_password
VIEWER_PASSWORD=replace_viewer_password
```

`APP_SECURE_COOKIES=true` 要求站点通过 HTTPS 访问。宝塔/Nginx 反向代理到本机 `127.0.0.1:8000` 即可。

## 4. 数据库初始化

建议使用专用 MySQL 用户，不要用 root 作为应用连接账号：

```sql
CREATE DATABASE IF NOT EXISTS order_manager CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER IF NOT EXISTS 'order_app'@'127.0.0.1' IDENTIFIED BY 'strong_password';
GRANT SELECT, INSERT, UPDATE, DELETE, CREATE, ALTER, INDEX, REFERENCES
ON order_manager.* TO 'order_app'@'127.0.0.1';
FLUSH PRIVILEGES;
```

初始化空库：

```bash
source venv/bin/activate
python scripts/init_db.py
python scripts/check_db_ready.py
```

如果是已有数据库升级，先备份，再按需要执行：

```bash
python scripts/migrate_add_order_source_customer_name.py
python scripts/migrate_profit_formula_warning.py
python scripts/migrate_optional_order_source_sku.py
python scripts/migrate_production_indexes.py
python scripts/ensure_future_partitions.py
python scripts/check_db_ready.py
```

## 5. 启动命令

宝塔 Python 项目或进程守护中使用：

```bash
/www/wwwroot/Cust_ManSys/venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --proxy-headers
```

如果宝塔使用项目目录和虚拟环境分开配置，启动模块填写：

```text
app.main:app
```

## 6. Nginx 反向代理

反向代理到：

```text
http://127.0.0.1:8000
```

Nginx 上传限制建议和 `.env` 的 `APP_MAX_UPLOAD_MB` 保持一致或略大。12 万行左右的月度 Excel 建议从 200MB 起：

```nginx
client_max_body_size 200m;
```

上线后访问：

```text
/healthz
/readyz
```

`/healthz` 表示应用进程可用，`/readyz` 会检查数据库连接。

## 7. 后续更新

```bash
cd /www/wwwroot/Cust_ManSys
git pull
source venv/bin/activate
pip install -r requirements.txt
python scripts/check_db_ready.py
```

如果更新里包含数据库迁移脚本，先备份 MySQL，再执行对应 `scripts/migrate_*.py`。更新完成后在宝塔里重启 Python 项目或进程守护服务。

低配服务器连续导入多个月份后，建议定期清理已完成或失败的导入暂存数据：

```bash
python scripts/cleanup_import_staging.py --days 7
```
