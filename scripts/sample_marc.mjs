import crypto from "node:crypto";
import fs from "node:fs";
import fsp from "node:fs/promises";
import path from "node:path";
import readline from "node:readline";
import zlib from "node:zlib";

const sourceDir = process.argv[2];
const outputCsv = process.argv[3];
const seed = process.argv[4] ?? "crossborder-voice-v1";
const samplesPerStratum = 100;
const languages = ["en", "es"];
const requiredFields = [
  "review_id",
  "product_id",
  "language",
  "stars",
  "review_title",
  "review_body",
  "product_category",
];

if (!sourceDir || !outputCsv) {
  console.error(
    "Usage: node scripts/sample_marc.mjs <source_dir> <output_csv> [seed]",
  );
  process.exit(1);
}

function deterministicScore(reviewId) {
  return crypto
    .createHash("sha256")
    .update(`${seed}\u0000${reviewId}`, "utf8")
    .digest("hex");
}

function csvCell(value) {
  const text = value == null ? "" : String(value);
  return `"${text.replaceAll('"', '""')}"`;
}

function insertCandidate(bucket, candidate) {
  bucket.push(candidate);
  bucket.sort((a, b) => a.score.localeCompare(b.score));
  if (bucket.length > samplesPerStratum) {
    bucket.pop();
  }
}

const buckets = new Map();
const eligibleCounts = new Map();
for (const language of languages) {
  for (let stars = 1; stars <= 5; stars += 1) {
    const key = `${language}-${stars}`;
    buckets.set(key, []);
    eligibleCounts.set(key, 0);
  }
}

for (const language of languages) {
  const inputPath = path.join(sourceDir, `${language}_train.jsonl.gz`);
  const input = fs.createReadStream(inputPath).pipe(zlib.createGunzip());
  const lines = readline.createInterface({ input, crlfDelay: Infinity });

  for await (const line of lines) {
    if (!line.trim()) continue;
    const record = JSON.parse(line);
    if (
      record.language !== language ||
      record.product_category !== "beauty" ||
      !Number.isInteger(record.stars) ||
      record.stars < 1 ||
      record.stars > 5
    ) {
      continue;
    }

    const key = `${language}-${record.stars}`;
    eligibleCounts.set(key, eligibleCounts.get(key) + 1);
    const selected = Object.fromEntries(
      requiredFields.map((field) => [field, record[field] ?? ""]),
    );
    insertCandidate(buckets.get(key), {
      score: deterministicScore(record.review_id),
      record: selected,
    });
  }
}

const shortStrata = [...buckets.entries()].filter(
  ([, rows]) => rows.length < samplesPerStratum,
);
if (shortStrata.length > 0) {
  throw new Error(
    `Insufficient eligible rows: ${shortStrata
      .map(([key, rows]) => `${key}=${rows.length}`)
      .join(", ")}`,
  );
}

const sampled = [...buckets.entries()]
  .sort(([keyA], [keyB]) => keyA.localeCompare(keyB))
  .flatMap(([, rows]) =>
    rows
      .map(({ record }) => record)
      .sort((a, b) => a.review_id.localeCompare(b.review_id)),
  );

const csvLines = [
  requiredFields.map(csvCell).join(","),
  ...sampled.map((record) =>
    requiredFields.map((field) => csvCell(record[field])).join(","),
  ),
];

await fsp.mkdir(path.dirname(outputCsv), { recursive: true });
await fsp.writeFile(outputCsv, `\uFEFF${csvLines.join("\r\n")}\r\n`, "utf8");

const summary = {
  source_split: "train",
  category: "beauty",
  seed,
  selection_rule:
    "For each language × stars stratum, keep the 100 review_ids with the smallest SHA-256(seed + NUL + review_id) value.",
  sampled_rows: sampled.length,
  eligible_rows_by_stratum: Object.fromEntries(eligibleCounts),
  sampled_rows_by_stratum: Object.fromEntries(
    [...buckets.entries()].map(([key, rows]) => [key, rows.length]),
  ),
};

console.log(JSON.stringify(summary, null, 2));
