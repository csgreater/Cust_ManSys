import assert from "node:assert/strict";
import test from "node:test";

import { buildExceptionQuery, buildReportPayload, displayExceptionMetric, evidenceFieldLabel, matchingCurrentReport, reportBody } from "../src/workbench/contract.js";

test("exception queries always carry the applied period, type and page while omitting empty filters", () => {
  const query = new URLSearchParams(buildExceptionQuery({
    start_time: "2026-08-01",
    end_time: "2026-08-31",
    platform: "抖音",
    shop_name: "",
    comparison_mode: "previous_period"
  }, { type: "operating", page: 3, pageSize: 50, ruleId: "low_margin", status: "pending" }));

  assert.equal(query.get("start_time"), "2026-08-01");
  assert.equal(query.get("end_time"), "2026-08-31");
  assert.equal(query.get("type"), "operating");
  assert.equal(query.get("page"), "3");
  assert.equal(query.get("page_size"), "50");
  assert.equal(query.get("shop_name"), null);
});

test("report generation uses the complete applied filter scope without page state", () => {
  assert.deepEqual(buildReportPayload({
    start_time: "2026-08-01",
    end_time: "2026-08-31",
    dept: "华东",
    page: 4,
    page_size: 20
  }, "monthly", "八月经营复盘"), {
    filters: { start_time: "2026-08-01", end_time: "2026-08-31", dept: "华东" },
    report_type: "monthly",
    title: "八月经营复盘"
  });
});

test("reportBody supports saved reports with nested body and flattened legacy data", () => {
  assert.deepEqual(reportBody({ body: { summary: { revenue: 88 } }, summary: { revenue: 11 } }).summary, { revenue: 88 });
  assert.deepEqual(reportBody({ summary: { revenue: 11 }, sections: [] }).summary, { revenue: 11 });
});

test("quality report values keep their validation text while operating metrics stay numeric", () => {
  assert.equal(displayExceptionMetric({ type: "quality", current_value: "发货日期格式错误" }, "current_value"), "发货日期格式错误");
  assert.equal(displayExceptionMetric({ type: "operating", current_value: "1234.5" }, "current_value"), "1,234.5");
});

test("evidence labels cover top-level groups and supporting fee fields", () => {
  assert.equal(evidenceFieldLabel("current"), "本期数据");
  assert.equal(evidenceFieldLabel("group"), "核查对象");
  assert.equal(evidenceFieldLabel("express_fee"), "快递费（旁证）");
  assert.equal(evidenceFieldLabel("logistics_fee"), "物流费（旁证）");
});

test("the home report card only selects a report for the complete applied scope and derives staleness", () => {
  const reports = [
    { id: "june", version: 2, filters: { start_time: "2026-06-01", end_time: "2026-06-30" }, data_version: "old", rules_version: "r1" },
    { id: "aug", version: 1, filters: { start_time: "2026-08-01", end_time: "2026-08-31", platform: "抖音" }, data_version: "d1", rules_version: "r1" }
  ];

  assert.equal(matchingCurrentReport(reports, { start_time: "2026-08-01", end_time: "2026-08-31", platform: "" }, {}), null);
  const match = matchingCurrentReport(reports, { start_time: "2026-08-01", end_time: "2026-08-31", platform: "抖音", comparison_mode: "previous_period" }, { dataVersion: "d2", rulesVersion: "r1" });
  assert.equal(match.id, "aug");
  assert.equal(match.stale, true);
});
