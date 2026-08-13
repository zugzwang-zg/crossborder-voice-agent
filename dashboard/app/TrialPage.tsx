"use client";

import {
  ArrowRight,
  Check,
  Download,
  FileSpreadsheet,
  LockKeyhole,
  RotateCcw,
  Sparkles,
  UploadCloud,
  X,
} from "lucide-react";
import { readSheet } from "read-excel-file/browser";
import { useRef, useState, type ChangeEvent, type DragEvent } from "react";

type UploadedReview = {
  rowNumber: number;
  id: string;
  language: "en" | "es";
  stars: number;
  text: string;
  product: string;
  date: string;
};

type AnalyzedReview = UploadedReview & {
  sentiment: "positive" | "negative" | "mixed" | "neutral";
  themes: string[];
};

type InvalidRow = { rowNumber: number; reason: string };

type ThemeResult = {
  key: string;
  label: string;
  count: number;
  negativeCount: number;
  example: string;
};

type TrialResult = {
  fileName: string;
  rows: AnalyzedReview[];
  invalidRows: InvalidRow[];
  averageStars: number;
  negativeCount: number;
  positiveCount: number;
  languages: { en: number; es: number };
  themes: ThemeResult[];
  suggestions: string[];
};

type ColumnKey = "id" | "language" | "stars" | "text" | "product" | "date";

const MAX_ROWS = 500;
const MAX_FILE_BYTES = 5 * 1024 * 1024;

const COLUMN_ALIASES: Record<ColumnKey, string[]> = {
  id: ["评论编号", "编号", "review_id", "id"],
  language: ["语言", "language", "lang"],
  stars: ["星级", "评分", "stars", "rating"],
  text: ["评论内容", "评论", "review_text", "review", "text", "content"],
  product: ["商品名称", "商品", "product_name", "product", "product_title"],
  date: ["日期", "评论日期", "date", "review_date"],
};

const THEME_RULES = [
  {
    key: "effect",
    label: "效果与预期",
    words: ["effect", "result", "work", "change", "funciona", "efecto", "resultado", "cambio", "sirve"],
  },
  {
    key: "delivery",
    label: "配送与到货",
    words: ["deliver", "shipping", "arrived", "late", "package never", "entrega", "envío", "llegó", "tarde", "paquete"],
  },
  {
    key: "packaging",
    label: "包装与破损",
    words: ["packaging", "seal", "leak", "broken", "damaged", "bottle", "empaque", "sello", "derram", "roto", "dañado", "botella"],
  },
  {
    key: "scent",
    label: "气味与香味",
    words: ["smell", "scent", "odor", "fragrance", "olor", "aroma", "fragancia"],
  },
  {
    key: "usability",
    label: "使用是否方便",
    words: ["easy", "difficult", "hard to", "apply", "instructions", "fácil", "difícil", "aplicar", "instrucciones"],
  },
  {
    key: "value",
    label: "价格与性价比",
    words: ["price", "expensive", "money", "value", "cheap", "precio", "caro", "dinero", "valor", "barato"],
  },
  {
    key: "comfort",
    label: "刺激与舒适度",
    words: ["irrit", "burn", "itch", "gentle", "soft", "irrita", "arde", "picor", "suave"],
  },
] as const;

const POSITIVE_WORDS = [
  "love", "great", "good", "excellent", "perfect", "recommend", "easy", "works", "worked",
  "encanta", "bueno", "excelente", "perfecto", "recomiendo", "fácil", "funciona", "funcionó",
];

const NEGATIVE_WORDS = [
  "bad", "poor", "terrible", "waste", "broken", "damaged", "late", "difficult", "irrit", "not work", "didn't work", "doesn't work",
  "malo", "terrible", "dinero perdido", "roto", "dañado", "tarde", "difícil", "irrita", "no funciona", "no funcionó",
];

const SENTIMENT_LABELS: Record<AnalyzedReview["sentiment"], string> = {
  positive: "偏正面",
  negative: "偏负面",
  mixed: "有好有坏",
  neutral: "暂不明确",
};

function normalizeHeader(value: string) {
  return value.trim().toLocaleLowerCase().replace(/[\s-]+/g, "_");
}

function escapeCsv(value: string | number) {
  const raw = String(value ?? "");
  const text = /^[=+\-@]/.test(raw) ? `'${raw}` : raw;
  return /[",\r\n]/.test(text) ? `"${text.replaceAll('"', '""')}"` : text;
}

function parseDelimitedText(input: string, delimiter: "," | "\t") {
  const rows: string[][] = [];
  let row: string[] = [];
  let value = "";
  let quoted = false;

  for (let index = 0; index < input.length; index += 1) {
    const character = input[index];
    const next = input[index + 1];
    if (character === '"' && quoted && next === '"') {
      value += '"';
      index += 1;
    } else if (character === '"') {
      quoted = !quoted;
    } else if (character === delimiter && !quoted) {
      row.push(value);
      value = "";
    } else if ((character === "\n" || character === "\r") && !quoted) {
      if (character === "\r" && next === "\n") index += 1;
      row.push(value);
      if (row.some((cell) => cell.trim())) rows.push(row);
      row = [];
      value = "";
    } else {
      value += character;
    }
  }
  row.push(value);
  if (row.some((cell) => cell.trim())) rows.push(row);
  return rows;
}

function inferLanguage(value: string): "en" | "es" | null {
  const normalized = value.trim().toLocaleLowerCase();
  if (["en", "eng", "english", "英语", "英文"].includes(normalized)) return "en";
  if (["es", "spa", "spanish", "español", "西语", "西班牙语"].includes(normalized)) return "es";
  return null;
}

function countMatches(text: string, words: readonly string[]) {
  return words.reduce((count, word) => count + (text.includes(word) ? 1 : 0), 0);
}

function analyzeReview(row: UploadedReview): AnalyzedReview {
  const normalized = row.text.toLocaleLowerCase();
  const positiveHits = countMatches(normalized, POSITIVE_WORDS);
  const negativeHits = countMatches(normalized, NEGATIVE_WORDS);
  let sentiment: AnalyzedReview["sentiment"] = "neutral";
  if (positiveHits && negativeHits) sentiment = "mixed";
  else if (negativeHits > positiveHits) sentiment = "negative";
  else if (positiveHits > negativeHits) sentiment = "positive";
  else if (row.stars <= 2) sentiment = "negative";
  else if (row.stars >= 4) sentiment = "positive";

  const themes = THEME_RULES
    .filter((theme) => theme.words.some((word) => normalized.includes(word)))
    .map((theme) => theme.key);
  return { ...row, sentiment, themes };
}

function buildResult(fileName: string, rows: UploadedReview[], invalidRows: InvalidRow[]): TrialResult {
  const analyzedRows = rows.map(analyzeReview);
  const averageStars = analyzedRows.reduce((sum, row) => sum + row.stars, 0) / Math.max(1, analyzedRows.length);
  const negativeCount = analyzedRows.filter((row) => row.sentiment === "negative" || row.sentiment === "mixed").length;
  const positiveCount = analyzedRows.filter((row) => row.sentiment === "positive").length;
  const languages = {
    en: analyzedRows.filter((row) => row.language === "en").length,
    es: analyzedRows.filter((row) => row.language === "es").length,
  };
  const themes = THEME_RULES.map((theme) => {
    const matched = analyzedRows.filter((row) => row.themes.includes(theme.key));
    return {
      key: theme.key,
      label: theme.label,
      count: matched.length,
      negativeCount: matched.filter((row) => row.sentiment === "negative" || row.sentiment === "mixed").length,
      example: matched[0]?.text || "",
    };
  }).filter((theme) => theme.count > 0).sort((a, b) => b.count - a.count);

  const topConcern = [...themes].sort((a, b) => b.negativeCount - a.negativeCount)[0];
  const topTheme = themes[0];
  const suggestions = [
    topConcern
      ? `先抽查“${topConcern.label}”相关的 ${topConcern.negativeCount} 条偏负面评论，确认是产品、页面说明还是履约问题。`
      : "当前没有明显集中的负面主题；建议先查看低星评论原文，确认是否存在样本外问题。",
    topTheme
      ? `把“${topTheme.label}”作为本轮复盘主题，分别整理正面证据和待改进证据，避免只看总量。`
      : "增加更多评论后再判断高频主题，少量记录不适合直接形成经营结论。",
    invalidRows.length
      ? `有 ${invalidRows.length} 行未进入分析，请按页面提示修正后重新上传。`
      : "表格格式完整；如要用于真实决策，请再补充商品、站点和日期，并人工复核代表性原文。",
  ];

  return {
    fileName,
    rows: analyzedRows,
    invalidRows,
    averageStars,
    negativeCount,
    positiveCount,
    languages,
    themes,
    suggestions,
  };
}

function rowsFromTable(table: string[][]) {
  if (table.length < 2) throw new Error("表格只有标题行，请至少填写 1 条评论。");
  const headers = table[0].map((cell) => normalizeHeader(String(cell ?? "")));
  const indexOf = (key: ColumnKey) => headers.findIndex((header) => COLUMN_ALIASES[key].map(normalizeHeader).includes(header));
  const indexes: Record<ColumnKey, number> = {
    id: indexOf("id"),
    language: indexOf("language"),
    stars: indexOf("stars"),
    text: indexOf("text"),
    product: indexOf("product"),
    date: indexOf("date"),
  };
  const missing = (["language", "stars", "text"] as ColumnKey[]).filter((key) => indexes[key] < 0);
  if (missing.length) {
    const labels: Record<ColumnKey, string> = { id: "评论编号", language: "语言", stars: "星级", text: "评论内容", product: "商品名称", date: "日期" };
    throw new Error(`缺少必填列：${missing.map((key) => labels[key]).join("、")}。请下载模板后再填写。`);
  }
  const inputRows = table.slice(1).filter((row) => row.some((cell) => String(cell ?? "").trim()));
  if (inputRows.length > MAX_ROWS) throw new Error(`免费试用每次最多分析 ${MAX_ROWS} 行，请拆分表格后重试。`);

  const rows: UploadedReview[] = [];
  const invalidRows: InvalidRow[] = [];
  inputRows.forEach((raw, index) => {
    const rowNumber = index + 2;
    const language = inferLanguage(String(raw[indexes.language] ?? ""));
    const stars = Number(String(raw[indexes.stars] ?? "").trim());
    const text = String(raw[indexes.text] ?? "").trim();
    const problems: string[] = [];
    if (!language) problems.push("语言请填写 en / es、English / Spanish、英语 / 西班牙语");
    if (!Number.isInteger(stars) || stars < 1 || stars > 5) problems.push("星级必须是 1—5 的整数");
    if (!text) problems.push("评论内容不能为空");
    if (problems.length) {
      invalidRows.push({ rowNumber, reason: problems.join("；") });
      return;
    }
    rows.push({
      rowNumber,
      id: indexes.id >= 0 && raw[indexes.id] ? String(raw[indexes.id]).trim() : `row-${rowNumber}`,
      language: language!,
      stars,
      text,
      product: indexes.product >= 0 ? String(raw[indexes.product] ?? "").trim() : "",
      date: indexes.date >= 0 ? String(raw[indexes.date] ?? "").trim() : "",
    });
  });
  if (!rows.length) throw new Error("没有可分析的评论。请根据错误提示修正表格后重试。");
  return { rows, invalidRows };
}

function downloadText(name: string, text: string, type = "text/csv;charset=utf-8") {
  const blob = new Blob(["\uFEFF", text], { type });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = name;
  anchor.click();
  URL.revokeObjectURL(url);
}

function createTemplate() {
  const rows = [
    ["评论编号", "语言", "星级", "评论内容", "商品名称", "日期"],
    ["demo-001", "en", "5", "Easy to use and the scent is gentle.", "示例商品 A", "2026-08-01"],
    ["demo-002", "es", "2", "El paquete llegó tarde y la botella estaba dañada.", "示例商品 A", "2026-08-02"],
  ];
  downloadText("CrossBorder-Voice-评论模板.csv", rows.map((row) => row.map(escapeCsv).join(",")).join("\r\n"));
}

const SAMPLE_TABLE = [
  ["评论编号", "语言", "星级", "评论内容", "商品名称", "日期"],
  ["sample-001", "en", "5", "Love the gentle scent and it is easy to apply.", "Glow Serum", "2026-08-01"],
  ["sample-002", "en", "2", "It did not work for me and the bottle arrived broken.", "Glow Serum", "2026-08-02"],
  ["sample-003", "es", "1", "El paquete llegó tarde y el sello estaba roto.", "Glow Serum", "2026-08-03"],
  ["sample-004", "es", "4", "Funciona bien, el aroma es suave y el precio es bueno.", "Glow Serum", "2026-08-04"],
  ["sample-005", "en", "3", "Good texture but too expensive for the size.", "Glow Serum", "2026-08-05"],
  ["sample-006", "es", "5", "Fácil de aplicar y noté un cambio positivo.", "Glow Serum", "2026-08-06"],
];

export default function TrialPage({ onExploreDemo }: { onExploreDemo: () => void }) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [isDragging, setIsDragging] = useState(false);
  const [isReading, setIsReading] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState<TrialResult | null>(null);

  const analyzeTable = (fileName: string, table: string[][]) => {
    const { rows, invalidRows } = rowsFromTable(table);
    setResult(buildResult(fileName, rows, invalidRows));
    setError("");
  };

  const handleFile = async (file?: File) => {
    if (!file) return;
    setError("");
    setResult(null);
    if (file.size > MAX_FILE_BYTES) {
      setError("文件超过 5MB。请删除图片、空白工作表或拆分数据后重试。");
      return;
    }
    const extension = file.name.split(".").pop()?.toLocaleLowerCase();
    if (!extension || !["csv", "tsv", "xlsx"].includes(extension)) {
      setError("暂时支持 CSV、TSV 和 XLSX 文件。旧版 XLS 请先在 Excel 中另存为 XLSX。");
      return;
    }
    setIsReading(true);
    try {
      const table = extension === "xlsx"
        ? (await readSheet(file)).map((row) => row.map((cell) => cell instanceof Date ? cell.toISOString().slice(0, 10) : String(cell ?? "")))
        : parseDelimitedText(await file.text(), extension === "tsv" ? "\t" : ",");
      analyzeTable(file.name, table);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "无法读取这个文件，请下载模板后重试。");
    } finally {
      setIsReading(false);
      if (inputRef.current) inputRef.current.value = "";
    }
  };

  const onDrop = (event: DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    setIsDragging(false);
    void handleFile(event.dataTransfer.files[0]);
  };

  const onFileChange = (event: ChangeEvent<HTMLInputElement>) => void handleFile(event.target.files?.[0]);

  const exportResult = () => {
    if (!result) return;
    const rows = [
      ["评论编号", "语言", "星级", "评论内容", "快速判断", "识别主题"],
      ...result.rows.map((row) => [row.id, row.language, row.stars, row.text, SENTIMENT_LABELS[row.sentiment], row.themes.map((key) => THEME_RULES.find((theme) => theme.key === key)?.label || key).join("；")]),
    ];
    downloadText("CrossBorder-Voice-快速分析结果.csv", rows.map((row) => row.map(escapeCsv).join(",")).join("\r\n"));
  };

  const reset = () => {
    setError("");
    setResult(null);
  };

  return (
    <section className="trial-page">
      <div className="trial-hero">
        <div className="trial-hero-copy">
          <span className="trial-eyebrow"><Sparkles size={15} /> 免费试用 · 不用注册</span>
          <h1>上传评论表格，几秒看清<br />顾客在喜欢什么、抱怨什么</h1>
          <p>按照模板填写评论、语言和星级。网页会在你的浏览器里完成快速汇总，给出高频问题、情绪分布和下一步建议。</p>
          <div className="trial-hero-actions">
            <button className="trial-primary" onClick={() => inputRef.current?.click()}><UploadCloud size={19} />选择表格</button>
            <button className="trial-secondary" onClick={() => analyzeTable("内置示例.csv", SAMPLE_TABLE)}><Sparkles size={18} />先看示例结果</button>
          </div>
          <div className="trial-privacy"><LockKeyhole size={16} /><span>文件只在当前浏览器中读取，不会上传到服务器，也不会调用付费 AI。</span></div>
        </div>
        <aside className="trial-receipt" aria-label="免费试用说明">
          <header><FileSpreadsheet size={21} /><strong>评论体检单</strong><span>FREE</span></header>
          <div className="receipt-line"><span>支持文件</span><strong>CSV / TSV / XLSX</strong></div>
          <div className="receipt-line"><span>单次上限</span><strong>500 行 · 5MB</strong></div>
          <div className="receipt-line"><span>必填内容</span><strong>语言 · 星级 · 评论</strong></div>
          <div className="receipt-line"><span>处理位置</span><strong>你的浏览器</strong></div>
          <footer><span /><b>上传即分析，不保存文件</b><span /></footer>
        </aside>
      </div>

      <div className="trial-steps" aria-label="使用步骤">
        <div><b>1</b><span><strong>下载模板</strong><small>保留三列必填内容</small></span></div>
        <ArrowRight size={18} />
        <div><b>2</b><span><strong>粘贴评论</strong><small>最多 500 行</small></span></div>
        <ArrowRight size={18} />
        <div><b>3</b><span><strong>上传查看结果</strong><small>无需等待人工处理</small></span></div>
      </div>

      <div className="trial-workspace">
        <article className="trial-upload-card">
          <div className="trial-card-heading">
            <div><span>第一步</span><h2>准备并上传表格</h2></div>
            <button onClick={createTemplate}><Download size={17} />下载 CSV 模板</button>
          </div>
          <div
            className={`trial-dropzone ${isDragging ? "dragging" : ""}`}
            onDragEnter={(event) => { event.preventDefault(); setIsDragging(true); }}
            onDragOver={(event) => event.preventDefault()}
            onDragLeave={() => setIsDragging(false)}
            onDrop={onDrop}
          >
            <input ref={inputRef} type="file" accept=".csv,.tsv,.xlsx" onChange={onFileChange} />
            <div className="dropzone-icon"><UploadCloud size={30} /></div>
            <strong>{isReading ? "正在读取表格…" : "把表格拖到这里"}</strong>
            <span>或者</span>
            <button disabled={isReading} onClick={() => inputRef.current?.click()}>选择电脑中的文件</button>
            <small>旧版 .xls 请先另存为 .xlsx</small>
          </div>
          <div className="template-guide">
            <h3>模板怎么填？</h3>
            <div><Check size={15} /><span><strong>语言</strong>：填写 en / es、English / Spanish 或中文名称</span></div>
            <div><Check size={15} /><span><strong>星级</strong>：填写 1—5 的整数</span></div>
            <div><Check size={15} /><span><strong>评论内容</strong>：每行一条完整评论</span></div>
            <div className="optional"><Check size={15} /><span><strong>可选</strong>：评论编号、商品名称、日期</span></div>
          </div>
          {error && <div className="trial-error" role="alert"><X size={18} /><div><strong>暂时无法分析</strong><span>{error}</span></div></div>}
        </article>

        <aside className="trial-explain-card">
          <span>你会得到什么</span>
          <h2>一份能直接开始复盘的结果</h2>
          <ul>
            <li><b>整体情况</b><span>平均星级、正负反馈和语言数量</span></li>
            <li><b>高频主题</b><span>效果、配送、包装、气味、价格等</span></li>
            <li><b>下一步建议</b><span>告诉你先读哪批评论、找谁确认</span></li>
            <li><b>结果下载</b><span>下载带快速判断和主题的 CSV</span></li>
          </ul>
          <button onClick={onExploreDemo}>没有自己的数据？浏览完整演示 <ArrowRight size={16} /></button>
          <p>快速分析使用透明的关键词与星级规则，适合初筛，不代替人工判断或专业模型分析。</p>
        </aside>
      </div>

      {result && (
        <section className="trial-results" aria-live="polite">
          <header className="results-heading">
            <div>
              <span>分析完成 · {result.fileName}</span>
              <h2>先看整体，再决定读哪些原文</h2>
              <p>{result.rows.length} 行进入分析{result.invalidRows.length ? `，${result.invalidRows.length} 行需要修正` : "，表格格式完整"}。</p>
            </div>
            <div>
              <button onClick={exportResult}><Download size={17} />下载分析结果</button>
              <button className="results-reset" onClick={reset}><RotateCcw size={17} />重新分析</button>
            </div>
          </header>

          <div className="trial-metrics">
            <div><span>有效评论</span><strong>{result.rows.length}</strong><small>条</small></div>
            <div><span>平均星级</span><strong>{result.averageStars.toFixed(1)}</strong><small>/ 5</small></div>
            <div className="negative"><span>需要优先阅读</span><strong>{result.negativeCount}</strong><small>条偏负面或有分歧</small></div>
            <div className="positive"><span>可提炼亮点</span><strong>{result.positiveCount}</strong><small>条偏正面</small></div>
          </div>

          <div className="results-grid">
            <article className="theme-results">
              <div className="result-title"><span>高频主题</span><strong>评论主要在谈什么</strong></div>
              {result.themes.length ? result.themes.slice(0, 6).map((theme) => (
                <div className="theme-result" key={theme.key}>
                  <div><strong>{theme.label}</strong><span>{theme.negativeCount} 条需要优先阅读</span></div>
                  <b>{theme.count}</b>
                  <div className="theme-bar"><span style={{ width: `${(theme.count / Math.max(1, result.themes[0].count)) * 100}%` }} /></div>
                  <q>{theme.example}</q>
                </div>
              )) : <p className="no-theme">暂未识别集中主题。可以增加评论数量，或直接查看低星评论原文。</p>}
            </article>
            <article className="next-actions">
              <div className="result-title"><span>建议从这里开始</span><strong>三步完成第一次复盘</strong></div>
              {result.suggestions.map((suggestion, index) => (
                <div key={suggestion}><b>{index + 1}</b><p>{suggestion}</p></div>
              ))}
              <aside><strong>语言分布</strong><span>英语 {result.languages.en} 条 · 西班牙语 {result.languages.es} 条</span><small>数量差异不等于市场差异，请分别阅读原文。</small></aside>
            </article>
          </div>

          {result.invalidRows.length > 0 && (
            <details className="invalid-rows">
              <summary>查看 {result.invalidRows.length} 行需要修正的内容</summary>
              {result.invalidRows.slice(0, 20).map((row) => <div key={row.rowNumber}><strong>第 {row.rowNumber} 行</strong><span>{row.reason}</span></div>)}
            </details>
          )}

          <article className="trial-table-card">
            <div className="result-title"><span>抽查原文</span><strong>前 {Math.min(12, result.rows.length)} 条分析结果</strong></div>
            <div className="trial-table-scroll">
              <table>
                <thead><tr><th>编号</th><th>语言</th><th>星级</th><th>快速判断</th><th>识别主题</th><th>评论内容</th></tr></thead>
                <tbody>{result.rows.slice(0, 12).map((row) => (
                  <tr key={`${row.id}-${row.rowNumber}`}>
                    <td>{row.id}</td><td>{row.language === "en" ? "英语" : "西班牙语"}</td><td>{row.stars} 星</td>
                    <td><span className={`sentiment-pill ${row.sentiment}`}>{SENTIMENT_LABELS[row.sentiment]}</span></td>
                    <td>{row.themes.length ? row.themes.map((key) => THEME_RULES.find((theme) => theme.key === key)?.label).filter(Boolean).join("、") : "未集中"}</td>
                    <td>{row.text}</td>
                  </tr>
                ))}</tbody>
              </table>
            </div>
          </article>
        </section>
      )}
    </section>
  );
}
