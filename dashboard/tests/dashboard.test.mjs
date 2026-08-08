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

test("dashboard implements scope and analysis filters plus five views", async () => {
  const page = await readFile(new URL("app/page.tsx", root), "utf8");
  for (const filter of ["product", "subcategory", "language", "stars", "sentiment", "aspect", "issue", "scenario"]) {
    assert.match(page, new RegExp(`filters\\.${filter}`));
  }
  for (const view of ["overview", "pain", "motivation", "language", "insights"]) {
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
  assert.match(page, /评论证据库/);
  assert.match(page, /dashboard-data\.demo\.json/);
  assert.match(page, /不生成虚假的单品洞察/);
  assert.match(page, /分层样本，不代表真实市场占比/);
  assert.match(page, /scope-decision-card/);
  for (const status of ["new", "needs_validation", "accepted", "rejected", "resolved"]) {
    assert.match(page, new RegExp(`${status}:`));
  }
  assert.match(page, /crossborder-voice\.insight-feedback\.v1/);
  assert.match(page, /标签错误/);
  assert.match(page, /证据不足/);
  assert.match(page, /建议无效/);
  assert.match(page, /导出反馈/);
  assert.match(page, /人工反馈独立保存/);
  assert.match(page, /crossborder-voice\.insight-comparison\.v1/);
  assert.match(page, /洞察版本对比/);
  assert.match(page, /新增、消失与支持量变化/);
  assert.match(page, /未校准，不是正确概率/);
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
  assert.match(html, /Crossborder Voice/);
  assert.match(html, /跨境电商评论洞察台/);
  assert.doesNotMatch(html, /codex-preview/);
});
