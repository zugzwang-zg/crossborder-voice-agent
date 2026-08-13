import assert from "node:assert/strict";
import { existsSync } from "node:fs";
import { readFile } from "node:fs/promises";
import test from "node:test";

const root = new URL("../", import.meta.url);

test("public demo bundle preserves sample traceability", async () => {
  const payload = JSON.parse(
    await readFile(new URL("public/data/dashboard-data.demo.json", root), "utf8"),
  );
  assert.equal(payload.insights.length, 15);
  assert.equal(payload.meta.traceability.failures, 0);
  assert.equal(payload.records.length, 10);
  assert.equal(payload.meta.fullDatasetRecords, 1000);
  assert.equal(payload.meta.traceability.status, "demo_subset");
  const reviewIds = new Set(payload.records.map((record) => record.id));
  let insightsWithEvidence = 0;
  for (const insight of payload.insights) {
    assert.equal("mean_model_confidence" in insight.data_evidence, false);
    assert.equal(insight.support_volume_tier, "high");
    assert.equal(insight.confidence_or_evidence_grade, "high_support_volume");
    if (insight.data_evidence.source_review_ids.length) insightsWithEvidence += 1;
    for (const reviewId of insight.data_evidence.source_review_ids) {
      assert.ok(reviewIds.has(reviewId), `${reviewId} must resolve to a source review`);
    }
  }
  assert.ok(insightsWithEvidence > 0);
});

const formalBundle = new URL("public/data/dashboard-data.json", root);
test(
  "local formal bundle preserves all records and insight traceability",
  { skip: !existsSync(formalBundle) },
  async () => {
    const payload = JSON.parse(await readFile(formalBundle, "utf8"));
    assert.equal(payload.records.length, 1000);
    assert.equal(payload.insights.length, 15);
    assert.equal(payload.meta.traceability.status, "pass");
    assert.equal(payload.meta.traceability.failures, 0);
    const reviewIds = new Set(payload.records.map((record) => record.id));
    for (const insight of payload.insights) {
      assert.ok(insight.data_evidence.source_review_ids.length > 0);
      for (const reviewId of insight.data_evidence.source_review_ids) {
        assert.ok(reviewIds.has(reviewId), `${reviewId} must resolve to a source review`);
      }
    }
  },
);

test("dashboard implements a local-file free trial plus six plain-language views", async () => {
  const page = await readFile(new URL("app/page.tsx", root), "utf8");
  const trial = await readFile(new URL("app/TrialPage.tsx", root), "utf8");
  for (const filter of ["product", "subcategory", "language", "stars", "sentiment", "aspect", "issue", "scenario"]) {
    assert.match(page, new RegExp(`filters\\.${filter}`));
  }
  for (const view of ["trial", "overview", "pain", "motivation", "language", "insights"]) {
    assert.match(page, new RegExp(`key: "${view}"`));
  }
  assert.match(page, /ReviewDrawer/);
  assert.match(page, /advanced-filters/);
  assert.match(page, /active-filter-rail/);
  assert.match(page, /const pageSize = 30/);
  assert.match(page, /stars_desc/);
  assert.match(page, /date_desc/);
  assert.match(page, /review-source-text/);
  assert.match(page, /HighlightText/);
  assert.match(page, /loadAttempt/);
  assert.match(page, /data_evidence\.source_review_ids/);
  assert.match(page, /查看评论原文/);
  assert.match(page, /dashboard-data\.demo\.json/);
  assert.match(page, /演示数据没有商品名称/);
  assert.match(page, /结果只说明这批评论，不代表整个市场/);
  assert.match(page, /scope-decision-card/);
  for (const status of ["new", "needs_validation", "accepted", "rejected", "resolved"]) {
    assert.match(page, new RegExp(`${status}:`));
  }
  assert.match(page, /crossborder-voice\.insight-feedback\.v1/);
  assert.match(page, /标签错误/);
  assert.match(page, /证据不足/);
  assert.match(page, /建议无效/);
  assert.match(page, /导出反馈/);
  assert.match(page, /处理记录单独保存在当前浏览器/);
  assert.match(page, /crossborder-voice\.insight-comparison\.v1/);
  assert.match(page, /洞察版本对比/);
  assert.match(page, /新增、消失与支持量变化/);
  assert.match(page, /数量表示“被提到多少次”/);
  assert.match(trial, /read-excel-file\/browser/);
  assert.match(trial, /文件只在当前浏览器中读取/);
  assert.match(trial, /CSV、TSV 和 XLSX/);
  assert.match(trial, /MAX_ROWS = 500/);
  assert.match(trial, /MAX_FILE_BYTES = 5 \* 1024 \* 1024/);
  assert.match(trial, /下载 CSV 模板/);
  assert.match(trial, /下载分析结果/);
  assert.match(trial, /没有可分析的评论/);
});

test("production HTML renders the branded dashboard shell", async () => {
  const workerUrl = new URL("dist/server/index.js", root);
  workerUrl.searchParams.set("test", `${process.pid}-${Date.now()}`);
  const { default: worker } = await import(workerUrl.href);
  const response = await worker.fetch(
    new Request("http://localhost/", { headers: { accept: "text/html" } }),
    { ASSETS: { fetch: async () => new Response("Not found", { status: 404 }) } },
    { waitUntil() {}, passThroughOnException() {} },
  );
  assert.equal(response.status, 200);
  const html = await response.text();
  assert.match(html, /CrossBorder Voice/);
  assert.match(html, /免费评论表格分析/);
  assert.doesNotMatch(html, /codex-preview/);
});
