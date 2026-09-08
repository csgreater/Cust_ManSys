<template>
  <section class="home-priority">
    <div class="coverage-banner">
      <div>
        <p class="kicker">DATA COVERAGE</p>
        <strong>{{ coverageTitle }}</strong>
        <small>最近成功数据：{{ context?.latest_data_at ? formatDate(context.latest_data_at) : "尚无记录" }}</small>
      </div>
      <button v-if="context?.latest_period && !hasData" class="ghost" type="button" @click="$emit('use-latest')">查看最近有数据月份</button>
    </div>

    <div v-if="status === 'loading'" class="workbench-empty">正在核对异常、报告和数据范围…</div>
    <div v-else-if="status === 'error'" class="workbench-empty error-state">
      <strong>工作台加载失败</strong><span>{{ error || "请重新加载。" }}</span><button class="ghost" type="button" @click="$emit('retry')">重试</button>
    </div>
    <div v-else class="priority-grid">
      <article v-if="canAnalytics" class="priority-card exception-card">
        <div class="priority-index">01 / EXCEPTIONS</div>
        <p>待核查异常</p>
        <strong>{{ exceptionSummary?.pending ?? exceptionSummary?.total ?? 0 }}</strong>
        <span>{{ topRule }}</span>
        <button class="primary" type="button" @click="$emit('open', 'exceptions')">进入异常中心</button>
      </article>
      <article v-if="canAnalytics" class="priority-card report-card">
        <div class="priority-index">02 / REPORTS</div>
        <p>本期报告</p>
        <strong>{{ latestReport ? `V${latestReport.version}` : "未生成" }}</strong>
        <span>{{ reportCaption }}</span>
        <button class="primary" type="button" @click="$emit('open', 'reports')">{{ latestReport ? "查看报告" : "生成报告" }}</button>
      </article>
      <article class="priority-card data-card">
        <div class="priority-index">03 / DATA STATE</div>
        <p>本期数据</p>
        <strong>{{ hasData ? `${Number(summary?.detail_rows || 0).toLocaleString("zh-CN")} 行` : "未查到" }}</strong>
        <span>{{ hasData ? `覆盖 ${Number(summary?.orders || 0).toLocaleString("zh-CN")} 个订单` : "当前范围未查到数据，不代表经营归零" }}</span>
        <button v-if="!hasData && canImport" class="ghost" type="button" @click="$emit('open', 'imports')">导入数据</button>
      </article>
    </div>
  </section>
</template>

<script setup>
import { computed } from "vue";

const props = defineProps({
  context: { type: Object, default: () => ({}) },
  summary: { type: Object, default: () => ({}) },
  exceptionSummary: { type: Object, default: () => ({}) },
  latestReport: { type: Object, default: null },
  status: { type: String, default: "loaded" },
  error: { type: String, default: "" },
  canImport: Boolean,
  canAnalytics: Boolean
});
defineEmits(["open", "use-latest", "retry"]);

const hasData = computed(() => Number(props.summary?.detail_rows || 0) > 0 || Number(props.summary?.orders || 0) > 0);
const coverageTitle = computed(() => props.context?.latest_period
  ? `最近有数据月份 ${props.context.latest_period.start_time} 至 ${props.context.latest_period.end_time}`
  : "当前授权范围尚未发现可用数据");
const topRule = computed(() => props.exceptionSummary?.by_rule?.[0]
  ? `${props.exceptionSummary.by_rule[0].rule_label} · ${props.exceptionSummary.by_rule[0].count} 项`
  : "本期没有待处理的规则命中");
const reportCaption = computed(() => {
  if (!props.latestReport) return "按当前已应用范围生成可复核版本";
  if (props.latestReport.stale) return "当前范围已有新数据，建议重新生成新版本";
  return `${props.latestReport.title} · ${formatDate(props.latestReport.created_at)}`;
});

function formatDate(value) {
  if (!value) return "—";
  return `${value}`.replace("T", " ").slice(0, 16);
}
</script>
