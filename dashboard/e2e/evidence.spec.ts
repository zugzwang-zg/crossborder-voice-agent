import { test, expect } from "@playwright/test";
import { readFileSync } from "node:fs";
import type { DashboardData } from "../lib/types";

const data: DashboardData = JSON.parse(readFileSync(new URL("../public/data/dashboard-data.demo.json", import.meta.url), "utf8"));

test("public evidence coverage is honest and a quote opens its source", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: /AI 洞察报告/ }).click();
  await expect(page.getByRole("heading", { level: 1 })).toHaveText("完整分析 15 条洞察 · 当前可追溯 11 条");
  await page.locator(".spine-quotes .evidence-quote").first().click();
  await expect(page.locator(".review-drawer")).toBeVisible();
  await expect(page.locator(".review-drawer")).toContainText("评论");
  await page.getByRole("button", { name: "关闭", exact: true }).click();
  await expect(page.locator(".review-drawer")).toHaveCount(0);
});

test("language and rating filters also constrain marketing recommendations", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: /购买动机/ }).click();
  for (const language of ["en", "es"]) {
    await page.getByRole("combobox", { name: "语言", exact: true }).selectOption(language);
    await page.getByRole("combobox", { name: "星级", exact: true }).selectOption("5");
    const ids = new Set(data.records.filter((r) => r.language === language && r.stars === 5).map((r) => r.id));
    const expected = data.insights.filter((insight) => insight.marketing_recommendation && insight.data_evidence.source_review_ids.some((id) => ids.has(id)));
    const titles = await page.locator(".translation-list strong").allTextContents();
    expect(titles.length).toBe(Math.min(expected.length, 4));
    for (const title of titles) expect(expected.some((insight) => insight.title === title)).toBe(true);
    if (!expected.length) await expect(page.getByRole("status")).toHaveText("当前筛选没有可追溯的营销建议。");
  }
});

test("invalid formal JSON falls back to the public bundle", async ({ page }) => {
  await page.route("**/data/dashboard-data.json", (route) => route.fulfill({ status: 200, contentType: "application/json", body: "broken json" }));
  await page.goto("/");
  await expect(page.getByText("PUBLIC DEMO", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: /AI 洞察报告/ }).click();
  await expect(page.getByRole("heading", { level: 1 })).toContainText("当前可追溯 11 条");
});
