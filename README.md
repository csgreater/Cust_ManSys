# 订单数据管理系统第一版

FastAPI + MySQL + Jinja 实现的订单数据管理系统，支持 Excel 导入、订单查询、产品分析、店铺平台分析和角色级数据权限。

## 1. 配置

复制 `.env.example` 为 `.env`，填写 MySQL 连接：

```ini
APP_ENV=development
DATABASE_URL=mysql+pymysql://order_app:your_password@127.0.0.1:3306/order_manager?charset=utf8mb4
APP_SECRET_KEY=change-this-secret-key-at-least-32-chars
```

线上部署时请设置 `APP_ENV=production`、`APP_SECURE_COOKIES=true`，并替换所有默认密码。完整宝塔部署流程见 `docs/deploy-baota.md`。

## 2. 初始化数据库

```bash
python scripts/init_db.py
```

初始化会创建业务表、导入表、权限表，并预置账号：

| 账号 | 默认密码 | 角色 |
| --- | --- | --- |
| admin | admin123 | 管理员 |
| importer | importer123 | 导入员 |
| analyst | analyst123 | 分析员 |
| viewer | viewer123 | 只读用户 |

默认密码可在 `.env` 中覆盖。首次部署后请修改。

如果数据库已经初始化过，需要补订单来源和客户名称字段，执行：

```bash
python scripts/migrate_add_order_source_customer_name.py
```

如果需要切换到当前利润口径并增加导入提示字段，执行：

```bash
python scripts/migrate_profit_formula_warning.py
```

如果需要允许 `订单来源` 和 `商品链接SkuId` 为空，执行：

```bash
python scripts/migrate_optional_order_source_sku.py
```

如果需要补齐生产辅助索引，执行：

```bash
python scripts/migrate_production_indexes.py
```

上线前检查数据库结构、索引、分区和预置账号：

```bash
python scripts/check_db_ready.py
```

每月导入前可预先补未来分区：

```bash
python scripts/ensure_future_partitions.py
```

## 3. 启动

```bash
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --proxy-headers
```

打开 `http://127.0.0.1:8000`。

健康检查：

- `/healthz`：应用进程可用。
- `/readyz`：应用和数据库连接可用。

## 4. 生成样例 Excel

如果暂时没有真实订单数据，可以生成一份小样例用于验证导入流程：

```bash
python scripts/create_sample_excel.py
```

脚本会生成 `sample_data/orders_sample.xlsx`。

## 5. 说明

- 查询、看板、分析、导出都会应用角色级数据范围。
- Excel 利润字段只做提示，不阻止入库；正式利润以导入明细按系统口径计算。
- 当前利润口径：`应收合计分摊 - 成本 - 运费 - 辅料 - 分摊费用`。
- 上传 Excel 后会先进入暂存批次，校验无异常才能确认入库。
- 上传文件大小默认限制为 `50MB`，可通过 `.env` 中的 `APP_MAX_UPLOAD_MB` 调整。
- 当前 Excel 模板包含 `订单来源` 和 `客户名称`，位置分别在 `客户编号` 前后。
- 订单明细不提供物理删除功能。
