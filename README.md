# 订单数据管理系统

基于 **FastAPI + MySQL + Vue 3/Vite** 的订单经营管理系统。系统用于导入月度订单明细、按权限查询与导出数据，并从产品、店铺、渠道等维度分析销售额、成本、利润和经营风险。

> 本文按当前工作区代码整理，最后核对日期为 2026-07-17。本地数据库连接和代表性业务接口已完成冒烟验证；线上环境变量、容量与部署状态仍需在发布时单独验收。

## 当前完成情况

| 模块 | 当前状态 | 已有能力 |
| --- | --- | --- |
| 账户与权限 | 已实现 | 登录会话、用户/角色、按部门/平台/店铺的数据范围隔离；订单中的姓名、手机和地址由 API 在服务端脱敏。 |
| 订单管理 | 已实现 | 多条件查询、默认上月时间范围、订单明细查看和流式 CSV 导出。 |
| Excel 导入 | 已实现 | 模板下载、`.xlsx`/`.xlsm` 上传、后台分块解析校验、进度轮询、异常行查看、确认入库、并发互斥和整批文件指纹去重。 |
| 数据看板 | 已实现 | 数据中心首页看板、产品分析、店铺分析及多维经营驾驶舱；包含核心 KPI、同期比较、经营趋势、平台结构、TOP 产品和风险信号。 |
| 智能分析 | 已实现 | 受权限约束的自然语言分析 API；内置规则解析，可选接入 Ark 解析意图，生成的 SQL 会经过安全审计。 |
| 前端 | 已实现 | Vue 3/Vite 单页运营台；构建后的 `frontend/dist` 由 FastAPI 挂载在 `/ui/`，保留 Jinja 页面作为兼容入口。 |
| 健康检查 | 已实现 | `/healthz` 检查进程，`/readyz` 检查数据库连接。 |
| Coding Plan | 已实现，待发布验收 | 当前工作区已新增 `/coding-plan` 和 Ark 对话接口；仅登录用户可访问，包含输入长度、按用户/IP 限流、每日额度、调用审计和生产配置校验。该组文件尚未提交，应完成上线验收后再作为正式功能发布。 |
| 质量基线 | 已实现 | 导入解析与 Ark 响应已有不依赖数据库的单元测试；GitHub Actions 会执行 Python 编译、单元测试、自然语言分析自检和 Vue 生产构建。 |

当前仍需将这些改动完成代码审查并合并为可追溯的发布版本；完整的分阶段计划见 [维护更新计划](docs/maintenance-plan.md)。

## 目录说明

```text
app/                 FastAPI 应用、数据库访问、导入与权限逻辑
app/templates/       保留的 Jinja 兼容页面
app/static/          兼容页面与 Coding Plan 的静态资源
frontend/            Vue 3/Vite 源码与构建配置
scripts/             初始化、迁移、检查、分区和清理脚本
docs/                上线检查、宝塔部署和维护计划
sample_data/         示例导入文件
```

## 快速开始（开发环境）

### 1. 配置 Python 与数据库

建议使用 Python 3.10+；数据库支持 MySQL 5.7.44+ 和 MySQL 8.0+。复制并填写环境变量：

```bash
cp .env.example .env
```

最小配置示例：

```ini
APP_ENV=development
DATABASE_URL=mysql+pymysql://order_app:your_password@127.0.0.1:3306/order_manager?charset=utf8mb4
APP_SECRET_KEY=change-this-secret-key-at-least-32-chars
```

安装后端依赖并初始化空数据库：

```bash
python -m venv venv
# Windows: venv\Scripts\activate
# macOS/Linux: source venv/bin/activate
pip install -r requirements.txt
python scripts/init_db.py
python scripts/check_db_ready.py
```

初始化会创建业务表、导入表、角色权限和默认账号。默认密码仅可用于本地初始验证；生产环境必须在 `.env` 中更换全部默认密码，并使用独立的 MySQL 应用账号。

### 2. 启动后端

```bash
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --proxy-headers
```

后端地址为 `http://127.0.0.1:8000`。可用性检查：

```text
http://127.0.0.1:8000/healthz
http://127.0.0.1:8000/readyz
```

### 3. 启动 Vue 前端（推荐）

另开一个终端：

```bash
cd frontend
npm install
npm run dev
```

访问 Vite 显示的地址（默认 `http://127.0.0.1:5173`）。开发服务器已将 `/api` 和订单导出请求代理到后端 `127.0.0.1:8000`。

构建生产前端：

```bash
cd frontend
npm ci
npm run build
```

构建结果位于 `frontend/dist`。该目录存在时，后端会在 `/ui/` 提供前端，并将旧页面访问重定向到该入口。

## 业务使用说明

### 导入订单

1. 在“数据导入”页下载模板，或生成示例文件：

   ```bash
   python scripts/create_sample_excel.py
   ```

2. 上传 `.xlsx` 或 `.xlsm` 文件。文件先进入后台处理批次，页面会轮询显示解析进度、警告和异常行。
3. 仅当校验通过、没有异常行时，才可确认入库。

当前导入规则要点：

- 必填字段：订单编号、发货时间、客户编号、渠道分类、渠道平台、销售渠道、货品编号、销售额、成本金额、利润。
- `订单来源`、`客户名称`、地址、省/市/区县、`货品分类` 等字段在模板中可用；货品分类为可选。
- 可选数值空值按 `0` 处理，必填数值不得为空；拒绝 NaN、无穷值和超出数据库字段范围的数值。同一订单同一货品允许多行。
- 导入文件采用与行顺序无关的整批数据指纹避免重复入库；上传与确认入库均带并发互斥，订单明细不提供物理删除功能。
- 利润口径为：`应收合计分摊 - 成本 - 运费 - 辅料 - 分摊费用`。Excel 中的利润仅用于提示，不阻止入库。

对于约 12 万行的月度文件，建议将 `APP_MAX_UPLOAD_MB`、数据库读写超时和 Nginx 上传限制同步调整为 200MB、600 秒或更高，并按月分批导入。

### 分析与权限

- 所有查询、看板、分析和导出均受角色数据范围限制。
- 首页看板默认查询上月；日期范围、部门、平台和店铺筛选仅在点击“执行筛选”后请求，避免输入过程反复扫描数据库。
- 智能分析会把问题解析为受控查询，并强制带订单日期范围；单次分析最长三年。
- `ANALYTICS_API_TOKEN` 可为分析 API 配置服务访问令牌；生产环境应设置为至少 24 位的随机值。

### 低配置服务器说明

- 首页看板在一次条件聚合中同时计算当前周期和等长前周期；占比查询使用窗口聚合，避免重复扫描明细表。
- 看板趋势最多按日展示 62 天，更长范围自动按月汇总；前端不引入大型图表库，生产构建的 JS gzip 约 43KB。
- 导出使用服务端游标按 500 行分批生成 CSV，不把全部结果一次性放入内存，并对可能触发电子表格公式的文本做转义。
- 导入状态轮询采用逐步退避，并在离开导入页面时取消；前端会取消过期请求并复用相同筛选条件的结果。

### 可选 Ark 能力

系统默认使用内置规则。要启用 Ark 的分析意图解析，在服务端 `.env` 中配置：

```ini
ARK_ANALYTICS_ENABLED=true
ARK_BASE_URL=https://ark.cn-beijing.volces.com/api/coding/v3
ARK_API_KEY=your_server_side_key
ARK_MODEL=your_model_id
ARK_TIMEOUT_SECONDS=20
```

当前工作区的 Coding Plan 候选功能与上述网关、密钥、模型共用配置，另需：

```ini
ARK_CODING_CHAT_ENABLED=true
ARK_CODING_MAX_OUTPUT_TOKENS=1600
ARK_CODING_RATE_LIMIT_PER_MINUTE=20
ARK_CODING_DAILY_LIMIT_PER_USER=50
ARK_CODING_DAILY_ALERT_THRESHOLD=40
```

该功能会把用户在对话页输入的内容发送给配置的模型服务。应用层只记录用户标识、来源 IP、模型、输入长度和用量，不记录对话正文；每日额度在应用进程内计数，生产环境仍应在模型网关或反向代理配置全局额度与告警。不要把密钥写入前端、代码仓库或客户端配置。

## 数据库升级与日常运维

新数据库只需执行 `python scripts/init_db.py`。已有数据库升级前必须备份，然后依据当前线上版本选择相应的 `scripts/migrate_*.py` 脚本；迁移脚本可重复运行，但不应把“全部迁移”当作跨版本升级策略。

上线前和每月导入前执行：

```bash
python scripts/ensure_future_partitions.py
python scripts/check_db_ready.py
```

清理已完成或失败的导入暂存数据（示例保留 7 天）：

```bash
python scripts/cleanup_import_staging.py --days 7
```

详细步骤见：

- [数据库上线检查清单](docs/database-online-checklist.md)
- [宝塔线上部署说明](docs/deploy-baota.md)
- [维护更新计划](docs/maintenance-plan.md)

## 生产环境最低要求

- `APP_ENV=production`、`APP_SECURE_COOKIES=true`，并通过 HTTPS 访问。
- 使用独立的 MySQL 应用账号，避免使用 `root`；替换 `APP_SECRET_KEY` 和所有默认账号密码。
- 配置每日备份，并至少每季度在独立环境完成一次恢复演练。
- 部署前完成数据库备份、必要迁移、`frontend` 构建、`check_db_ready.py`、`/healthz` 和 `/readyz` 验收。
- 不将 `.env`、备份文件、上传文件或 `frontend/node_modules` 提交到仓库。

## 维护优先级摘要

1. **上线前**：将当前未提交的 Coding Plan 改动完成审查、提交，并在生产网关配置全局调用额度/告警。
2. **两周内**：为 CI 启用分支保护，并扩展需要数据库的 API 冒烟测试。
3. **一个月内**：为每次发布建立迁移清单、回滚说明和备份恢复演练记录。
4. **持续执行**：每日查看健康与备份结果；每月补分区、检查导入质量和清理暂存数据；每季度升级依赖并做恢复演练。
