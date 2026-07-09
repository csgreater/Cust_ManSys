<template>
  <div class="app-shell">
    <section v-if="!me.authenticated" class="login-stage">
      <div class="login-hero">
        <p class="kicker">ORDER INTELLIGENCE</p>
        <h1>订单数据管理系统</h1>
        <p>面向产品经营、渠道表现、利润结构和权限隔离的高端商务运营台。</p>
      </div>
      <form class="login-card" @submit.prevent="login">
        <div>
          <p class="kicker">SECURE ACCESS</p>
          <h2>账号登录</h2>
        </div>
        <label>账号<input v-model="loginForm.username" autocomplete="username" /></label>
        <label>密码<input v-model="loginForm.password" type="password" autocomplete="current-password" /></label>
        <div v-if="error" class="alert">{{ error }}</div>
        <button class="primary" type="submit">进入系统</button>
      </form>
    </section>

    <template v-else>
      <aside class="nav-rail">
        <div class="brand">
          <span>OM</span>
          <div><strong>Order Matrix</strong><small>Business Console</small></div>
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
            <button v-if="view === 'orders'" class="export-btn" @click="exportOrders"><Download :size="16" /> 导出</button>
          </div>
        </header>

        <section v-if="['dashboard', 'orders', 'products', 'shops'].includes(view)" class="filter-suite">
          <div class="range-control">
            <span>订单日期</span>
            <button type="button" @click="rangeOpen = !rangeOpen">{{ filters.start_time }} 至 {{ filters.end_time }}</button>
            <div v-if="rangeOpen" class="range-pop">
              <nav><button v-for="p in presets" :key="p[0]" type="button" @click="applyPreset(p[0])">{{ p[1] }}</button></nav>
              <div class="range-custom">
                <label>开始时间<input type="date" v-model="filters.start_time" /></label>
                <b>至</b>
                <label>结束时间<input type="date" v-model="filters.end_time" /></label>
                <button class="primary" type="button" @click="rangeOpen=false; loadCurrent()">应用</button>
              </div>
            </div>
          </div>
          <label>部门<input v-model="filters.dept" @input="delayedLoad" @change="loadCurrent" placeholder="全部" /></label>
          <label>平台<input v-model="filters.platform" @input="delayedLoad" @change="loadCurrent" placeholder="全部" /></label>
          <label>店铺<input v-model="filters.shop_name" @input="delayedLoad" @change="loadCurrent" placeholder="全部" /></label>
          <label v-if="view === 'products'">大类<input v-model="filters.category" @input="delayedLoad" @change="loadCurrent" placeholder="全部" /></label>
          <label v-if="['orders','products'].includes(view)">产品/SKU<input v-model="filters.product" @input="delayedLoad" @change="loadCurrent" placeholder="名称、货号、SKU" /></label>
          <label v-if="view === 'orders'">订单号<input v-model="filters.order_no" @input="delayedLoad" @change="loadCurrent" placeholder="订单编号" /></label>
        </section>

        <section v-if="loading" class="loading-panel">正在载入数据...</section>

        <template v-else>
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
              <div class="panel-title"><h2>分析结论</h2><span>{{ smart.result.filters.start_time }} 至 {{ smart.result.filters.end_time }}</span></div>
              <div class="smart-summary">{{ smart.result.answer }}</div>
            </section>

            <section v-if="smart.result" class="chart-grid">
              <div class="panel">
                <div class="panel-title"><h2>{{ smart.result.chart.metric_label }}图表</h2><span>{{ smart.result.chart.type }}</span></div>
                <div v-if="smart.result.chart.type === 'pie'" class="smart-pie-wrap">
                  <div class="smart-pie" :style="smartPieStyle"></div>
                  <div class="smart-legend">
                    <div v-for="point in smart.result.chart.points.slice(0, 12)" :key="point.label"><i></i><span>{{ point.label }}</span><b>{{ Number(point.value || 0).toFixed(2) }}%</b></div>
                  </div>
                </div>
                <div v-else class="smart-bars">
                  <div v-for="point in smart.result.chart.points" :key="point.label" class="smart-bar">
                    <span>{{ point.label }}</span>
                    <div><i :style="{ width: smartBarWidth(point.value) }"></i></div>
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
            <section class="metric-grid">
              <article><span>销售额</span><strong>{{ Money(dashboard.summary.revenue) }}</strong></article>
              <article><span>销量</span><strong>{{ Money(dashboard.summary.qty) }}</strong></article>
              <article><span>利润</span><strong>{{ Money(dashboard.summary.profit) }}</strong></article>
              <article><span>利润率</span><strong>{{ Money(dashboard.summary.profit_rate) }}%</strong></article>
              <article><span>订单数</span><strong>{{ dashboard.summary.orders || 0 }}</strong></article>
            </section>
            <section class="panel">
              <div class="panel-title"><h2>TOP 产品</h2><span>按销售额排序</span></div>
              <table>
                <thead><tr><th>产品</th><th>大类</th><th>货号</th><th>销量</th><th>销售额</th><th>利润</th></tr></thead>
                <tbody>
                  <tr v-for="row in dashboard.top_products" :key="row.product_no">
                    <td>{{ row.product_name }}</td><td>{{ row.category }}</td><td>{{ row.product_no }}</td>
                    <td>{{ Money(row.qty) }}</td><td>{{ Money(row.revenue) }}</td><td>{{ Money(row.profit) }}</td>
                  </tr>
                  <tr v-if="!dashboard.top_products?.length"><td colspan="6">暂无数据</td></tr>
                </tbody>
              </table>
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
                    <td><b>{{ MaskName(row.receiver_name) }}</b><small>{{ MaskAddress(row.receiver_address) }}</small></td>
                    <td>{{ row.platform }}<small>{{ row.shop_name }}</small></td>
                    <td><b>{{ row.product_name }}</b><small>{{ row.category }} / {{ row.product_no }}</small></td>
                    <td>{{ Money(row.qty) }}</td><td>{{ Money(row.share_receivable) }}</td><td>{{ Money(row.profit) }}</td>
                  </tr>
                  <tr v-if="!orders.rows?.length"><td colspan="11">暂无数据</td></tr>
              </tbody>
            </table>
          </section>

          <section v-if="view === 'imports'">
            <section class="import-layout">
              <div class="panel upload-card">
                <UploadCloud :size="28" />
                <h2>上传月度 Excel</h2>
                <div v-if="importMessage.text" :class="importMessage.type === 'error' ? 'alert' : 'notice'">{{ importMessage.text }}</div>
                <input type="file" accept=".xlsx,.xlsm" @change="selectedFile = $event.target.files[0]" />
                <div v-if="importBusy || uploadProgress > 0" class="upload-progress">
                  <span :style="{ width: `${uploadProgress}%` }"></span>
                  <b>{{ uploadProgress ? `${uploadProgress}%` : '等待服务器接收' }}</b>
                </div>
                <button class="primary" :disabled="importBusy" @click="selectedFile ? uploadFile(selectedFile) : showImportError('请先选择 Excel 文件')">
                  {{ importBusy ? "正在处理..." : "上传并校验" }}
                </button>
              </div>
              <div class="panel">
                <div class="panel-title"><h2>导入批次</h2><span>最近 50 条</span></div>
                <table>
                  <thead><tr><th>批次</th><th>文件</th><th>状态</th><th>总行</th><th>异常</th><th>时间</th></tr></thead>
                  <tbody>
                    <tr v-for="log in imports.logs" :key="log.batch_no" @click="openImport(log.batch_no)">
                      <td>{{ log.batch_no }}</td><td>{{ log.file_name }}</td><td><em>{{ log.status }}</em></td>
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
                <button v-if="importDetail.log.status !== 'committed' && importDetail.log.fail_rows === 0 && importDetail.log.total_rows > 0" class="primary" @click="commitImport(importDetail.log.batch_no)">确认入库</button>
              </div>
              <table>
                <thead><tr><th>行号</th><th>订单</th><th>客户</th><th>地址</th><th>产品</th><th>利润</th><th>异常</th><th>提示</th></tr></thead>
                <tbody>
                  <tr v-for="row in importDetail.rows" :key="row.id">
                    <td>{{ row.row_no }}</td><td>{{ row.order_no }}</td><td>{{ row.customer_name }} / {{ row.customer_no }}</td>
                    <td>{{ MaskAddress(row.receiver_address) }}</td>
                    <td>{{ row.product_name }}</td><td>{{ Money(row.profit) }}</td><td>{{ row.error_message }}</td><td>{{ row.warning_message }}</td>
                  </tr>
                </tbody>
              </table>
            </section>
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
                    <div><strong>{{ row.product_name }}</strong><small>{{ row.category }} / {{ row.product_no }}</small></div>
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
                <thead><tr><th>大类</th><th>产品</th><th>货号</th><th>销量</th><th>销售额</th><th>成本</th><th>利润</th><th>利润率</th></tr></thead>
                <tbody>
                  <tr v-for="row in products.rows" :key="row.product_no">
                    <td><em>{{ row.category }}</em></td><td>{{ row.product_name }}</td><td>{{ row.product_no }}</td>
                    <td>{{ Money(row.qty) }}</td><td>{{ Money(row.revenue) }}</td><td>{{ Money(row.cost) }}</td><td>{{ Money(row.profit) }}</td><td>{{ Money(row.profit_rate) }}%</td>
                  </tr>
                  <tr v-if="!products.rows?.length"><td colspan="8">暂无数据</td></tr>
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
import { computed, defineComponent, onMounted, reactive, ref, watch } from "vue";
import {
  BarChart3,
  Box,
  Building2,
  Download,
  FileSpreadsheet,
  LayoutDashboard,
  LineChart,
  Sparkles,
  Settings,
  ShoppingBag,
  UploadCloud
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

function MaskName(value) {
  const text = String(value || "");
  if (!text) return "";
  return text.length > 1 ? `${text.slice(0, 1)}**` : "*";
}

function MaskAddress(value) {
  const text = String(value || "");
  if (!text) return "";
  if (text.length <= 6) return "***";
  return `${text.slice(0, 3)}***${text.slice(-3)}`;
}
const lastMonthStart = addMonths(startOfMonth(today), -1);
const lastMonthEnd = addDays(startOfMonth(today), -1);

const view = ref("dashboard");
const loading = ref(false);
const error = ref("");
const rangeOpen = ref(false);
const selectedFile = ref(null);
const importBusy = ref(false);
const uploadProgress = ref(0);
const importMessage = reactive({ type: "", text: "" });
let filterTimer = null;
const me = reactive({ authenticated: false, permissions: [], role_codes: [] });
const loginForm = reactive({ username: "admin", password: "" });
const filters = reactive({
  start_time: fmt(lastMonthStart),
  end_time: fmt(lastMonthEnd),
  dept: "",
  platform: "",
  shop_name: "",
  category: "",
  product: "",
  order_no: ""
});

const dashboard = reactive({ summary: {}, top_products: [] });
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

const nav = [
  { key: "smart", label: "智能分析", meta: "NATURAL LANGUAGE SQL", icon: Sparkles, permission: "analytics" },
  { key: "dashboard", label: "经营看板", meta: "EXECUTIVE OVERVIEW", icon: LayoutDashboard, permission: "view" },
  { key: "orders", label: "订单明细", meta: "ORDER LEDGER", icon: ShoppingBag, permission: "view" },
  { key: "imports", label: "数据导入", meta: "IMPORT CONTROL", icon: FileSpreadsheet, permission: "import" },
  { key: "products", label: "产品分析", meta: "PRODUCT INTELLIGENCE", icon: LineChart, permission: "analytics" },
  { key: "shops", label: "店铺平台", meta: "CHANNEL PERFORMANCE", icon: Building2, permission: "analytics" },
  { key: "settings", label: "权限配置", meta: "ACCESS GOVERNANCE", icon: Settings, permission: "settings" }
];
const can = (permission) => me.permissions?.includes("admin") || me.permissions?.includes(permission);
const visibleNav = computed(() => nav.filter((item) => can(item.permission)));
const currentNav = computed(() => nav.find((item) => item.key === view.value));
const usesFilters = computed(() => ["dashboard", "orders", "products", "shops"].includes(view.value));
const maxCategoryRevenue = computed(() => Math.max(...products.category_rows.map((row) => Number(row.revenue || 0)), 1));
const maxProductRevenue = computed(() => Math.max(...products.rows.slice(0, 10).map((row) => Number(row.revenue || 0)), 1));
const smartColumns = computed(() => smart.result?.rows?.length ? Object.keys(smart.result.rows[0]) : []);
const smartMaxValue = computed(() => Math.max(...(smart.result?.chart?.points || []).map((point) => Number(point.value || 0)), 1));
const smartPieStyle = computed(() => {
  const colors = ["#6bf8e0", "#8dff93", "#ffcb6b", "#b78cff", "#ff6b6b", "#7bc9ff", "#d6ff6b", "#ffa66b", "#f48cff", "#9fb4ff", "#66e2a6", "#ffd36b"];
  const points = smart.result?.chart?.points || [];
  let cursor = 0;
  const segments = points.map((point, index) => {
    const next = cursor + Math.max(0, Number(point.value || 0));
    const segment = `${colors[index % colors.length]} ${cursor}% ${next}%`;
    cursor = next;
    return segment;
  });
  return { background: `conic-gradient(${segments.join(", ") || "#203235 0% 100%"})` };
});
const presets = [
  ["last7", "近7天"], ["last30", "近30天"], ["lastWeek", "上周"], ["thisMonth", "本月"], ["lastMonth", "上月"],
  ["quarter", "本季度"], ["firstHalf", "上半年"], ["secondHalf", "下半年"], ["lastYear", "近一年"], ["thisYear", "今年"]
];

function query() {
  return new URLSearchParams(Object.fromEntries(Object.entries(filters).filter(([, v]) => v))).toString();
}

async function api(path, options = {}) {
  const response = await fetch(path, { credentials: "same-origin", ...options });
  const contentType = response.headers.get("content-type") || "";
  const body = contentType.includes("application/json") ? await response.json() : {};
  if (!response.ok) throw new Error(body.detail || "请求失败");
  return body.data ?? body;
}

async function refreshMe() {
  const data = await api("/api/me");
  Object.assign(me, data);
}

async function login() {
  error.value = "";
  const form = new FormData();
  form.append("username", loginForm.username);
  form.append("password", loginForm.password);
  try {
    const data = await api("/api/login", { method: "POST", body: form });
    Object.assign(me, data);
    await loadCurrent();
  } catch (err) {
    error.value = err.message;
  }
}

async function logout() {
  await api("/api/logout", { method: "POST" });
  Object.assign(me, { authenticated: false, permissions: [], role_codes: [] });
}

async function loadCurrent() {
  if (!me.authenticated) return;
  loading.value = true;
  try {
    if (view.value === "dashboard") Object.assign(dashboard, await api(`/api/dashboard?${query()}`));
    if (view.value === "orders") Object.assign(orders, await api(`/api/orders?${query()}`));
    if (view.value === "imports") Object.assign(imports, await api("/api/imports"));
    if (view.value === "products") Object.assign(products, await api(`/api/analytics/products?${query()}`));
    if (view.value === "shops") Object.assign(shops, await api(`/api/analytics/shops?${query()}`));
    if (view.value === "settings") {
      const [users, roles] = await Promise.all([api("/api/settings/users"), api("/api/settings/roles")]);
      settings.users = users.users;
      settings.roles = roles.roles;
    }
  } finally {
    loading.value = false;
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
  loadCurrent();
}

function delayedLoad() {
  clearTimeout(filterTimer);
  filterTimer = setTimeout(loadCurrent, 350);
}

function barWidth(value, max) {
  return `${Math.max(2, Math.min(100, Number(value || 0) / max * 100))}%`;
}

function smartBarWidth(value) {
  return `${Math.max(2, Math.min(100, Number(value || 0) / smartMaxValue.value * 100))}%`;
}

function smartColumnLabel(key) {
  const labels = {
    month: "月份",
    category: "产品大类",
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

async function openView(key) {
  view.value = key;
  importDetail.value = null;
  await loadCurrent();
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

async function pollImport(batchNo) {
  for (let i = 0; i < 1800; i += 1) {
    await sleep(i === 0 ? 0 : 2000);
    await openImport(batchNo);
    Object.assign(imports, await api("/api/imports"));
    const log = importDetail.value?.log;
    importMessage.type = log?.status === "failed" ? "error" : log?.status === "validated" ? "success" : "notice";
    importMessage.text = importProgressText(log);
    if (["validated", "failed", "committed"].includes(log?.status)) return;
  }
  throw new Error("后台导入仍在处理，请稍后从导入批次列表查看结果。");
}

async function commitImport(batchNo) {
  await api(`/api/imports/${batchNo}/commit`, { method: "POST" });
  await openImport(batchNo);
}

async function saveRole(role) {
  const form = new FormData();
  form.append("role_id", role.id);
  form.append("dept_scope", role.scopes.dept || "");
  form.append("platform_scope", role.scopes.platform || "");
  form.append("shop_scope", role.scopes.shop || "");
  const data = await api("/api/settings/roles", { method: "POST", body: form });
  settings.roles = data.roles;
}

onMounted(async () => {
  await refreshMe();
  if (me.authenticated) await loadCurrent();
});

const FilterBar = defineComponent({
  props: { modelValue: Object, showCategory: Boolean, showProduct: Boolean, showOrder: Boolean },
  emits: ["update:modelValue", "change"],
  setup(props, { emit }) {
    const open = ref(false);
    const local = reactive({ ...props.modelValue });
    let timer = null;
    const presets = [
      ["last7", "近7天"], ["last30", "近30天"], ["lastWeek", "上周"], ["thisMonth", "本月"], ["lastMonth", "上月"],
      ["quarter", "本季度"], ["firstHalf", "上半年"], ["secondHalf", "下半年"], ["lastYear", "近一年"], ["thisYear", "今年"]
    ];
    watch(() => props.modelValue, (value) => Object.assign(local, value), { deep: true });
    const presetRange = (name) => {
      const now = new Date();
      const month = startOfMonth(now);
      const weekday = now.getDay() || 7;
      if (name === "last7") return [addDays(now, -6), now];
      if (name === "last30") return [addDays(now, -29), now];
      if (name === "lastWeek") { const start = addDays(now, -weekday - 6); return [start, addDays(start, 6)]; }
      if (name === "thisMonth") return [month, now];
      if (name === "lastMonth") { const start = addMonths(month, -1); return [start, addDays(month, -1)]; }
      if (name === "quarter") return [new Date(now.getFullYear(), Math.floor(now.getMonth() / 3) * 3, 1), now];
      if (name === "firstHalf") return [new Date(now.getFullYear(), 0, 1), new Date(now.getFullYear(), 5, 30)];
      if (name === "secondHalf") return [new Date(now.getFullYear(), 6, 1), new Date(now.getFullYear(), 11, 31)];
      if (name === "lastYear") return [addDays(now, -364), now];
      return [new Date(now.getFullYear(), 0, 1), now];
    };
    const apply = () => {
      emit("update:modelValue", { ...local });
      emit("change");
    };
    const delayed = () => {
      clearTimeout(timer);
      timer = setTimeout(apply, 280);
    };
    const applyPreset = (name) => {
      const [start, end] = presetRange(name);
      local.start_time = fmt(start);
      local.end_time = fmt(end);
      open.value = false;
      apply();
    };
    return { local, open, presets, apply, delayed, applyPreset };
  },
  template: `
    <section class="filter-suite">
      <div class="range-control">
        <span>订单日期</span>
        <button type="button" @click="open = !open">{{ local.start_time }} 至 {{ local.end_time }}</button>
        <div v-if="open" class="range-pop">
          <nav><button v-for="p in presets" :key="p[0]" type="button" @click="applyPreset(p[0])">{{ p[1] }}</button></nav>
          <div class="range-custom">
            <label>开始时间<input type="date" v-model="local.start_time" /></label>
            <b>至</b>
            <label>结束时间<input type="date" v-model="local.end_time" /></label>
            <button class="primary" type="button" @click="open=false; apply()">应用</button>
          </div>
        </div>
      </div>
      <label>部门<input v-model="local.dept" @change="apply" @input="delayed" placeholder="全部" /></label>
      <label>平台<input v-model="local.platform" @change="apply" @input="delayed" placeholder="全部" /></label>
      <label>店铺<input v-model="local.shop_name" @change="apply" @input="delayed" placeholder="全部" /></label>
      <label v-if="showCategory">大类<input v-model="local.category" @change="apply" @input="delayed" placeholder="全部" /></label>
      <label v-if="showProduct">产品/SKU<input v-model="local.product" @change="apply" @input="delayed" placeholder="名称、货号、SKU" /></label>
      <label v-if="showOrder">订单号<input v-model="local.order_no" @change="apply" @input="delayed" placeholder="订单编号" /></label>
    </section>`
});

const DashboardView = defineComponent({
  props: { data: Object },
  setup(props) {
    return { Money, Box, BarChart3, UploadCloud, Download };
  },
  template: `
    <section class="metric-grid">
      <article><span>销售额</span><strong>{{ Money(data.summary.revenue) }}</strong></article>
      <article><span>销量</span><strong>{{ Money(data.summary.qty) }}</strong></article>
      <article><span>利润</span><strong>{{ Money(data.summary.profit) }}</strong></article>
      <article><span>利润率</span><strong>{{ Money(data.summary.profit_rate) }}%</strong></article>
      <article><span>订单数</span><strong>{{ data.summary.orders || 0 }}</strong></article>
    </section>
    <section class="panel">
      <div class="panel-title"><h2>TOP 产品</h2><span>按销售额排序</span></div>
      <table><thead><tr><th>产品</th><th>货号</th><th>销量</th><th>销售额</th><th>利润</th></tr></thead>
      <tbody><tr v-for="row in data.top_products" :key="row.product_no"><td>{{ row.product_name }}</td><td>{{ row.product_no }}</td><td>{{ Money(row.qty) }}</td><td>{{ Money(row.revenue) }}</td><td>{{ Money(row.profit) }}</td></tr><tr v-if="!data.top_products?.length"><td colspan="5">暂无数据</td></tr></tbody></table>
    </section>`
});

const OrdersView = defineComponent({
  props: { rows: Array },
  setup() { return { Money }; },
  template: `
    <section class="panel">
      <div class="panel-title"><h2>订单明细</h2><span>最多显示 200 行</span></div>
      <table><thead><tr><th>发货时间</th><th>订单</th><th>来源</th><th>客户</th><th>地区</th><th>平台/店铺</th><th>产品</th><th>数量</th><th>应收</th><th>利润</th></tr></thead>
      <tbody><tr v-for="row in rows" :key="row.id"><td>{{ row.ship_time }}</td><td>{{ row.order_no }}</td><td>{{ row.order_source }}</td><td><b>{{ row.customer_name }}</b><small>{{ row.customer_no }}</small></td><td><b>{{ row.province }}</b><small>{{ row.city }}<span v-if="row.district"> / {{ row.district }}</span></small></td><td>{{ row.platform }}<small>{{ row.shop_name }}</small></td><td><b>{{ row.product_name }}</b><small>{{ row.category }} / {{ row.product_no }}</small></td><td>{{ Money(row.qty) }}</td><td>{{ Money(row.share_receivable) }}</td><td>{{ Money(row.profit) }}</td></tr><tr v-if="!rows?.length"><td colspan="10">暂无数据</td></tr></tbody></table>
    </section>`
});

const ProductsView = defineComponent({
  props: { data: Object },
  setup(props) {
    const maxCategoryRevenue = computed(() => Math.max(...props.data.category_rows.map((r) => Number(r.revenue || 0)), 1));
    const maxProductRevenue = computed(() => Math.max(...props.data.rows.slice(0, 10).map((r) => Number(r.revenue || 0)), 1));
    const width = (value, max) => `${Math.max(2, Math.min(100, Number(value || 0) / max * 100))}%`;
    return { Money, maxCategoryRevenue, maxProductRevenue, width };
  },
  template: `
    <section class="chart-grid">
      <div class="panel">
        <div class="panel-title"><h2>大类收入结构</h2><span>分类维度</span></div>
        <div class="executive-bars">
          <div v-for="row in data.category_rows" :key="row.category" class="exec-bar-row">
            <div class="exec-label"><strong>{{ row.category }}</strong><small>{{ row.product_count }} 个货品</small></div>
            <div class="exec-track"><i :style="{ width: width(row.revenue, maxCategoryRevenue) }"></i></div>
            <div class="exec-value">{{ Money(row.revenue) }}</div>
          </div>
          <div v-if="!data.category_rows?.length" class="empty-state">暂无大类数据</div>
        </div>
      </div>
      <div class="panel">
        <div class="panel-title"><h2>产品收入与利润</h2><span>多维对比</span></div>
        <div class="profit-matrix">
          <article v-for="row in data.rows.slice(0, 10)" :key="row.product_no">
            <div><strong>{{ row.product_name }}</strong><small>{{ row.category }} / {{ row.product_no }}</small></div>
            <div class="matrix-bars">
              <span><i :style="{ width: width(row.revenue, maxProductRevenue) }"></i></span>
              <span class="profit"><i :class="{ loss: row.profit < 0 }" :style="{ width: width(Math.abs(Number(row.profit || 0)), Math.max(Math.abs(Number(row.revenue || 0)), 1)) }"></i></span>
            </div>
            <div class="matrix-values"><b>{{ Money(row.revenue) }}</b><em>{{ Money(row.profit) }}</em></div>
          </article>
          <div v-if="!data.rows?.length" class="empty-state">暂无产品数据</div>
        </div>
      </div>
    </section>
    <section class="panel">
      <div class="panel-title"><h2>产品明细排行</h2><span>按销售额排序</span></div>
      <table><thead><tr><th>大类</th><th>产品</th><th>货号</th><th>销量</th><th>销售额</th><th>成本</th><th>利润</th><th>利润率</th></tr></thead>
      <tbody><tr v-for="row in data.rows" :key="row.product_no"><td><em>{{ row.category }}</em></td><td>{{ row.product_name }}</td><td>{{ row.product_no }}</td><td>{{ Money(row.qty) }}</td><td>{{ Money(row.revenue) }}</td><td>{{ Money(row.cost) }}</td><td>{{ Money(row.profit) }}</td><td>{{ Money(row.profit_rate) }}%</td></tr><tr v-if="!data.rows?.length"><td colspan="8">暂无数据</td></tr></tbody></table>
    </section>`
});

const ShopsView = defineComponent({
  props: { rows: Array },
  setup() { return { Money }; },
  template: `<section class="panel"><div class="panel-title"><h2>店铺平台分析</h2><span>渠道经营表现</span></div><table><thead><tr><th>平台</th><th>店铺</th><th>销量</th><th>销售额</th><th>利润</th><th>利润率</th></tr></thead><tbody><tr v-for="row in rows" :key="row.platform + row.shop_name"><td>{{ row.platform }}</td><td>{{ row.shop_name }}</td><td>{{ Money(row.qty) }}</td><td>{{ Money(row.revenue) }}</td><td>{{ Money(row.profit) }}</td><td>{{ Money(row.profit_rate) }}%</td></tr><tr v-if="!rows?.length"><td colspan="6">暂无数据</td></tr></tbody></table></section>`
});

const ImportsView = defineComponent({
  props: { logs: Array, detail: Object },
  emits: ["upload", "open", "commit"],
  setup(_, { emit }) {
    const file = ref(null);
    const upload = () => file.value && emit("upload", file.value);
    return { file, upload };
  },
  template: `
    <section class="import-layout">
      <div class="panel upload-card"><UploadCloud :size="28" /><h2>上传月度 Excel</h2><input type="file" accept=".xlsx,.xlsm" @change="file = $event.target.files[0]" /><button class="primary" @click="upload">上传并校验</button></div>
      <div class="panel"><div class="panel-title"><h2>导入批次</h2><span>最近 50 条</span></div><table><thead><tr><th>批次</th><th>文件</th><th>状态</th><th>总行</th><th>异常</th><th>时间</th></tr></thead><tbody><tr v-for="log in logs" :key="log.batch_no" @click="$emit('open', log.batch_no)"><td>{{ log.batch_no }}</td><td>{{ log.file_name }}</td><td><em>{{ log.status }}</em></td><td>{{ log.total_rows }}</td><td>{{ log.fail_rows }}</td><td>{{ log.import_time }}</td></tr></tbody></table></div>
    </section>
    <section v-if="detail" class="panel"><div class="panel-title"><h2>{{ detail.log.batch_no }}</h2><button v-if="detail.log.status !== 'committed' && detail.log.fail_rows === 0 && detail.log.total_rows > 0" class="primary" @click="$emit('commit', detail.log.batch_no)">确认入库</button></div><table><thead><tr><th>行号</th><th>订单</th><th>客户</th><th>产品</th><th>利润</th><th>异常</th><th>提示</th></tr></thead><tbody><tr v-for="row in detail.rows" :key="row.id"><td>{{ row.row_no }}</td><td>{{ row.order_no }}</td><td>{{ row.customer_name }} / {{ row.customer_no }}</td><td>{{ row.product_name }}</td><td>{{ row.profit }}</td><td>{{ row.error_message }}</td><td>{{ row.warning_message }}</td></tr></tbody></table></section>`
});

const SettingsView = defineComponent({
  props: { users: Array, roles: Array },
  emits: ["save-role"],
  template: `
    <section class="settings-grid">
      <div class="panel"><div class="panel-title"><h2>用户</h2><span>账号与角色</span></div><table><thead><tr><th>账号</th><th>姓名</th><th>角色</th><th>状态</th></tr></thead><tbody><tr v-for="user in users" :key="user.id"><td>{{ user.username }}</td><td>{{ user.display_name }}</td><td>{{ user.roles }}</td><td>{{ user.is_active ? '启用' : '停用' }}</td></tr></tbody></table></div>
      <div class="role-panel"><article v-for="role in roles" :key="role.id" class="role-card"><h3>{{ role.role_name }}</h3><small>{{ role.permissions }}</small><label>部门范围<input v-model="role.scopes.dept" /></label><label>平台范围<input v-model="role.scopes.platform" /></label><label>店铺范围<input v-model="role.scopes.shop" /></label><button class="primary" @click="$emit('save-role', role)">保存</button></article></div>
    </section>`
});
</script>
