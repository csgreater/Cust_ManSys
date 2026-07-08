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
                <button class="primary" @click="selectedFile ? uploadFile(selectedFile) : showImportError('请先选择 Excel 文件')">上传并校验</button>
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

const nav = [
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
  const form = new FormData();
  form.append("file", file);
  try {
    const data = await api("/api/imports/upload", { method: "POST", body: form });
    importMessage.type = "success";
    importMessage.text = "上传完成，已生成校验批次。";
    await openImport(data.batch_no);
    await loadCurrent();
  } catch (err) {
    showImportError(err.message);
  }
}

function showImportError(message) {
  importMessage.type = "error";
  importMessage.text = message || "上传失败，请检查 Excel 模板。";
}

async function openImport(batchNo) {
  const data = await api(`/api/imports/${batchNo}`);
  importDetail.value = data;
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
