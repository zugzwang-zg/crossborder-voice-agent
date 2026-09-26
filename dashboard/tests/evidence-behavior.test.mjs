import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import test from "node:test";
import { build } from "esbuild";

const result = await build({ entryPoints: [fileURLToPath(new URL("../lib/evidence.ts", import.meta.url))], bundle: true, write: false, format: "esm", platform: "node" });
const { selectInsights } = await import(`data:text/javascript;base64,${Buffer.from(result.outputFiles[0].text).toString("base64")}`);
const data = JSON.parse(await readFile(new URL("../public/data/dashboard-data.demo.json", import.meta.url), "utf8"));

test("public subset exposes only conclusions with resolvable evidence", () => {
  assert.equal(selectInsights(data.insights, data.records).length, 11);
  assert.equal(data.insights.length, 15);
});

test("every suggestion in a filtered scope has evidence in that scope", () => {
  for (const language of ["en", "es"]) {
    for (const stars of [1, 2, 3, 4, 5]) {
      const records = data.records.filter((record) => record.language === language && record.stars === stars);
      const ids = new Set(records.map((record) => record.id));
      for (const { matchedIds } of selectInsights(data.insights, records)) {
        assert.ok(matchedIds.length);
        assert.ok(matchedIds.every((id) => ids.has(id)));
      }
    }
  }
  assert.deepEqual(selectInsights(data.insights, []), []);
});

test("duplicate references do not inflate current support", () => {
  const insight = { ...data.insights[0], data_evidence: { source_review_ids: ["r", "r", "missing"] } };
  assert.deepEqual(selectInsights([insight], [{ id: "r" }])[0].matchedIds, ["r"]);
});
