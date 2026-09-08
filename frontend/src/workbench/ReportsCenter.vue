<template>
  <section class="reports-workbench">
    <header class="workbench-hero report-hero">
      <div><p class="kicker">IMMUTABLE REPORT LIBRARY</p><h2>把本期判断固定成可复核版本</h2><p>每次重新生成都会创建新版本。历史报告仍按当前账号的数据范围校验。</p></div>
      <button class="primary" type="button" @click="composerOpen = !composerOpen">生成新报告</button>
    </header>

    <form v-if="composerOpen" class="report-composer" @submit.prevent="generate">
      <label>报告类型<select v-model="draft.report_type"><option value="monthly">月度经营报告</option><option value="exception">异常专题报告</option></select></label>
      <label>报告标题<input v-model="draft.title" maxlength="120" placeholder="留空则使用系统标题" /></label>
      <div><small>将按当前已应用条件生成，数字来自完整授权范围。</small><button class="primary" :disabled="saving">{{ saving ? '生成中…' : '生成并保存版本' }}</button></div>
    </form>

    <div class="report-layout">
      <aside class="panel report-list">
        <div class="panel-title"><h2>报告版本</h2><span>{{ reports.length }} 份</span></div>
        <div v-if="state === 'loading' && !reports.length" class="workbench-empty">正在读取报告…</div>
        <div v-else-if="state === 'error' && !reports.length" class="workbench-empty error-state"><strong>报告列表加载失败</strong><span>{{ error }}</span><button class="ghost" @click="loadReports">重试</button></div>
        <button v-for="report in reports" :key="report.id" :class="['report-list-item', { active: selected?.id === report.id }]" @click="selectReport(report.id)">
          <span><em>{{ typeLabel(report.report_type) }}</em><b>V{{ report.version }}</b></span>
          <strong>{{ report.title }}</strong>
          <small>{{ periodLabel(report.filters) }} · {{ formatDate(report.created_at) }}</small>
          <i v-if="report.stale">有新数据</i>
        </button>
        <div v-if="state !== 'loading' && !reports.length" class="workbench-empty">还没有保存的报告。选择当前期间生成第一版。</div>
      </aside>

      <section class="panel report-preview">
        <div v-if="previewBusy" class="workbench-empty">正在校验权限并读取报告…</div>
        <div v-else-if="previewError" class="workbench-empty error-state"><strong>报告无法读取</strong><span>{{ previewError }}</span></div>
        <template v-else-if="selected">
          <header class="report-cover">
            <div><p class="kicker">{{ typeLabel(selected.report_type).toUpperCase() }}</p><h2>{{ selected.title }}</h2><p>{{ periodLabel(body.filters || selected.filters) }}</p></div>
            <div class="report-version"><span>VERSION</span><strong>V{{ selected.version }}</strong><small>{{ formatDate(selected.created_at) }}</small></div>
          </header>
          <div v-if="selected.stale" class="stale-banner">这份历史版本未包含最新数据。需要更新时请重新生成，原版本会保留。</div>
          <div v-for="warning in body.warnings || []" :key="warning" class="report-warning">{{ warning }}</div>
          <section class="report-kpis">
            <article><span>销售额</span><strong>¥ {{ money(body.summary?.revenue) }}</strong></article>
            <article><span>经营利润</span><strong :class="{ loss: Number(body.summary?.profit || 0) < 0 }">¥ {{ money(body.summary?.profit) }}</strong></article>
            <article><span>利润率</span><strong>{{ body.summary?.profit_rate == null ? '—' : `${money(body.summary.profit_rate)}%` }}</strong></article>
            <article><span>订单数</span><strong>{{ Number(body.summary?.orders || 0).toLocaleString('zh-CN') }}</strong></article>
          </section>
          <section v-if="body.narrative" class="report-narrative"><p>{{ narrativeText }}</p></section>
          <section v-if="!hasBaseline" class="baseline-note"><strong>缺少可用基线</strong><span>报告保留本期事实，不生成下降或增长结论。可检查比较模式或数据覆盖。</span></section>
          <section v-for="(section, index) in body.sections || []" :key="section.key || index" class="report-section">
            <div class="report-section-title"><span>{{ String(index + 1).padStart(2, '0') }}</span><section><h3>{{ section.title }}</h3><small v-if="section.top_n">展示 {{ Math.min(section.top_n, section.rows?.length || 0) }} / {{ section.total || 0 }} 项；完整清单见 XLSX</small></section></div>
            <div class="report-section-body">
              <dl v-if="section.key === 'summary'" class="section-summary">
                <template v-for="item in summaryRows(section.summary || body.summary)" :key="item.label"><dt>{{ item.label }}</dt><dd>{{ item.value }}</dd></template>
              </dl>
              <div v-else-if="section.key === 'operating' || section.key === 'quality'" class="table-scroll">
                <p v-if="section.key === 'quality'" class="quality-period-note">质量异常不按发货日期过滤，以保留日期无效的记录；仍服从其他筛选条件与批次权限。</p>
                <table class="report-detail-table"><thead><tr><th>规则 / 对象</th><th>当前 / 基线</th><th>影响</th><th>核查结论</th><th>建议</th></tr></thead><tbody>
                  <tr v-for="row in section.rows || []" :key="row.id"><td><b>{{ row.rule_label }}</b><small>{{ row.object_label }}</small></td><td>{{ displayExceptionMetric(row, 'current_value') }}<small>基线 {{ displayExceptionMetric(row, 'baseline_value') }}</small></td><td>{{ displayExceptionMetric(row, 'impact_amount') }}</td><td><b>{{ reviewLabel(row.status) }}</b><small>{{ row.note || '未记录备注' }}</small></td><td>{{ row.suggestion || row.message }}</td></tr>
                  <tr v-if="!section.rows?.length"><td colspan="5">本报告版本没有{{ section.key === 'quality' ? '数据质量' : '经营' }}异常。</td></tr>
                </tbody></table>
              </div>
              <div v-else-if="section.key === 'contributions'" class="table-scroll">
                <table class="report-detail-table"><thead><tr><th>对象</th><th>销售额</th><th>销售额变化</th><th>利润</th><th>利润变化</th></tr></thead><tbody>
                  <tr v-for="row in section.rows || []" :key="`${row.product_no}-${row.shop_name}`"><td><b>{{ row.object_label }}</b><small>{{ row.new_in_period ? '本期新增' : row.disappeared ? '本期未出现' : '持续经营' }}</small></td><td>{{ displayExceptionMetric(row, 'current_revenue') }}<small>基线 {{ displayExceptionMetric(row, 'previous_revenue') }}</small></td><td :class="{ loss: Number(row.revenue_change || 0) < 0 }">{{ signedMetric(row.revenue_change) }}</td><td>{{ displayExceptionMetric(row, 'current_profit') }}<small>基线 {{ displayExceptionMetric(row, 'previous_profit') }}</small></td><td :class="{ loss: Number(row.profit_change || 0) < 0 }">{{ signedMetric(row.profit_change) }}</td></tr>
                  <tr v-if="!section.rows?.length"><td colspan="5">没有可展示的变化贡献。</td></tr>
                </tbody></table>
              </div>
              <ul v-else-if="Array.isArray(section.items || section.content)"><li v-for="(item, itemIndex) in (section.items || section.content)" :key="itemIndex">{{ itemText(item) }}</li></ul>
              <p v-else-if="typeof section.content === 'string'">{{ section.content }}</p>
              <pre v-else class="section-raw">{{ JSON.stringify(section, null, 2) }}</pre>
            </div>
          </section>
          <section class="report-provenance">
            <div><span>数据版本</span><b>{{ selected.data_version || body.data_version || '—' }}</b></div>
            <div><span>规则版本</span><b>{{ selected.rules_version || body.rules_version || '—' }}</b></div>
            <div><span>比较基线</span><b>{{ comparisonLabel }}</b></div>
            <div><span>利润公式</span><b>应收 − 成本 − 运费 − 辅料费 − 分摊费用</b></div>
          </section>
          <footer class="report-actions">
            <button class="ghost" :disabled="saving" @click="regenerate">{{ saving ? '生成中…' : '按当前数据重新生成' }}</button>
            <a v-if="canExport" class="export-btn" :href="`/api/reports/${selected.id}/export.pdf`"><Download :size="16" /> PDF</a>
            <a v-if="canExport" class="export-btn" :href="`/api/reports/${selected.id}/export.xlsx`"><Download :size="16" /> XLSX</a>
          </footer>
        </template>
        <div v-else class="workbench-empty"><strong>选择一份报告进行预览</strong><span>报告包含口径、数据版本、规则版本与异常证据。</span></div>
      </section>
    </div>
    <div v-if="actionError" class="page-alert" role="alert">{{ actionError }}</div>
  </section>
</template>

<script setup>
import { computed, onMounted, reactive, ref, watch } from "vue";
import { Download } from "lucide-vue-next";
import { buildReportPayload, displayExceptionMetric, reportBody } from "./contract.js";

const props = defineProps({ api: { type: Function, required: true }, filters: { type: Object, required: true }, canExport: Boolean, refreshKey: { type: Number, default: 0 } });
const emit = defineEmits(["status", "latest"]);
const reports = ref([]);
const selected = ref(null);
const state = ref("idle");
const error = ref("");
const previewBusy = ref(false);
const previewError = ref("");
const saving = ref(false);
const composerOpen = ref(false);
const actionError = ref("");
const draft = reactive({ report_type: "monthly", title: "" });
let listToken = 0;
let previewToken = 0;

const body = computed(() => reportBody(selected.value || {}));
const hasBaseline = computed(() => body.value.previous_summary && Number(body.value.previous_summary.orders || body.value.previous_summary.detail_rows || 0) > 0);
const narrativeText = computed(() => Array.isArray(body.value.narrative) ? body.value.narrative.join("；") : body.value.narrative);
const comparisonLabel = computed(() => {
  const comparison = body.value.comparison || {};
  if (!comparison.start_time || !comparison.end_time) return "缺少基线";
  return `${comparison.label || "对比"} ${comparison.start_time} 至 ${comparison.end_time}`;
});

watch(() => props.filters, () => { if (state.value === "loaded") state.value = "stale"; }, { deep: true });
watch(() => props.refreshKey, () => loadReports());
onMounted(loadReports);

async function loadReports(selectId = null) {
  const token = ++listToken;
  state.value = reports.value.length ? "stale" : "loading";
  error.value = "";
  emit("status", state.value);
  try {
    const data = await props.api("/api/reports");
    if (token !== listToken) return;
    reports.value = data.reports || [];
    state.value = "loaded";
    emit("latest", reports.value[0] || null);
    const target = selectId || selected.value?.id || reports.value[0]?.id;
    if (target) await selectReport(target);
  } catch (err) {
    if (token !== listToken || err.name === "AbortError") return;
    error.value = err.message || "报告列表加载失败";
    state.value = "error";
  } finally { if (token === listToken) emit("status", state.value); }
}

async function selectReport(id) {
  const token = ++previewToken;
  previewBusy.value = true;
  previewError.value = "";
  try {
    const data = await props.api(`/api/reports/${id}`);
    if (token === previewToken) selected.value = data;
  } catch (err) { if (token === previewToken) previewError.value = err.message || "报告读取失败"; }
  finally { if (token === previewToken) previewBusy.value = false; }
}

async function generate() {
  saving.value = true;
  actionError.value = "";
  try {
    const created = await props.api("/api/reports", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(buildReportPayload(props.filters, draft.report_type, draft.title)) });
    composerOpen.value = false;
    draft.title = "";
    await loadReports(created.id);
  } catch (err) { actionError.value = err.message || "报告生成失败"; }
  finally { saving.value = false; }
}

async function regenerate() {
  if (!selected.value) return;
  saving.value = true;
  actionError.value = "";
  try {
    const created = await props.api(`/api/reports/${selected.value.id}/regenerate`, { method: "POST" });
    await loadReports(created.id);
  } catch (err) { actionError.value = err.message || "报告重新生成失败"; }
  finally { saving.value = false; }
}

function money(value) { return Number(value || 0).toLocaleString("zh-CN", { maximumFractionDigits: 2 }); }
function typeLabel(value) { return value === "exception" ? "异常专题报告" : "月度经营报告"; }
function periodLabel(filters = {}) { return filters.start_time && filters.end_time ? `${filters.start_time} 至 ${filters.end_time}` : "范围记录缺失"; }
function formatDate(value) { return value ? new Date(value).toLocaleString("zh-CN", { hour12: false }) : "—"; }
function itemText(item) { return typeof item === "string" ? item : item?.text || item?.summary || item?.title || JSON.stringify(item); }
function signedMetric(value) { const number = Number(value || 0); return `${number > 0 ? "+" : ""}${money(number)}`; }
function reviewLabel(value) { return ({ pending: "待核查", confirmed: "已确认问题", dismissed: "已排除" })[value] || "待核查"; }
function summaryRows(summary = {}) {
  return [
    { label: "销售额", value: `¥ ${money(summary.revenue)}` },
    { label: "经营利润", value: `¥ ${money(summary.profit)}` },
    { label: "利润率", value: summary.profit_rate == null ? "—" : `${money(summary.profit_rate)}%` },
    { label: "扣减费用", value: `¥ ${money(summary.fees)}` },
    { label: "销量", value: money(summary.qty) },
    { label: "明细行", value: Number(summary.detail_rows || 0).toLocaleString("zh-CN") }
  ];
}
</script>
