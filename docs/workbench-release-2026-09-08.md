# 异常中心与分析报告：交付与升级说明

日期：2026-09-08。对应用户已确认的重点：完善功能和体验，实际使用入口为异常数据与分析报告。

交付范围为 GitHub 仓库中的源码、测试、迁移脚本及同源构建的 `frontend/dist`。本次不包含宝塔服务器部署；Linux 升级流程见 [宝塔部署说明](deploy-baota.md#7-后续更新)。

## 本轮交付

| 用户任务 | 当前行为 |
| --- | --- |
| 发现异常 | 经营异常与数据质量分别查看；显示规则、对象、基线、影响、证据和核查状态。完整分页与 XLSX 不使用普通订单的 200 行展示上限。 |
| 记录判断 | 待核查、已确认、已排除及理由；证据变化后旧判断不直接套用。核查不修改经营金额。 |
| 生成报告 | 月度经营和异常专题模板，包含经营摘要、重点异常、变化贡献、核查建议及口径；数据完整计算，正文 Top 10 明确标识。 |
| 保存与复核 | 按账号保存不可变版本，重新生成增加版本；数据、规则、核查发生变化时旧报告可提示更新。PDF 用于阅读，XLSX 用于完整复核。 |
| 权限隔离 | 导入归属、整批行范围和提交时重新校验；报告按当前权限校验。管理员历史报告若含他人导入证据，降权后也不能绕过批次归属读取。 |
| 导入纠错 | 超长字段、不可存金额精度和派生利润溢出前置报错；敏感字段不复制到诊断原文。可下载完整质量清单并修正重传。 |
| 中断恢复 | 解析超过 15 分钟无进度且工作线程锁已释放时，显式释放中断批次并重新上传。正常活跃任务、入库事务均不取消。每次分块写入还在同一事务锁定批次状态，阻止已恢复的旧解析任务继续写入。 |
| 来源追溯 | 新入库数据记录 source_batch_no/source_row_no。既有记录来源为空，不反推、补写历史映射。 |
| 页面体验 | 主导航突出异常/报告；首页数据覆盖提示、最近有数据月份、编辑/已应用筛选、页面状态和窄屏布局；退出清空账号数据及进行中的请求。 |

规则参考值：低利润率 5%、高扣减费用率 20%、收入/利润下降 20%、最低收入 1000。负利润独立触发。阈值由设置权限修改，规则版本进入报告；不同规则影响金额分别显示，不相加称为总损失。

利润保持现有公式：`share_receivable - cost - freight - aux_material - share_cost`。费用率仅用 `freight + aux_material + share_cost`，不重复扣减 express_fee/logistics_fee。

整月区间对比等月数前期，非整月对比等天数前期，也可选去年同期。某个商品消失但本期其他商品有数据时，按零值计入贡献；整个本期无数据时明确缺数据，不认定业务下降。变化贡献是数值差额，不能当作已核实原因。

## 结构与启动

新增 `app/anomaly_engine.py`、`report_exports.py`、`workbench_api.py`、`workbench_store.py`、`import_access.py`、`import_lifecycle.py`、`analysis_periods.py`。Vue 工作台组件在 `frontend/src/workbench/`。

已有环境升级按顺序执行，连接目标必须是准备升级的数据库：

```powershell
python -m venv .venv
.venv/Scripts/python.exe -m pip install -r requirements-dev.txt
.venv/Scripts/python.exe scripts/migrate_anomaly_workbench.py
.venv/Scripts/python.exe scripts/check_db_ready.py
npm.cmd --prefix frontend ci
npm.cmd --prefix frontend run build
.venv/Scripts/python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8918
```

迁移仅增加三张工作台表、两个订单来源字段和来源索引，可重复执行。不要用 `init_db.py` 升级已有库，避免初始化默认角色的附带行为。大表加字段/索引耗时需在目标环境预演。

本机检查时 8000、5173 已有其他服务，本轮未替换它们。上述启动示例使用 8918，启动后访问 `http://127.0.0.1:8918/ui/` 即可使用已构建界面。验收用临时服务、浏览器和七个合成数据库已清理，实际开发库保留。

本机已验证 loopback development，并执行新增迁移。本地保留的迁移证据确认前后订单金额、行数及现有导入/账号记录数量一致，没有批量改写原有业务数据。线上迁移与部署尚未执行。

## 验证与复现

```powershell
.venv/Scripts/python.exe -m unittest discover -s tests -v
.venv/Scripts/python.exe scripts/check_nl_analytics.py
.venv/Scripts/python.exe -m compileall -q app scripts tests
npm.cmd --prefix frontend test
npm.cmd --prefix frontend run build
.venv/Scripts/python.exe scripts/check_workbench_integration.py
```

集成脚本只允许本地开发 MySQL，创建带随机后缀的专用测试库，使用合成订单、多个账号和 250 条质量错误；不复用用户业务库。验证完整分页/导出、手算金额、同货号别名的汇总等价、真实 Excel 上传及幂等入库、来源字段、异常核查、旧证据拒绝、版本并发与权限收窄。测试库由独有标记保护，浏览器验证后可用 `--drop <输出库名>` 删除，仅删除本脚本创建的测试库。

本地验证结果：后端 81 项测试、前端 16 项测试、自然语言分析 4 项自检及 Python 编译通过；Vite 生产构建通过。独立 MySQL 集成、桌面与 390px 窄屏流程、中文 PDF 两页导出均已验收。生产环境能力边界见下文。

以下验证原始材料仅保留在本地，不随代码上传；仓库提供上述测试和集成脚本用于复现：

- `output/implementation-20260908/integration-evidence.json`：真实 API 集成。
- `output/implementation-20260908/verification-final.json`：最终命令结果与数量。
- `output/playwright/implementation-*.png`：合成数据桌面、证据及窄屏截图。
- `output/implementation-20260908/sample-report.pdf`、`sample-report.xlsx`、`quality-250.xlsx`：合成导出样例。
- `output/implementation-20260908/task*-report.md`、`foundation-review.md`、`final-review.md`：实现与审查过程；审查发现的最终处置以本说明及最终验证文件为准。

## 明确留待后续的范围

本轮实现 V1/V2 及必要的版本、重算、权限、解析恢复与新增来源记录。没有实现完整账号 CRUD、独立全域导入角色、自动定时报告、团队分派、模型问答收藏/历史、批次作废替代流程或跨期“新增/持续/解除”历史对照视图。集中导入管理目前使用已有管理员权限。

普通订单兼容接口保留原有展示/导出边界，CSV 响应明确返回 50000 行上限；它们不承担本次完整异常导出。历史导入批次若缺少来源映射，受限账号不能据此取得无法证明合法的已入库批次内容。

本轮没有做生产月度大文件容量、网络故障注入、跨节点部署测试；没有调用外部模型。PDF 优先使用可用中文字体，Linux 发布环境需检查中文字体渲染。当前报告全量分组在应用内存处理，低资源生产环境应先验证实际峰值和耗时。

## 发布与回退

发布前备份目标数据库、应用代码、环境配置和前端构建，确认报告中文字体、数据范围与实际月度容量。先在单实例或小范围业务账号试运行，再扩大使用。

回退代码与前端时保留新增表和来源字段，避免删除已生成报告及核查记录；不执行删除列/表的自动回滚。旧版清理脚本未使用解析锁，回退时应暂停该旧脚本，避免误关闭仍在解析的批次。线上迁移、发布和验证尚未执行。
