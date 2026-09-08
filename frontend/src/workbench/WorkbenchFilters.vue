<template>
  <section class="workbench-filter" aria-label="分析条件">
    <div class="filter-ledger">
      <div>
        <p class="kicker">APPLIED SCOPE</p>
        <strong>已应用：{{ appliedSummary }}</strong>
      </div>
      <span :class="['load-state', status]">{{ statusLabel }}</span>
    </div>
    <form @submit.prevent="apply">
      <label>数据所属期·开始<input v-model="draft.start_time" type="date" required /></label>
      <label>数据所属期·结束<input v-model="draft.end_time" type="date" required /></label>
      <label>比较基线
        <select v-model="draft.comparison_mode">
          <option value="previous_period">前一周期</option>
          <option value="year_over_year">去年同期</option>
        </select>
      </label>
      <label v-for="field in visibleFields" :key="field.key">{{ field.label }}
        <input v-model="draft[field.key]" :list="`${field.key}-catalog`" :placeholder="field.placeholder || '全部'" />
        <datalist :id="`${field.key}-catalog`"><option v-for="value in catalog(field.key)" :key="value" :value="value" /></datalist>
      </label>
      <div class="filter-actions">
        <button class="ghost" type="button" @click="reset">清空条件</button>
        <button v-if="context?.latest_period" class="ghost" type="button" @click="useLatest">最近有数据月份</button>
        <button class="primary" type="submit" :disabled="!hasChanges">应用条件</button>
      </div>
    </form>
    <p v-if="validationError" class="filter-error" role="alert">{{ validationError }}</p>
  </section>
</template>

<script setup>
import { computed, reactive, watch } from "vue";

const props = defineProps({
  modelValue: { type: Object, required: true },
  context: { type: Object, default: () => ({}) },
  fields: { type: Array, default: () => ["dept", "platform", "shop_name"] },
  status: { type: String, default: "idle" }
});
const emit = defineEmits(["apply"]);

const definitions = [
  { key: "dept", label: "部门" },
  { key: "platform", label: "平台" },
  { key: "shop_name", label: "店铺" },
  { key: "category", label: "大类" },
  { key: "product_classification", label: "货品分类" },
  { key: "product", label: "产品 / SKU", placeholder: "名称、货号或 SKU" },
  { key: "province", label: "省份" },
  { key: "city", label: "城市" },
  { key: "order_source", label: "订单来源" }
];
const draft = reactive({});
const validationError = computed(() => draft.start_time && draft.end_time && draft.start_time > draft.end_time ? "开始日期不能晚于结束日期" : "");
const visibleFields = computed(() => definitions.filter((item) => props.fields.includes(item.key)));
const serializedDraft = computed(() => JSON.stringify(draft));
const serializedApplied = computed(() => JSON.stringify(props.modelValue));
const hasChanges = computed(() => !validationError.value && serializedDraft.value !== serializedApplied.value);
const statusLabel = computed(() => ({ loading: "加载中", loaded: "已更新", stale: "显示旧结果", error: "加载失败", idle: "等待查询" })[props.status] || props.status);
const appliedSummary = computed(() => {
  const parts = [`${props.modelValue.start_time || "—"} 至 ${props.modelValue.end_time || "—"}`];
  for (const field of definitions) if (props.modelValue[field.key]) parts.push(`${field.label} ${props.modelValue[field.key]}`);
  return parts.join(" · ");
});

watch(() => props.modelValue, (value) => Object.assign(draft, value), { immediate: true, deep: true });

function catalog(key) {
  return props.context?.catalogs?.[key] || [];
}

function apply() {
  if (validationError.value) return;
  emit("apply", { ...draft });
}

function reset() {
  for (const field of definitions) draft[field.key] = "";
  draft.comparison_mode = "previous_period";
}

function useLatest() {
  draft.start_time = props.context.latest_period.start_time;
  draft.end_time = props.context.latest_period.end_time;
  apply();
}
</script>
