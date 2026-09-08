<template>
  <section class="exception-workbench">
    <header class="workbench-hero">
      <div><p class="kicker">EXCEPTION REVIEW DESK</p><h2>先看影响，再核对证据</h2><p>经营异常与导入质量分别解释。核查结论只记录判断，不改写原始金额。</p></div>
      <div class="hero-actions">
        <a v-if="canExport || type === 'quality'" class="export-btn" :href="exportUrl"><Download :size="16" /> 下载完整 XLSX</a>
        <button v-if="canSettings" class="ghost" type="button" @click="openRules">参考阈值</button>
      </div>
    </header>

    <div class="workbench-tabs" role="tablist" aria-label="异常类型">
      <button v-if="canOperating" role="tab" :aria-selected="type === 'operating'" :class="{ active: type === 'operating' }" @click="setType('operating')">经营异常</button>
      <button v-if="canQuality" role="tab" :aria-selected="type === 'quality'" :class="{ active: type === 'quality' }" @click="setType('quality')">数据质量</button>
    </div>
    <p v-if="type === 'quality'" class="scope-explanation">数据质量异常不按发货日期过滤，以保留日期无效的记录；仍服从其他筛选条件与批次权限。</p>

    <div class="exception-summary">
      <article><span>全部</span><strong>{{ result.summary?.total ?? result.total ?? 0 }}</strong></article>
      <article><span>待核查</span><strong>{{ result.summary?.pending ?? 0 }}</strong></article>
      <article><span>已确认</span><strong>{{ result.summary?.confirmed ?? 0 }}</strong></article>
      <article><span>已排除</span><strong>{{ result.summary?.dismissed ?? 0 }}</strong></article>
    </div>

    <section v-if="result.summary?.by_rule?.length" class="rule-impact-strip" aria-label="规则影响">
      <article v-for="rule in result.summary.by_rule" :key="rule.rule_id">
        <span>{{ rule.rule_label }}</span><b>{{ rule.count }} 项</b><strong>{{ money(rule.impact_amount) }}</strong>
      </article>
      <p v-if="result.summary.impact_note">{{ result.summary.impact_note }}</p>
    </section>

    <form class="inline-filter" @submit.prevent="reloadFirstPage">
      <label>规则<select v-model="ruleId"><option value="">全部规则</option><option v-for="rule in ruleOptions" :key="rule.id" :value="rule.id">{{ rule.label }}</option></select></label>
      <label>核查状态<select v-model="reviewStatus"><option value="">全部状态</option><option value="pending">待核查</option><option value="confirmed">已确认问题</option><option value="dismissed">已排除</option></select></label>
      <button class="primary" type="submit">查询异常</button>
      <span class="result-state">{{ stateLabel }}</span>
    </form>

    <div v-if="state === 'loading' && !result.rows.length" class="workbench-empty">正在计算完整授权范围内的异常…</div>
    <div v-else-if="state === 'error' && !result.rows.length" class="workbench-empty error-state"><strong>异常加载失败</strong><span>{{ error }}</span><button class="ghost" @click="load">重试</button></div>
    <section v-else class="panel exception-table-panel">
      <div v-if="state === 'error' || state === 'stale'" class="stale-banner">当前展示上次成功结果。{{ error }}</div>
      <div class="table-scroll">
        <table class="exception-table">
          <thead><tr><th>级别 / 规则</th><th>对象</th><th>当前 / 基线</th><th>变化</th><th>影响</th><th>核查</th></tr></thead>
          <tbody>
            <tr v-for="row in result.rows" :key="row.id" tabindex="0" @click="openEvidence(row, $event)" @keydown.enter="openEvidence(row, $event)">
              <td><em :class="['severity', row.severity]">{{ severityLabel(row.severity) }}</em><b>{{ row.rule_label }}</b><small>{{ row.message }}</small></td>
              <td><b>{{ row.object_label || '—' }}</b><small>{{ [row.platform, row.shop_name, row.product_no].filter(Boolean).join(' / ') }}</small></td>
              <td><b>{{ displayExceptionMetric(row, 'current_value') }}</b><small>基线 {{ displayExceptionMetric(row, 'baseline_value') }}</small></td>
              <td>{{ row.change_pct == null ? '—' : `${money(row.change_pct)}%` }}</td>
              <td :class="{ loss: Number(row.impact_amount || 0) < 0 }">{{ displayExceptionMetric(row, 'impact_amount') }}</td>
              <td><span :class="['review-pill', row.status || 'pending']">{{ statusLabel(row.status) }}</span><small>{{ row.note || '点击查看证据' }}</small></td>
            </tr>
            <tr v-if="!result.rows.length"><td colspan="6"><div class="workbench-empty">当前已应用范围没有{{ type === 'operating' ? '经营' : '数据质量' }}异常。</div></td></tr>
          </tbody>
        </table>
      </div>
      <footer class="pagination">
        <span>共 {{ result.total || 0 }} 项 · 第 {{ result.page || page }} / {{ totalPages }} 页</span>
        <div><button class="ghost" :disabled="page <= 1 || state === 'loading'" @click="changePage(page - 1)">上一页</button><button class="ghost" :disabled="page >= totalPages || state === 'loading'" @click="changePage(page + 1)">下一页</button></div>
      </footer>
    </section>

    <div v-if="detail" class="workbench-dialog-backdrop" @click.self="closeEvidence">
      <section ref="detailDialog" class="workbench-dialog evidence-dialog" role="dialog" aria-modal="true" aria-labelledby="evidence-title" tabindex="-1" @keydown.esc="closeEvidence">
        <header><div><p class="kicker">EVIDENCE RECORD</p><h2 id="evidence-title">{{ detail.rule_label }}</h2></div><button class="icon-button" aria-label="关闭证据" @click="closeEvidence">×</button></header>
        <div class="evidence-lead"><strong>{{ detail.object_label }}</strong><p>{{ detail.message }}</p><p>{{ detail.suggestion }}</p></div>
        <dl class="evidence-grid">
          <template v-for="(entryValue, key) in detail.evidence" :key="key"><dt>{{ evidenceLabel(key) }}</dt><dd><EvidenceTree :value="entryValue" /></dd></template>
        </dl>
        <form class="review-form" @submit.prevent="saveReview">
          <label>核查结论<select v-model="review.status"><option value="pending">待核查</option><option value="confirmed">已确认问题</option><option value="dismissed">已排除</option></select></label>
          <label>核查备注<textarea v-model="review.note" maxlength="1000" placeholder="记录证据、判断或后续核查项"></textarea></label>
          <div v-if="dialogError" class="alert" role="alert">{{ dialogError }}</div>
          <div class="dialog-actions"><button class="ghost" type="button" @click="closeEvidence">取消</button><button class="primary" :disabled="saving">{{ saving ? '保存中…' : '保存核查' }}</button></div>
        </form>
      </section>
    </div>

    <div v-if="rulesOpen" class="workbench-dialog-backdrop" @click.self="closeRules">
      <section ref="rulesDialog" class="workbench-dialog rules-dialog" role="dialog" aria-modal="true" aria-labelledby="rules-title" tabindex="-1" @keydown.esc="closeRules">
        <header><div><p class="kicker">REFERENCE THRESHOLDS</p><h2 id="rules-title">经营异常参考阈值</h2></div><button class="icon-button" aria-label="关闭阈值设置" @click="closeRules">×</button></header>
        <p class="dialog-note">阈值用于发现需要核查的信号。负利润规则不受最低收入影响，规则版本会写入报告。</p>
        <form class="rules-grid" @submit.prevent="saveRules">
          <label v-for="rule in ruleDefinitions" :key="rule.key">{{ rule.label }}<div><input v-model.number="ruleDraft[rule.key]" type="number" min="0" step="0.01" required /><span>{{ rule.unit }}</span></div><small>{{ rule.help }}</small></label>
          <div v-if="dialogError" class="alert" role="alert">{{ dialogError }}</div>
          <footer class="dialog-actions"><span>当前版本 {{ result.rules_version || context?.rules_version || '—' }}</span><button class="ghost" type="button" @click="closeRules">取消</button><button class="primary" :disabled="saving">{{ saving ? '保存中…' : '保存并生成新版本' }}</button></footer>
        </form>
      </section>
    </div>
  </section>
</template>

<script setup>
import { computed, nextTick, onMounted, reactive, ref, watch } from "vue";
import { Download } from "lucide-vue-next";
import { buildExceptionQuery, displayExceptionMetric, evidenceFieldLabel } from "./contract.js";
import EvidenceTree from "./EvidenceTree.vue";

const props = defineProps({
  api: { type: Function, required: true },
  filters: { type: Object, required: true },
  context: { type: Object, default: () => ({}) },
  canOperating: Boolean,
  canQuality: Boolean,
  canSettings: Boolean,
  canExport: Boolean,
  refreshKey: { type: Number, default: 0 }
});
const emit = defineEmits(["status", "summary"]);
const type = ref(props.canOperating ? "operating" : "quality");
const page = ref(1);
const pageSize = 50;
const ruleId = ref("");
const reviewStatus = ref("");
const state = ref("idle");
const error = ref("");
const result = reactive({ rows: [], total: 0, page: 1, page_size: pageSize, summary: {}, rules: {}, rules_version: "", comparison: {} });
const detail = ref(null);
const detailDialog = ref(null);
const rulesDialog = ref(null);
const rulesOpen = ref(false);
const ruleDraft = reactive({});
const review = reactive({ status: "pending", note: "" });
const saving = ref(false);
const dialogError = ref("");
let requestToken = 0;
let returnFocus = null;

const ruleDefinitions = [
  { key: "low_margin_pct", label: "低利润率", unit: "%", help: "收入达到最低业务量后，低于该利润率触发。" },
  { key: "high_fee_pct", label: "高扣减费用率", unit: "%", help: "运费、辅料费和分摊费用占收入比例。" },
  { key: "decline_pct", label: "下降幅度", unit: "%", help: "与已选择基线相比的参考下降幅度。" },
  { key: "min_revenue", label: "最低收入", unit: "元", help: "用于过滤低样本信号，不影响负利润判断。" }
];
const ruleOptions = computed(() => {
  const rules = new Map();
  for (const row of result.rows) rules.set(row.rule_id, row.rule_label);
  for (const row of result.summary?.by_rule || []) rules.set(row.rule_id, row.rule_label);
  return [...rules].map(([id, label]) => ({ id, label }));
});
const totalPages = computed(() => Math.max(1, Math.ceil(Number(result.total || 0) / Number(result.page_size || pageSize))));
const queryString = computed(() => buildExceptionQuery(props.filters, { type: type.value, page: page.value, pageSize, ruleId: ruleId.value, status: reviewStatus.value }));
const exportUrl = computed(() => `/api/exceptions/export.xlsx?${queryString.value}`);
const stateLabel = computed(() => ({ idle: "等待查询", loading: "正在加载", loaded: "已更新", stale: "显示旧结果", error: "加载失败" })[state.value]);

watch(() => props.filters, () => { page.value = 1; state.value = result.rows.length ? "stale" : "loading"; load(); }, { deep: true });
watch(() => props.refreshKey, load);

onMounted(load);

async function load() {
  const token = ++requestToken;
  state.value = result.rows.length ? "stale" : "loading";
  error.value = "";
  emit("status", state.value);
  try {
    const data = await props.api(`/api/exceptions?${queryString.value}`);
    if (token !== requestToken) return;
    Object.assign(result, { ...data, rows: data.rows || [], summary: data.summary || {} });
    page.value = Number(data.page || page.value);
    state.value = "loaded";
    emit("summary", result.summary);
  } catch (err) {
    if (token !== requestToken || err.name === "AbortError") return;
    error.value = err.message || "异常加载失败";
    state.value = result.rows.length ? "error" : "error";
  } finally {
    if (token === requestToken) emit("status", state.value);
  }
}

function reloadFirstPage() { page.value = 1; load(); }
function changePage(next) { page.value = next; load(); }
function setType(next) { if (next === "quality" && !props.canQuality) return; type.value = next; page.value = 1; ruleId.value = ""; load(); }
function statusLabel(value) { return ({ pending: "待核查", confirmed: "已确认问题", dismissed: "已排除" })[value] || "待核查"; }
function severityLabel(value) { return ({ critical: "严重", high: "高", medium: "中", low: "低", error: "错误", warning: "警告" })[value] || value || "提示"; }
function money(value) { return Number(value || 0).toLocaleString("zh-CN", { maximumFractionDigits: 2 }); }
function evidenceLabel(key) { return evidenceFieldLabel(key); }

async function openEvidence(row, event) {
  returnFocus = event?.currentTarget || document.activeElement;
  detail.value = row;
  review.status = row.status || "pending";
  review.note = row.note || "";
  dialogError.value = "";
  await nextTick();
  detailDialog.value?.focus();
}
function closeEvidence() { detail.value = null; nextTick(() => returnFocus?.focus?.()); }

async function saveReview() {
  saving.value = true;
  dialogError.value = "";
  try {
    await props.api("/api/exceptions/review", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ filters: { ...props.filters }, type: type.value, id: detail.value.id, evidence_hash: detail.value.evidence_hash, status: review.status, note: review.note.trim() }) });
    closeEvidence();
    await load();
  } catch (err) { dialogError.value = err.message || "核查记录保存失败"; }
  finally { saving.value = false; }
}

async function openRules(event) {
  returnFocus = event?.currentTarget || document.activeElement;
  Object.assign(ruleDraft, props.context?.rules || result.rules || {});
  rulesOpen.value = true;
  dialogError.value = "";
  await nextTick();
  rulesDialog.value?.focus();
}
function closeRules() { rulesOpen.value = false; nextTick(() => returnFocus?.focus?.()); }
async function saveRules() {
  saving.value = true;
  dialogError.value = "";
  try {
    const data = await props.api("/api/workbench/rules", { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ rules: { ...ruleDraft } }) });
    Object.assign(result.rules, data.rules || {});
    result.rules_version = data.version;
    closeRules();
    await load();
  } catch (err) { dialogError.value = err.message || "阈值保存失败"; }
  finally { saving.value = false; }
}
</script>
