const nonReportFilterKeys = new Set(["page", "page_size", "type", "rule_id", "status"]);

export function compactFilters(filters = {}, excluded = new Set()) {
  return Object.fromEntries(Object.entries(filters).filter(([key, value]) => {
    if (excluded.has(key)) return false;
    return value !== "" && value !== null && value !== undefined;
  }));
}

export function buildExceptionQuery(filters, { type, page = 1, pageSize = 50, ruleId = "", status = "" }) {
  const params = new URLSearchParams(compactFilters(filters));
  params.set("type", type);
  params.set("page", `${page}`);
  params.set("page_size", `${pageSize}`);
  if (ruleId) params.set("rule_id", ruleId);
  if (status) params.set("status", status);
  return params.toString();
}

export function buildReportPayload(filters, reportType, title = "") {
  const payload = {
    filters: compactFilters(filters, nonReportFilterKeys),
    report_type: reportType
  };
  if (`${title}`.trim()) payload.title = `${title}`.trim();
  return payload;
}

export function reportBody(report = {}) {
  return report.body && typeof report.body === "object" ? report.body : report;
}

export function displayExceptionMetric(row = {}, key) {
  const value = row[key];
  if (value === null || value === undefined || value === "") return "—";
  if (row.type === "quality" && ["current_value", "baseline_value"].includes(key)) return `${value}`;
  const number = Number(value);
  return Number.isFinite(number)
    ? number.toLocaleString("zh-CN", { maximumFractionDigits: 2 })
    : `${value}`;
}

const evidenceLabels = {
  group: "核查对象", current: "本期数据", previous: "基线数据", rule: "触发规则",
  rules: "阈值快照", period: "本期范围", comparison: "比较范围", filters: "筛选范围",
  start_time: "开始日期", end_time: "结束日期", comparison_mode: "比较方式",
  dept: "部门", platform: "平台", shop_name: "店铺", category: "大类",
  product_classification: "货品分类", product: "产品", product_no: "货号", product_name: "产品名称",
  province: "省份", city: "城市", order_source: "订单来源", sku_id: "SKU",
  revenue: "销售额", profit: "利润", fees: "扣减费用", qty: "销量", orders: "订单数", detail_rows: "明细行数",
  freight: "运费", aux_material: "辅料费", share_cost: "分摊费用", cost: "成本", share_receivable: "分摊应收",
  express_fee: "快递费（旁证）", logistics_fee: "物流费（旁证）",
  id: "规则编号", low_margin_pct: "低利润率阈值", high_fee_pct: "高扣减费用率阈值",
  decline_pct: "下降阈值", min_revenue: "最低收入", mode: "比较方式", label: "比较说明",
  batch_no: "来源批次", row_no: "源行号", error_message: "阻断错误", warning_message: "校验警告",
  current_period: "当前期间", baseline_period: "基线期间", formula: "指标口径"
};

export function evidenceFieldLabel(key) {
  return evidenceLabels[key] || key;
}

function normalizedScope(filters = {}) {
  const compact = compactFilters(filters, nonReportFilterKeys);
  compact.comparison_mode = compact.comparison_mode || "previous_period";
  return Object.fromEntries(Object.entries(compact).sort(([left], [right]) => left.localeCompare(right)));
}

export function matchingCurrentReport(reports = [], filters = {}, { dataVersion = "", rulesVersion = "" } = {}) {
  const expected = JSON.stringify(normalizedScope(filters));
  const match = reports.find((report) => JSON.stringify(normalizedScope(report.filters || {})) === expected);
  if (!match) return null;
  return {
    ...match,
    stale: Boolean(match.stale)
      || Boolean(dataVersion && match.data_version !== dataVersion)
      || Boolean(rulesVersion && match.rules_version !== rulesVersion)
  };
}
