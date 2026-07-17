<template>
  <div class="app-shell">
    <section v-if="!me.authenticated" class="login-stage">
      <div class="login-hero">
        <p class="kicker">DATA OPERATIONS NETWORK · ONLINE</p>
        <h1>订单数据中枢</h1>
        <p>统一接入订单、渠道、产品与利润信号，在一个轻量控制台内完成监测、分析、导入和权限治理。</p>
      </div>
      <form class="login-card" @submit.prevent="login">
        <div>
          <p class="kicker">SECURE ACCESS</p>
          <h2>账号登录</h2>
        </div>
        <label>账号<input v-model="loginForm.username" autocomplete="username" /></label>
        <label>密码<input v-model="loginForm.password" type="password" autocomplete="current-password" /></label>
        <div v-if="error" class="alert">{{ error }}</div>
        <button class="primary" type="submit" :disabled="authBusy">{{ authBusy ? '正在验证...' : '进入系统' }}</button>
      </form>
    </section>

    <template v-else>
      <aside class="nav-rail">
        <div class="brand">
          <span>DC</span>
          <div><strong>订单数据中枢</strong><small>DATA CONTROL CENTER</small></div>
        </div>
        <nav class="nav-menu">
          <button v-for="item in visibleNav" :key="item.key" :class="{ active: view === item.key }" @click="openView(item.key)">
            <component :is="item.icon" :size="18" />
            {{ item.label }}
          </button>
        </nav>
        <div class="nav-foot">
          <div class="profile">
            <strong>{{ me.display_name }}</strong>
            <small>{{ me.username }}</small>
          </div>
          <button class="ghost" @click="logout">退出</button>
        </div>
      </aside>

      <main class="workspace">
        <header class="topbar">
          <div>
            <p class="kicker">{{ currentNav?.meta }}</p>
            <h1>{{ currentNav?.label }}</h1>
          </div>
          <div class="top-actions">
            <span class="scope-pill">角色：{{ me.role_codes?.join(" / ") }}</span>
            <button v-if="view === 'orders' && can('export')" class="export-btn" @click="exportOrders"><Download :size="16" /> 导出</button>
          </div>
        </header>

        <section class="command-status" aria-label="系统状态">
          <div class="status-live"><span class="status-dot"></span><b>服务在线</b><small>ONLINE</small></div>
          <div class="status-item"><ShieldCheck :size="16" /><span>数据范围</span><b>{{ scopeSummary }}</b></div>
          <div class="status-item"><Database :size="16" /><span>当前周期</span><b>{{ filters.start_time }} — {{ filters.end_time }}</b></div>
          <div class="status-item"><Activity :size="16" /><span>最近刷新</span><b>{{ lastLoadedLabel }}</b></div>
          <button class="refresh-btn" type="button" :disabled="loading" @click="loadCurrent(true)"><RefreshCw :size="16" :class="{ spinning: loading }" /> 刷新</button>
        </section>

        <div v-if="pageError" class="page-alert" role="alert">
          <CircleAlert :size="18" /><span>{{ pageError }}</span><button type="button" aria-label="关闭错误提示" @click="pageError = ''">×</button>
        </div>

        <form v-if="['dashboard', 'commerce', 'orders', 'products', 'shops'].includes(view)" class="filter-suite" @submit.prevent="loadCurrent(true)">
          <div class="range-control">
            <span>订单日期</span>
            <button type="button" @click="rangeOpen = !rangeOpen">{{ filters.start_time }} 至 {{ filters.end_time }}</button>
            <div v-if="rangeOpen" class="range-pop">
              <nav><button v-for="p in presets" :key="p[0]" type="button" @click="applyPreset(p[0])">{{ p[1] }}</button></nav>
              <div class="range-custom">
                <label>开始时间<input type="date" v-model="filters.start_time" /></label>
                <b>至</b>
                <label>结束时间<input type="date" v-model="filters.end_time" /></label>
                <button class="primary" type="button" @click="rangeOpen=false; loadCurrent(true)">应用</button>
              </div>
            </div>
          </div>
          <label>部门<input v-model="filters.dept" placeholder="全部" /></label>
          <label>平台<input v-model="filters.platform" placeholder="全部" /></label>
          <label>店铺<input v-model="filters.shop_name" placeholder="全部" /></label>
          <label v-if="['commerce','products'].includes(view)">大类<input v-model="filters.category" placeholder="全部" /></label>
          <label v-if="['commerce','products'].includes(view)">货品分类<input v-model="filters.product_classification" placeholder="全部" /></label>
          <label v-if="['commerce','orders','products'].includes(view)">产品/SKU<input v-model="filters.product" placeholder="名称、货号、SKU" /></label>
          <label v-if="view === 'orders'">订单号<input v-model="filters.order_no" placeholder="订单编号" /></label>
          <div class="filter-actions">
            <button class="ghost" type="button" @click="resetFilters">重置</button>
            <button class="primary" type="submit">执行筛选</button>
          </div>
        </form>

        <section v-if="loading" class="loading-panel">正在载入数据...</section>

        <template v-else>
          <section v-if="view === 'commerce'" class="commerce-board">
            <section class="commerce-toolbar">
              <div>
                <p class="kicker">ECOMMERCE OPERATIONS</p>
                <h2>电商经营驾驶舱</h2>
              </div>
              <div class="switch-group">
                <button v-for="item in commerceDimensions" :key="item.key" :class="{ active: commerce.dimension === item.key }" @click="setCommerceDimension(item.key)">{{ item.label }}</button>
              </div>
              <div class="switch-group">
                <button v-for="item in commerceMetrics" :key="item.key" :class="{ active: commerce.metric === item.key }" @click="setCommerceMetric(item.key)">{{ item.label }}</button>
              </div>
            </section>

            <section class="metric-grid commerce-metrics">
              <article><span>销售额</span><strong>{{ Money(commerce.summary.revenue) }}</strong></article>
              <article><span>利润</span><strong :class="{ loss: Number(commerce.summary.profit || 0) < 0 }">{{ Money(commerce.summary.profit) }}</strong></article>
              <article><span>利润率</span><strong>{{ Money(commerce.summary.profit_rate) }}%</strong></article>
              <article><span>订单数</span><strong>{{ commerce.summary.orders || 0 }}</strong></article>
              <article><span>客单价</span><strong>{{ Money(commerce.summary.avg_order_value) }}</strong></article>
            </section>

            <section class="chart-grid">
              <div class="panel">
                <div class="panel-title"><h2>月度经营趋势</h2><span>销售额 / 利润 / 订单</span></div>
                <div class="trend-strip">
                  <article v-for="row in commerce.trend_rows" :key="row.month">
                    <span>{{ row.month }}</span>
                    <div><i :style="{ height: commerceTrendHeight(row.revenue) }"></i></div>
                    <b>{{ Money(row.revenue) }}</b>
                    <small>利润 {{ Money(row.profit) }} / {{ row.orders || 0 }} 单</small>
                  </article>
                  <div v-if="!commerce.trend_rows.length" class="empty-state">暂无趋势数据</div>
                </div>
              </div>
              <div class="panel">
                <div class="panel-title"><h2>{{ currentCommerceDimension.label }}排行</h2><span>按{{ currentCommerceMetric.label }}排序</span></div>
                <div class="commerce-rank">
                  <article v-for="row in commerce.dimension_rows.slice(0, 12)" :key="commerceRowLabel(row)">
                    <div><strong>{{ commerceRowLabel(row) }}</strong><small>占比 {{ Money(row.revenue_share_pct) }}% / {{ row.orders || 0 }} 单</small></div>
                    <span><i :class="{ negative: Number(row[commerce.metric] || 0) < 0 }" :style="{ width: commerceRankWidth(row[commerce.metric]) }"></i></span>
                    <b>{{ formatSmartValue(row[commerce.metric], commerce.metric) }}</b>
                  </article>
                  <div v-if="!commerce.dimension_rows.length" class="empty-state">暂无排行数据</div>
                </div>
              </div>
            </section>

            <section class="panel">
              <div class="panel-title"><h2>低利润风险清单</h2><span>亏损或利润率低于 10%</span></div>
              <table>
                <thead><tr><th>产品</th><th>店铺</th><th>销售额</th><th>销量</th><th>利润</th><th>利润率</th><th>订单数</th></tr></thead>
                <tbody>
                  <tr v-for="row in commerce.risk_rows" :key="row.product_no + row.shop_name">
                    <td><b>{{ row.product_name }}</b><small>{{ row.product_classification || "未分类" }} / {{ row.product_no }}</small></td>
                    <td>{{ row.shop_name }}</td>
                    <td>{{ Money(row.revenue) }}</td>
                    <td>{{ Money(row.qty) }}</td>
                    <td :class="{ loss: Number(row.profit || 0) < 0 }">{{ Money(row.profit) }}</td>
                    <td>{{ Money(row.profit_rate) }}%</td>
                    <td>{{ row.orders || 0 }}</td>
                  </tr>
                  <tr v-if="!commerce.risk_rows.length"><td colspan="7">暂无低利润风险项</td></tr>
                </tbody>
              </table>
            </section>
          </section>

          <section v-if="view === 'smart'" class="smart-layout">
            <section class="panel smart-query">
              <div class="panel-title"><h2>自然语言分析</h2><span>生成受控 SQL 并返回图表</span></div>
              <div class="smart-query-body">
                <textarea v-model="smart.question" placeholder="例如：今年1-5月各产品销售额占比，按销售额排序"></textarea>
                <div class="smart-actions">
                  <button class="primary" :disabled="smart.busy" @click="askSmart"><Sparkles :size="16" /> {{ smart.busy ? "分析中..." : "开始分析" }}</button>
                  <button v-for="example in smartExamples" :key="example" class="ghost" type="button" @click="smart.question = example; askSmart()">{{ example }}</button>
                </div>
                <div v-if="smart.error" class="alert">{{ smart.error }}</div>
              </div>
            </section>

            <section v-if="smart.result" class="panel smart-answer">
              <div class="panel-title"><h2>分析结论</h2><span>{{ smart.result.parser === "ark" ? "Ark 解析" : "规则解析" }} / {{ smart.result.filters.start_time }} 至 {{ smart.result.filters.end_time }}</span></div>
              <div class="smart-summary">{{ smart.result.answer }}</div>
            </section>

            <section v-if="smart.result" class="chart-grid">
              <div class="panel">
                <div class="panel-title"><h2>{{ smart.result.chart.metric_label }}图表</h2><span>{{ smart.result.chart.type }}</span></div>
                <div v-if="smart.result.chart.type === 'line'" class="smart-line-chart">
                  <svg viewBox="0 0 720 240" role="img" :aria-label="`${smart.result.chart.metric_label}趋势图`">
                    <line v-for="y in [40, 80, 120, 160, 200]" :key="y" class="line-grid" x1="32" :y1="y" x2="688" :y2="y" />
                    <polygon v-if="smartLinePoints.length" class="line-area" :points="smartLineArea" />
                    <polyline v-if="smartLinePoints.length" class="line-path" :points="smartLinePolyline" />
                    <circle v-for="point in smartLinePoints" :key="point.label" class="line-point" :cx="point.x" :cy="point.y" r="4">
                      <title>{{ point.label }}：{{ formatSmartValue(point.value, smart.result.chart.metric) }}</title>
                    </circle>
                  </svg>
                  <div class="line-axis-labels"><span v-for="point in smartLinePoints" :key="point.label">{{ point.label }}</span></div>
                </div>
                <div v-else-if="smart.result.chart.type === 'pie'" class="smart-pie-wrap">
                  <div class="smart-pie" :style="smartPieStyle"></div>
                  <div class="smart-legend">
                    <div v-for="(point, index) in smart.result.chart.points.slice(0, 12)" :key="point.label"><i :style="{ background: chartColors[index % chartColors.length] }"></i><span>{{ point.label }}</span><b>{{ Number(point.value || 0).toFixed(2) }}%</b></div>
                  </div>
                </div>
                <div v-else class="smart-bars">
                  <div v-for="point in smart.result.chart.points" :key="point.label" class="smart-bar">
                    <span>{{ point.label }}</span>
                    <div><i :class="{ negative: Number(point.value || 0) < 0 }" :style="{ width: smartBarWidth(point.value) }"></i></div>
                    <b>{{ formatSmartValue(point.value, smart.result.chart.metric) }}</b>
                  </div>
                </div>
              </div>
              <div class="panel">
                <div class="panel-title"><h2>生成 SQL</h2><span>只读聚合查询</span></div>
                <details class="sql-box" open>
                  <summary>查看 SQL 与参数</summary>
                  <pre>{{ smart.result.sql }}</pre>
                  <pre>{{ JSON.stringify(smart.result.sql_params, null, 2) }}</pre>
                </details>
              </div>
            </section>

            <section v-if="smart.result" class="panel">
              <div class="panel-title"><h2>查询结果</h2><span>最多展示 {{ smart.result.rows.length }} 行</span></div>
              <table>
                <thead><tr><th v-for="col in smartColumns" :key="col">{{ smartColumnLabel(col) }}</th></tr></thead>
                <tbody>
                  <tr v-for="(row, index) in smart.result.rows" :key="index">
                    <td v-for="col in smartColumns" :key="col">{{ formatSmartCell(row[col], col) }}</td>
                  </tr>
                  <tr v-if="!smart.result.rows.length"><td :colspan="smartColumns.length || 1">暂无数据</td></tr>
                </tbody>
              </table>
            </section>
          </section>

          <section v-if="view === 'dashboard'">
            <section class="metric-grid dashboard-metrics">
              <article class="metric-card">
                <div class="metric-head"><span>销售额</span><TrendingUp :size="17" /></div>
                <strong>¥ {{ Money(dashboard.summary.revenue) }}</strong>
                <small :class="['metric-change', changeTone(dashboard.comparison.revenue_change_pct)]">{{ changeText(dashboard.comparison.revenue_change_pct) }} 较前周期</small>
              </article>
              <article class="metric-card">
                <div class="metric-head"><span>经营利润</span><Activity :size="17" /></div>
                <strong :class="{ loss: Number(dashboard.summary.profit || 0) < 0 }">¥ {{ Money(dashboard.summary.profit) }}</strong>
                <small :class="['metric-change', changeTone(dashboard.comparison.profit_change_pct)]">{{ changeText(dashboard.comparison.profit_change_pct) }} 较前周期</small>
              </article>
              <article class="metric-card">
                <div class="metric-head"><span>利润率</span><Gauge :size="17" /></div>
                <strong :class="{ loss: Number(dashboard.summary.profit_rate || 0) < 0 }">{{ Money(dashboard.summary.profit_rate) }}%</strong>
                <small class="metric-change neutral">收入利润结构</small>
              </article>
              <article class="metric-card">
                <div class="metric-head"><span>订单数</span><ShoppingBag :size="17" /></div>
                <strong>{{ dashboard.summary.orders || 0 }}</strong>
                <small :class="['metric-change', changeTone(dashboard.comparison.orders_change_pct)]">{{ changeText(dashboard.comparison.orders_change_pct) }} 较前周期</small>
              </article>
              <article class="metric-card">
                <div class="metric-head"><span>客单价</span><BarChart3 :size="17" /></div>
                <strong>¥ {{ Money(dashboard.summary.avg_order_value) }}</strong>
                <small class="metric-change neutral">按去重订单计算</small>
              </article>
              <article class="metric-card">
                <div class="metric-head"><span>客户覆盖</span><Users :size="17" /></div>
                <strong>{{ dashboard.summary.customers || 0 }}</strong>
                <small class="metric-change neutral">{{ dashboard.summary.products || 0 }} 个货品</small>
              </article>
            </section>

            <section class="dashboard-main">
              <div class="panel">
                <div class="panel-title"><h2>经营脉冲</h2><span>{{ dashboard.trend.granularity === 'day' ? '按日' : '按月' }} · 销售额 / 利润 / 订单</span></div>
                <div class="trend-chart">
                  <article v-for="row in dashboard.trend.rows" :key="row.period" class="trend-column">
                    <div class="trend-value"><b>¥{{ compactNumber(row.revenue) }}</b><small>{{ row.orders || 0 }} 单</small></div>
                    <div class="trend-bar"><i :style="{ height: dashboardTrendHeight(row.revenue) }"></i></div>
                    <span>{{ row.period }}</span>
                    <small :class="{ loss: Number(row.profit || 0) < 0 }">利润 {{ compactNumber(row.profit) }}</small>
                  </article>
                  <div v-if="!dashboard.trend.rows.length" class="empty-state">当前周期暂无趋势数据</div>
                </div>
              </div>

              <div class="panel">
                <div class="panel-title"><h2>平台结构</h2><span>销售额占比</span></div>
                <div class="platform-stack">
                  <article v-for="row in dashboard.platform_rows" :key="row.platform" class="platform-row">
                    <div><strong>{{ row.platform || '未分类平台' }}</strong><small>{{ row.orders || 0 }} 单 · 利润 {{ Money(row.profit) }}</small></div>
                    <div class="platform-track"><i :style="{ width: `${Math.max(2, Number(row.revenue_share_pct || 0))}%` }"></i></div>
                    <b>{{ Money(row.revenue_share_pct) }}%</b>
                  </article>
                  <div v-if="!dashboard.platform_rows.length" class="empty-state">暂无平台结构数据</div>
                </div>
              </div>
            </section>

            <section class="dashboard-main dashboard-lower">
              <div class="panel">
                <div class="panel-title"><h2>TOP 产品矩阵</h2><span>收入贡献与利润质量</span></div>
                <div class="table-scroll">
                  <table>
                    <thead><tr><th>产品</th><th>分类</th><th>货号</th><th>销售额</th><th>收入占比</th><th>利润</th><th>利润率</th></tr></thead>
                    <tbody>
                      <tr v-for="row in dashboard.top_products" :key="row.product_no">
                        <td><b>{{ row.product_name || '未命名产品' }}</b><small>{{ Money(row.qty) }} 件</small></td>
                        <td>{{ row.category || '未分类' }}<small>{{ row.product_classification || '未分类' }}</small></td>
                        <td>{{ row.product_no }}</td><td>¥ {{ Money(row.revenue) }}</td><td>{{ Money(row.revenue_share_pct) }}%</td>
                        <td :class="{ loss: Number(row.profit || 0) < 0 }">¥ {{ Money(row.profit) }}</td><td>{{ Money(row.profit_rate) }}%</td>
                      </tr>
                      <tr v-if="!dashboard.top_products?.length"><td colspan="7">暂无数据</td></tr>
                    </tbody>
                  </table>
                </div>
              </div>

              <div class="panel">
                <div class="panel-title"><h2>数据与风险信号</h2><span>无需额外扫描</span></div>
                <div class="signal-grid">
                  <article class="signal-card compact"><Database :size="18" /><span>数据截至</span><strong>{{ formatDateTime(dashboard.summary.latest_ship_time) }}</strong></article>
                  <article class="signal-card" :class="{ loss: Number(dashboard.summary.loss_orders || 0) > 0 }"><AlertTriangle :size="18" /><span>亏损订单</span><strong>{{ dashboard.summary.loss_orders || 0 }}</strong></article>
                  <article class="signal-card"><FileSpreadsheet :size="18" /><span>明细行数</span><strong>{{ dashboard.summary.detail_rows || 0 }}</strong></article>
                  <article class="signal-card compact"><CalendarRange :size="18" /><span>对比周期</span><strong>{{ dashboard.comparison.start_time }}<br>{{ dashboard.comparison.end_time }}</strong></article>
                </div>
              </div>
            </section>
          </section>
          <section v-if="view === 'orders'" class="panel">
            <div class="panel-title"><h2>订单明细</h2><span>最多显示 200 行</span></div>
            <table>
              <thead><tr><th>发货时间</th><th>订单</th><th>来源</th><th>客户</th><th>地区</th><th>收货地址</th><th>平台/店铺</th><th>产品</th><th>数量</th><th>应收</th><th>利润</th></tr></thead>
                <tbody>
                  <tr v-for="row in orders.rows" :key="row.id">
                    <td>{{ row.ship_time }}</td><td>{{ row.order_no }}</td><td>{{ row.order_source }}</td>
                    <td><b>{{ row.customer_name }}</b><small>{{ row.customer_no }}</small></td>
                    <td><b>{{ row.province }}</b><small>{{ row.city }}<span v-if="row.district"> / {{ row.district }}</span></small></td>
                    <td><b>{{ row.receiver_name || '-' }}</b><small>{{ row.receiver_phone || '' }}</small><small>{{ row.receiver_address || '-' }}</small></td>
                    <td>{{ row.platform }}<small>{{ row.shop_name }}</small></td>
                    <td><b>{{ row.product_name }}</b><small>{{ row.category }} / {{ row.product_classification || "未分类" }} / {{ row.product_no }}</small></td>
                    <td>{{ Money(row.qty) }}</td><td>{{ Money(row.share_receivable) }}</td><td>{{ Money(row.profit) }}</td>
                  </tr>
                  <tr v-if="!orders.rows?.length"><td colspan="11">暂无数据</td></tr>
              </tbody>
            </table>
          </section>

          <section v-if="view === 'imports'">
            <section v-if="latestImportLog" :class="['import-gate', latestImportIsTerminal ? 'terminal' : latestValidUncommittedImport ? 'pending' : 'settled']">
              <div class="import-gate-icon"><component :is="latestImportIsTerminal ? AlertTriangle : latestValidUncommittedImport ? CircleAlert : CheckCircle2" :size="20" /></div>
              <div>
                <p>{{ latestImportIsTerminal ? '上一批校验已终止' : latestValidUncommittedImport ? '上一批待确认入库' : '上一批已完成' }}</p>
                <strong>{{ latestImportLog.file_name || latestImportLog.batch_no }}</strong>
                <small>{{ importGateDescription }}</small>
              </div>
              <div class="import-gate-actions">
                <button class="ghost" @click="openImport(latestImportLog.batch_no)">查看批次</button>
                <button v-if="latestValidUncommittedImport" class="primary" @click="openImport(latestImportLog.batch_no)">去确认入库</button>
              </div>
            </section>
            <section class="import-layout">
              <div class="panel upload-card">
                <UploadCloud :size="28" />
                <h2>上传月度 Excel</h2>
                <p class="upload-hint">先校验，后入库。校验异常的批次会终止，不会写入正式订单。</p>
                <div v-if="importMessage.text" :class="importMessage.type === 'error' ? 'alert' : 'notice'">{{ importMessage.text }}</div>
                <input ref="importFileInput" type="file" accept=".xlsx,.xlsm" @change="selectedFile = $event.target.files[0]" />
                <div v-if="importBusy || uploadProgress > 0" class="upload-progress">
                  <span :style="{ width: `${uploadProgress}%` }"></span>
                  <b>{{ uploadProgress ? `${uploadProgress}%` : '等待服务器接收' }}</b>
                </div>
                <button class="primary" :disabled="importBusy" @click="requestImportUpload">
                  {{ importBusy ? "正在处理..." : "上传并校验" }}
                </button>
                <a class="export-btn" href="/api/imports/template"><Download :size="16" /> 下载导入模板</a>
              </div>
              <div class="panel">
                <div class="panel-title"><h2>导入批次</h2><span>最近 50 条</span></div>
                <table>
                  <thead><tr><th>批次</th><th>文件</th><th>状态</th><th>总行</th><th>异常</th><th>时间</th></tr></thead>
                  <tbody>
                    <tr v-for="log in imports.logs" :key="log.batch_no" tabindex="0" @click="openImport(log.batch_no)" @keydown.enter="openImport(log.batch_no)">
                      <td>{{ log.batch_no }}</td><td>{{ log.file_name }}</td><td><em>{{ importStatusLabel(log.status) }}</em></td>
                      <td>{{ log.total_rows }}</td><td>{{ log.fail_rows }}</td><td>{{ log.import_time }}</td>
                    </tr>
                    <tr v-if="!imports.logs?.length"><td colspan="6">暂无导入记录</td></tr>
                  </tbody>
                </table>
              </div>
            </section>
            <section v-if="importDetail" class="panel">
              <div class="panel-title">
                <h2>{{ importDetail.log.batch_no }}</h2>
                <button v-if="importDetail.log.status === 'validated' && importDetail.log.fail_rows === 0 && importDetail.log.total_rows > 0" class="primary" :disabled="commitBusy" @click="commitImport(importDetail.log.batch_no)">{{ commitBusy ? '正在入库...' : '确认入库' }}</button>
              </div>
              <table>
                <thead><tr><th>行号</th><th>订单</th><th>客户</th><th>地址</th><th>产品</th><th>利润</th><th>异常</th><th>提示</th></tr></thead>
                <tbody>
                  <tr v-for="row in importDetail.rows" :key="row.id">
                    <td>{{ row.row_no }}</td><td>{{ row.order_no }}</td><td>{{ row.customer_name }} / {{ row.customer_no }}</td>
                    <td>{{ row.receiver_address || '-' }}</td>
                    <td>{{ row.product_name }}</td><td>{{ Money(row.profit) }}</td><td>{{ row.error_message }}</td><td>{{ row.warning_message }}</td>
                  </tr>
                </tbody>
              </table>
            </section>
            <div v-if="uploadReminderOpen" class="import-reminder-backdrop" role="presentation" @click.self="cancelImportReminder">
              <section class="import-reminder" role="alertdialog" aria-modal="true" aria-labelledby="import-reminder-title">
                <div class="import-reminder-mark"><CircleAlert :size="24" /></div>
                <div>
                  <p class="kicker">IMPORT CHECKPOINT</p>
                  <h2 id="import-reminder-title">上一批已校验通过，但尚未入库</h2>
                  <p>“{{ latestValidUncommittedImport?.file_name || latestValidUncommittedImport?.batch_no }}”没有异常行。继续上传不会自动提交它，请确认这是你的预期操作。</p>
                </div>
                <div class="import-reminder-actions">
                  <button class="ghost" @click="openPendingImport">先处理上一批</button>
                  <button class="primary" @click="continueImportUpload">继续上传新文件</button>
                </div>
              </section>
            </div>
          </section>

          <section v-if="view === 'products'">
            <section class="chart-grid">
              <div class="panel">
                <div class="panel-title"><h2>大类收入结构</h2><span>分类维度</span></div>
                <div class="executive-bars">
                  <div v-for="row in products.category_rows" :key="row.category" class="exec-bar-row">
                    <div class="exec-label"><strong>{{ row.category }}</strong><small>{{ row.product_count }} 个货品</small></div>
                    <div class="exec-track"><i :style="{ width: barWidth(row.revenue, maxCategoryRevenue) }"></i></div>
                    <div class="exec-value">{{ Money(row.revenue) }}</div>
                  </div>
                  <div v-if="!products.category_rows?.length" class="empty-state">暂无大类数据</div>
                </div>
              </div>
              <div class="panel">
                <div class="panel-title"><h2>产品收入与利润</h2><span>多维对比</span></div>
                <div class="profit-matrix">
                  <article v-for="row in products.rows.slice(0, 10)" :key="row.product_no">
                    <div><strong>{{ row.product_name }}</strong><small>{{ row.category }} / {{ row.product_classification || "未分类" }} / {{ row.product_no }}</small></div>
                    <div class="matrix-bars">
                      <span><i :style="{ width: barWidth(row.revenue, maxProductRevenue) }"></i></span>
                      <span class="profit"><i :class="{ loss: row.profit < 0 }" :style="{ width: barWidth(Math.abs(Number(row.profit || 0)), Math.max(Math.abs(Number(row.revenue || 0)), 1)) }"></i></span>
                    </div>
                    <div class="matrix-values"><b>{{ Money(row.revenue) }}</b><em>{{ Money(row.profit) }}</em></div>
                  </article>
                  <div v-if="!products.rows?.length" class="empty-state">暂无产品数据</div>
                </div>
              </div>
            </section>
            <section class="panel">
              <div class="panel-title"><h2>产品明细排行</h2><span>按销售额排序</span></div>
              <table>
                <thead><tr><th>大类</th><th>货品分类</th><th>产品</th><th>货号</th><th>销量</th><th>销售额</th><th>成本</th><th>利润</th><th>利润率</th></tr></thead>
                <tbody>
                  <tr v-for="row in products.rows" :key="row.product_no">
                    <td><em>{{ row.category }}</em></td><td>{{ row.product_classification || "未分类" }}</td><td>{{ row.product_name }}</td><td>{{ row.product_no }}</td>
                    <td>{{ Money(row.qty) }}</td><td>{{ Money(row.revenue) }}</td><td>{{ Money(row.cost) }}</td><td>{{ Money(row.profit) }}</td><td>{{ Money(row.profit_rate) }}%</td>
                  </tr>
                  <tr v-if="!products.rows?.length"><td colspan="9">暂无数据</td></tr>
                </tbody>
              </table>
            </section>
          </section>

          <section v-if="view === 'shops'" class="panel">
            <div class="panel-title"><h2>店铺平台分析</h2><span>渠道经营表现</span></div>
            <table>
              <thead><tr><th>平台</th><th>店铺</th><th>销量</th><th>销售额</th><th>利润</th><th>利润率</th></tr></thead>
              <tbody>
                <tr v-for="row in shops.rows" :key="row.platform + row.shop_name">
                  <td>{{ row.platform }}</td><td>{{ row.shop_name }}</td><td>{{ Money(row.qty) }}</td><td>{{ Money(row.revenue) }}</td><td>{{ Money(row.profit) }}</td><td>{{ Money(row.profit_rate) }}%</td>
                </tr>
                <tr v-if="!shops.rows?.length"><td colspan="6">暂无数据</td></tr>
              </tbody>
            </table>
          </section>

          <section v-if="view === 'settings'" class="settings-grid">
            <div class="panel">
              <div class="panel-title"><h2>用户</h2><span>账号与角色</span></div>
              <table>
                <thead><tr><th>账号</th><th>姓名</th><th>角色</th><th>状态</th></tr></thead>
                <tbody><tr v-for="user in settings.users" :key="user.id"><td>{{ user.username }}</td><td>{{ user.display_name }}</td><td>{{ user.roles }}</td><td>{{ user.is_active ? '启用' : '停用' }}</td></tr></tbody>
              </table>
            </div>
            <div class="role-panel">
              <article v-for="role in settings.roles" :key="role.id" class="role-card">
                <h3>{{ role.role_name }}</h3><small>{{ role.permissions }}</small>
                <label>部门范围<input v-model="role.scopes.dept" /></label>
                <label>平台范围<input v-model="role.scopes.platform" /></label>
                <label>店铺范围<input v-model="role.scopes.shop" /></label>
                <button class="primary" @click="saveRole(role)">保存</button>
              </article>
            </div>
          </section>
        </template>
      </main>
    </template>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from "vue";
import {
  Activity,
  AlertTriangle,
  BarChart3,
  Box,
  Building2,
  CalendarRange,
  CheckCircle2,
  CircleAlert,
  Database,
  Download,
  FileSpreadsheet,
  Gauge,
  LayoutDashboard,
  LineChart,
  RefreshCw,
  ShieldCheck,
  Sparkles,
  Settings,
  ShoppingBag,
  TrendingUp,
  UploadCloud,
  Users
} from "lucide-vue-next";

const today = new Date();
const pad = (n) => `${n}`.padStart(2, "0");
const fmt = (d) => `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
const addDays = (d, n) => new Date(d.getFullYear(), d.getMonth(), d.getDate() + n);
const addMonths = (d, n) => new Date(d.getFullYear(), d.getMonth() + n, 1);
const startOfMonth = (d) => new Date(d.getFullYear(), d.getMonth(), 1);
function Money(value) {
  return Number(value || 0).toLocaleString("zh-CN", { maximumFractionDigits: 2 });
}

const lastMonthStart = addMonths(startOfMonth(today), -1);
const lastMonthEnd = addDays(startOfMonth(today), -1);

const view = ref("dashboard");
const loading = ref(false);
const error = ref("");
const pageError = ref("");
const authBusy = ref(false);
const rangeOpen = ref(false);
const selectedFile = ref(null);
const importFileInput = ref(null);
const importBusy = ref(false);
const commitBusy = ref(false);
const uploadProgress = ref(0);
const importMessage = reactive({ type: "", text: "" });
const uploadReminderOpen = ref(false);
const lastLoadedAt = ref(null);
let activeLoadController = null;
let importPollToken = 0;
const loadedKeys = new Map();
const me = reactive({ authenticated: false, permissions: [], role_codes: [] });
const loginForm = reactive({ username: "admin", password: "" });
const filters = reactive({
  start_time: fmt(lastMonthStart),
  end_time: fmt(lastMonthEnd),
  dept: "",
  platform: "",
  shop_name: "",
  category: "",
  product_classification: "",
  product: "",
  order_no: ""
});

const dashboard = reactive({ summary: {}, comparison: {}, trend: { granularity: "month", rows: [] }, platform_rows: [], top_products: [], meta: {} });
const commerce = reactive({ summary: {}, trend_rows: [], dimension_rows: [], risk_rows: [], dimension: "product", metric: "revenue" });
const orders = reactive({ rows: [] });
const imports = reactive({ logs: [] });
const importDetail = ref(null);
const products = reactive({ rows: [], category_rows: [] });
const shops = reactive({ rows: [] });
const settings = reactive({ users: [], roles: [] });
const smart = reactive({
  question: "今年1-5月各产品销售额占比，按销售额排序",
  result: null,
  busy: false,
  error: ""
});
const smartExamples = [
  "今年1-5月各产品销售额占比",
  "今年1-5月各店铺利润排名",
  "今年1-5月按月销售额趋势",
  "今年1-5月各平台订单数和销售额"
];
const commerceDimensions = [
  { key: "product", label: "产品" },
  { key: "shop", label: "店铺" },
  { key: "platform", label: "平台" },
  { key: "category", label: "大类" },
  { key: "product_classification", label: "货品分类" },
  { key: "province", label: "省份" }
];
const commerceMetrics = [
  { key: "revenue", label: "销售额" },
  { key: "profit", label: "利润" },
  { key: "qty", label: "销量" },
  { key: "orders", label: "订单数" },
  { key: "profit_rate", label: "利润率" }
];

const nav = [
  { key: "dashboard", label: "数据总览", meta: "DATA CENTER OVERVIEW", icon: LayoutDashboard, permission: "view" },
  { key: "commerce", label: "多维驾驶舱", meta: "ECOMMERCE COMMAND", icon: BarChart3, permission: "analytics" },
  { key: "orders", label: "订单明细", meta: "ORDER LEDGER", icon: ShoppingBag, permission: "view" },
  { key: "products", label: "产品分析", meta: "PRODUCT INTELLIGENCE", icon: LineChart, permission: "analytics" },
  { key: "shops", label: "店铺平台", meta: "CHANNEL PERFORMANCE", icon: Building2, permission: "analytics" },
  { key: "smart", label: "智能分析", meta: "NATURAL LANGUAGE SQL", icon: Sparkles, permission: "analytics" },
  { key: "imports", label: "数据导入", meta: "IMPORT CONTROL", icon: FileSpreadsheet, permission: "import" },
  { key: "settings", label: "权限配置", meta: "ACCESS GOVERNANCE", icon: Settings, permission: "settings" }
];
const can = (permission) => me.permissions?.includes("admin") || me.permissions?.includes(permission);
const visibleNav = computed(() => nav.filter((item) => can(item.permission)));
const currentNav = computed(() => nav.find((item) => item.key === view.value));
const scopeSummary = computed(() => {
  if (Object.values(me.all_scopes || {}).every(Boolean)) return "全域授权";
  const scopes = me.scopes || {};
  const total = ["dept", "platform", "shop"].reduce((sum, key) => sum + (scopes[key]?.length || 0), 0);
  return total ? `${total} 个授权范围` : "受限范围";
});
const lastLoadedLabel = computed(() => lastLoadedAt.value
  ? lastLoadedAt.value.toLocaleTimeString("zh-CN", { hour12: false })
  : "等待首次查询");
const maxCategoryRevenue = computed(() => Math.max(...products.category_rows.map((row) => Number(row.revenue || 0)), 1));
const maxProductRevenue = computed(() => Math.max(...products.rows.slice(0, 10).map((row) => Number(row.revenue || 0)), 1));
const maxDashboardTrendRevenue = computed(() => Math.max(...dashboard.trend.rows.map((row) => Number(row.revenue || 0)), 1));
const maxCommerceTrendRevenue = computed(() => Math.max(...commerce.trend_rows.map((row) => Number(row.revenue || 0)), 1));
const maxCommerceRankValue = computed(() => Math.max(...commerce.dimension_rows.map((row) => Math.abs(Number(row[commerce.metric] || 0))), 1));
const currentCommerceDimension = computed(() => commerceDimensions.find((item) => item.key === commerce.dimension) || commerceDimensions[0]);
const currentCommerceMetric = computed(() => commerceMetrics.find((item) => item.key === commerce.metric) || commerceMetrics[0]);
const smartColumns = computed(() => smart.result?.rows?.length ? Object.keys(smart.result.rows[0]) : []);
const smartMaxValue = computed(() => Math.max(...(smart.result?.chart?.points || []).map((point) => Math.abs(Number(point.value || 0))), 1));
const chartColors = ["#45e0c1", "#8de074", "#e7b85f", "#6ba8ff", "#ef6a6a", "#a98be8", "#74c8d8", "#d6dc73", "#df8f5d", "#cf77b8", "#91a9dd", "#5dc490"];
const smartPieStyle = computed(() => {
  const points = smart.result?.chart?.points || [];
  let cursor = 0;
  const segments = points.map((point, index) => {
    const next = cursor + Math.max(0, Number(point.value || 0));
    const segment = `${chartColors[index % chartColors.length]} ${cursor}% ${next}%`;
    cursor = next;
    return segment;
  });
  return { background: `conic-gradient(${segments.join(", ") || "#203235 0% 100%"})` };
});
const smartLinePoints = computed(() => {
  const points = smart.result?.chart?.points || [];
  if (!points.length) return [];
  const values = points.map((point) => Number(point.value || 0));
  const min = Math.min(0, ...values);
  const max = Math.max(0, ...values);
  const span = Math.max(max - min, 1);
  return points.map((point, index) => ({
    label: point.label,
    value: Number(point.value || 0),
    x: points.length === 1 ? 360 : 32 + index * (656 / (points.length - 1)),
    y: 200 - ((Number(point.value || 0) - min) / span) * 160
  }));
});
const smartLinePolyline = computed(() => smartLinePoints.value.map((point) => `${point.x},${point.y}`).join(" "));
const smartLineArea = computed(() => smartLinePoints.value.length
  ? `32,200 ${smartLinePolyline.value} 688,200`
  : "");
const latestImportLog = computed(() => imports.logs?.[0] || null);
const latestImportIsTerminal = computed(() => {
  const log = latestImportLog.value;
  return Boolean(log && (log.status === "failed" || (log.status === "validated" && Number(log.fail_rows || 0) > 0)));
});
const latestValidUncommittedImport = computed(() => {
  const log = latestImportLog.value;
  if (!log || log.status !== "validated" || Number(log.fail_rows || 0) > 0 || Number(log.total_rows || 0) <= 0) return null;
  return log;
});
const importGateDescription = computed(() => {
  const log = latestImportLog.value;
  if (!log) return "";
  if (latestImportIsTerminal.value) return `${log.remark || "存在校验异常"}。可直接上传修正后的文件。`;
  if (latestValidUncommittedImport.value) return `共 ${log.total_rows} 行，校验通过。上传新文件前会再次提醒。`;
  return log.remark || `状态：${log.status}`;
});
const presets = [
  ["last7", "近7天"], ["last30", "近30天"], ["lastWeek", "上周"], ["thisMonth", "本月"], ["lastMonth", "上月"],
  ["quarter", "本季度"], ["firstHalf", "上半年"], ["secondHalf", "下半年"], ["lastYear", "近一年"], ["thisYear", "今年"]
];

function query() {
  return new URLSearchParams(Object.fromEntries(Object.entries(filters).filter(([, v]) => v))).toString();
}

function commerceQuery() {
  const params = new URLSearchParams(query());
  params.set("dimension", commerce.dimension);
  params.set("metric", commerce.metric);
  return params.toString();
}

async function api(path, options = {}) {
  const response = await fetch(path, { credentials: "same-origin", ...options });
  const contentType = response.headers.get("content-type") || "";
  const body = contentType.includes("application/json") ? await response.json() : {};
  if (!response.ok) {
    if (response.status === 401 && path !== "/api/me") {
      Object.assign(me, { authenticated: false, permissions: [], role_codes: [] });
    }
    throw new Error(body.detail || `请求失败（${response.status}）`);
  }
  return body.data ?? body;
}

async function refreshMe() {
  const data = await api("/api/me");
  Object.assign(me, data);
}

async function login() {
  error.value = "";
  authBusy.value = true;
  const form = new FormData();
  form.append("username", loginForm.username);
  form.append("password", loginForm.password);
  try {
    const data = await api("/api/login", { method: "POST", body: form });
    Object.assign(me, data);
    loadedKeys.clear();
    await loadCurrent(true);
  } catch (err) {
    error.value = err.message;
  } finally {
    authBusy.value = false;
  }
}

async function logout() {
  importPollToken += 1;
  activeLoadController?.abort();
  try {
    await api("/api/logout", { method: "POST" });
  } finally {
    loadedKeys.clear();
    Object.assign(me, { authenticated: false, permissions: [], role_codes: [], scopes: {}, all_scopes: {} });
  }
}

function currentLoadKey(targetView = view.value) {
  const base = ["dashboard", "commerce", "orders", "products", "shops"].includes(targetView) ? query() : "";
  const commerceState = targetView === "commerce" ? `:${commerce.dimension}:${commerce.metric}` : "";
  return `${targetView}:${base}${commerceState}`;
}

async function loadCurrent(force = false) {
  if (!me.authenticated) return;
  const targetView = view.value;
  if (targetView === "smart") return;
  const loadKey = currentLoadKey(targetView);
  if (!force && loadedKeys.get(targetView) === loadKey) return;
  activeLoadController?.abort();
  const controller = new AbortController();
  activeLoadController = controller;
  loading.value = true;
  pageError.value = "";
  try {
    const requestOptions = { signal: controller.signal };
    if (targetView === "dashboard") Object.assign(dashboard, await api(`/api/dashboard?${query()}`, requestOptions));
    if (targetView === "commerce") {
      const data = await api(`/api/analytics/commerce-dashboard?${commerceQuery()}`, requestOptions);
      commerce.summary = data.summary || {};
      commerce.trend_rows = data.trend_rows || [];
      commerce.dimension_rows = data.dimension_rows || [];
      commerce.risk_rows = data.risk_rows || [];
    }
    if (targetView === "orders") Object.assign(orders, await api(`/api/orders?${query()}`, requestOptions));
    if (targetView === "imports") Object.assign(imports, await api("/api/imports", requestOptions));
    if (targetView === "products") Object.assign(products, await api(`/api/analytics/products?${query()}`, requestOptions));
    if (targetView === "shops") Object.assign(shops, await api(`/api/analytics/shops?${query()}`, requestOptions));
    if (targetView === "settings") {
      const [users, roles] = await Promise.all([
        api("/api/settings/users", requestOptions),
        api("/api/settings/roles", requestOptions)
      ]);
      settings.users = users.users;
      settings.roles = roles.roles;
    }
    loadedKeys.set(targetView, loadKey);
    lastLoadedAt.value = new Date();
  } catch (err) {
    if (err.name !== "AbortError") pageError.value = err.message || "数据加载失败";
  } finally {
    if (activeLoadController === controller) {
      loading.value = false;
      activeLoadController = null;
    }
  }
}

function presetRange(name) {
  const now = new Date();
  const month = startOfMonth(now);
  const weekday = now.getDay() || 7;
  if (name === "last7") return [addDays(now, -6), now];
  if (name === "last30") return [addDays(now, -29), now];
  if (name === "lastWeek") {
    const start = addDays(now, -weekday - 6);
    return [start, addDays(start, 6)];
  }
  if (name === "thisMonth") return [month, now];
  if (name === "lastMonth") {
    const start = addMonths(month, -1);
    return [start, addDays(month, -1)];
  }
  if (name === "quarter") return [new Date(now.getFullYear(), Math.floor(now.getMonth() / 3) * 3, 1), now];
  if (name === "firstHalf") return [new Date(now.getFullYear(), 0, 1), new Date(now.getFullYear(), 5, 30)];
  if (name === "secondHalf") return [new Date(now.getFullYear(), 6, 1), new Date(now.getFullYear(), 11, 31)];
  if (name === "lastYear") return [addDays(now, -364), now];
  return [new Date(now.getFullYear(), 0, 1), now];
}

function applyPreset(name) {
  const [start, end] = presetRange(name);
  filters.start_time = fmt(start);
  filters.end_time = fmt(end);
  rangeOpen.value = false;
  loadCurrent(true);
}

function resetFilters() {
  Object.assign(filters, {
    start_time: fmt(lastMonthStart),
    end_time: fmt(lastMonthEnd),
    dept: "",
    platform: "",
    shop_name: "",
    category: "",
    product_classification: "",
    product: "",
    order_no: ""
  });
  loadCurrent(true);
}

function compactNumber(value) {
  return new Intl.NumberFormat("zh-CN", { notation: "compact", maximumFractionDigits: 1 }).format(Number(value || 0));
}

function formatDateTime(value) {
  if (!value) return "暂无数据";
  return String(value).replace("T", " ").slice(0, 16);
}

function changeText(value) {
  if (value === null || value === undefined) return "无同期基线";
  const amount = Number(value || 0);
  return `${amount >= 0 ? "+" : ""}${amount.toFixed(1)}%`;
}

function changeTone(value) {
  if (value === null || value === undefined || Number(value) === 0) return "neutral";
  return Number(value) > 0 ? "positive" : "negative";
}

function barWidth(value, max) {
  return `${Math.max(2, Math.min(100, Number(value || 0) / max * 100))}%`;
}

function smartBarWidth(value) {
  return `${Math.max(2, Math.min(100, Math.abs(Number(value || 0)) / smartMaxValue.value * 100))}%`;
}

function commerceTrendHeight(value) {
  return `${Math.max(6, Math.min(100, Number(value || 0) / maxCommerceTrendRevenue.value * 100))}%`;
}

function dashboardTrendHeight(value) {
  return `${Math.max(6, Math.min(100, Number(value || 0) / maxDashboardTrendRevenue.value * 100))}%`;
}

function commerceRankWidth(value) {
  return `${Math.max(2, Math.min(100, Math.abs(Number(value || 0)) / maxCommerceRankValue.value * 100))}%`;
}

function commerceRowLabel(row) {
  return row.product_name || row.shop_name || row.platform || row.category || row.product_classification || row.province || "未分类";
}

async function setCommerceDimension(key) {
  commerce.dimension = key;
  await loadCurrent();
}

async function setCommerceMetric(key) {
  commerce.metric = key;
  commerce.dimension_rows.sort((left, right) => Number(right[key] || 0) - Number(left[key] || 0));
}

function smartColumnLabel(key) {
  const labels = {
    month: "月份",
    category: "产品大类",
    product_classification: "货品分类",
    product_no: "货号",
    product_name: "产品",
    platform: "平台",
    shop_name: "店铺",
    dept: "部门",
    customer_no: "客户编号",
    customer_name: "客户",
    province: "省份",
    city: "城市",
    order_source: "订单来源",
    revenue: "销售额",
    qty: "销量",
    profit: "利润",
    cost: "成本",
    orders: "订单数",
    profit_rate: "利润率",
    revenue_share_pct: "销售额占比"
  };
  return labels[key] || key;
}

function formatSmartValue(value, key) {
  if (key === "revenue_share_pct" || key === "profit_rate") return `${Number(value || 0).toFixed(2)}%`;
  return Money(value);
}

function formatSmartCell(value, key) {
  if (value === null || value === undefined || value === "") return "-";
  if (["revenue", "qty", "profit", "cost", "orders", "profit_rate", "revenue_share_pct"].includes(key)) {
    return formatSmartValue(value, key);
  }
  return value;
}

async function askSmart() {
  smart.error = "";
  if (!smart.question.trim()) {
    smart.error = "请输入要分析的问题";
    return;
  }
  smart.busy = true;
  try {
    smart.result = await api("/api/analytics/ask", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question: smart.question })
    });
  } catch (err) {
    smart.error = err.message;
  } finally {
    smart.busy = false;
  }
}

async function openView(key, updateHistory = true) {
  if (!visibleNav.value.some((item) => item.key === key)) return;
  if (key !== "imports") importPollToken += 1;
  activeLoadController?.abort();
  view.value = key;
  importDetail.value = null;
  if (updateHistory && window.location.hash !== `#${key}`) {
    window.history.pushState({ view: key }, "", `#${key}`);
  }
  await loadCurrent(key === "imports" || key === "settings");
}

function exportOrders() {
  window.location.href = `/orders/export?${query()}`;
}

async function uploadFile(file) {
  importMessage.text = "";
  importMessage.type = "";
  importBusy.value = true;
  uploadProgress.value = 0;
  try {
    importMessage.type = "notice";
    importMessage.text = "正在上传：0%";
    const data = await uploadImportFile(file);
    selectedFile.value = null;
    if (importFileInput.value) importFileInput.value.value = "";
    importMessage.type = "notice";
    importMessage.text = "文件已上传，系统正在后台解析校验。";
    await openImport(data.batch_no);
    await pollImport(data.batch_no);
  } catch (err) {
    showImportError(err.message);
  } finally {
    importBusy.value = false;
    uploadProgress.value = 0;
  }
}

function requestImportUpload() {
  if (!selectedFile.value) {
    showImportError("请先选择 Excel 文件");
    return;
  }
  if (latestValidUncommittedImport.value) {
    uploadReminderOpen.value = true;
    return;
  }
  uploadFile(selectedFile.value);
}

function cancelImportReminder() {
  uploadReminderOpen.value = false;
}

function continueImportUpload() {
  uploadReminderOpen.value = false;
  if (selectedFile.value) uploadFile(selectedFile.value);
}

function openPendingImport() {
  uploadReminderOpen.value = false;
  if (latestValidUncommittedImport.value) openImport(latestValidUncommittedImport.value.batch_no);
}

function uploadImportFile(file) {
  return new Promise((resolve, reject) => {
    const form = new FormData();
    form.append("file", file);
    const xhr = new XMLHttpRequest();
    xhr.open("POST", "/api/imports/upload", true);
    xhr.withCredentials = true;
    xhr.upload.onprogress = (event) => {
      if (!event.lengthComputable) {
        importMessage.text = "正在上传文件...";
        return;
      }
      uploadProgress.value = Math.round((event.loaded / event.total) * 100);
      importMessage.type = "notice";
      importMessage.text = `正在上传：${uploadProgress.value}%`;
    };
    xhr.onload = () => {
      let body = {};
      try {
        body = xhr.responseText ? JSON.parse(xhr.responseText) : {};
      } catch {
        reject(new Error("上传响应解析失败"));
        return;
      }
      if (xhr.status >= 200 && xhr.status < 300) {
        resolve(body.data ?? body);
      } else {
        reject(new Error(body.detail || "上传失败"));
      }
    };
    xhr.onerror = () => reject(new Error("上传网络异常，请稍后重试。"));
    xhr.send(form);
  });
}

function showImportError(message) {
  importMessage.type = "error";
  importMessage.text = message || "上传失败，请检查 Excel 模板。";
}

async function openImport(batchNo) {
  const data = await api(`/api/imports/${batchNo}`);
  importDetail.value = data;
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function importProgressText(log) {
  if (!log) return "正在读取导入批次。";
  const total = Number(log.total_rows || 0);
  const fail = Number(log.fail_rows || 0);
  if (log.status === "processing") return `${log.remark || "正在处理"}；已处理 ${total} 行，异常 ${fail} 行`;
  if (log.status === "validated") return `校验完成：共 ${total} 行，异常 ${fail} 行`;
  if (log.status === "failed") return log.remark || "导入失败";
  return log.remark || `当前状态：${log.status}`;
}

function importStatusLabel(status) {
  return ({ processing: "处理中", validated: "待入库", committing: "入库中", committed: "已入库", failed: "已终止" })[status] || status;
}

async function pollImport(batchNo) {
  const token = ++importPollToken;
  for (let i = 0; i < 240; i += 1) {
    const interval = i === 0 ? 0 : i < 15 ? 2000 : i < 60 ? 5000 : 10000;
    await sleep(document.hidden ? Math.max(interval, 10000) : interval);
    if (token !== importPollToken || view.value !== "imports") return;
    await openImport(batchNo);
    const log = importDetail.value?.log;
    importMessage.type = log?.status === "failed" ? "error" : log?.status === "validated" ? "success" : "notice";
    importMessage.text = importProgressText(log);
    if (["validated", "failed", "committed"].includes(log?.status)) {
      Object.assign(imports, await api("/api/imports"));
      loadedKeys.delete("imports");
      return;
    }
    if (i > 0 && i % 6 === 0) Object.assign(imports, await api("/api/imports"));
  }
  throw new Error("后台导入仍在处理，请稍后从导入批次列表查看结果。");
}

async function commitImport(batchNo) {
  if (!window.confirm("确认将该批次写入正式订单？提交过程具备幂等保护，但业务数据入库后不提供物理删除。")) return;
  commitBusy.value = true;
  pageError.value = "";
  try {
    await api(`/api/imports/${batchNo}/commit`, { method: "POST" });
    await openImport(batchNo);
    Object.assign(imports, await api("/api/imports"));
    loadedKeys.delete("imports");
  } catch (err) {
    pageError.value = err.message || "批次入库失败";
  } finally {
    commitBusy.value = false;
  }
}

async function saveRole(role) {
  const form = new FormData();
  form.append("role_id", role.id);
  form.append("dept_scope", role.scopes.dept || "");
  form.append("platform_scope", role.scopes.platform || "");
  form.append("shop_scope", role.scopes.shop || "");
  pageError.value = "";
  try {
    const data = await api("/api/settings/roles", { method: "POST", body: form });
    settings.roles = data.roles;
    loadedKeys.delete("settings");
  } catch (err) {
    pageError.value = err.message || "权限范围保存失败";
  }
}

onMounted(async () => {
  try {
    await refreshMe();
    if (me.authenticated) {
      const requestedView = window.location.hash.slice(1);
      if (visibleNav.value.some((item) => item.key === requestedView)) view.value = requestedView;
      else window.history.replaceState({ view: view.value }, "", `#${view.value}`);
      window.addEventListener("popstate", () => {
        const target = window.location.hash.slice(1) || "dashboard";
        openView(target, false);
      });
      await loadCurrent(true);
    }
  } catch (err) {
    pageError.value = err.message || "系统初始化失败";
  }
});

</script>
