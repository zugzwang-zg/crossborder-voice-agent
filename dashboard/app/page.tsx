"use client";

import {
  BarChart3,
  BookOpenText,
  ChevronRight,
  CircleDot,
  FileSearch,
  Filter,
  Languages,
  Lightbulb,
  Menu,
  MessageSquareQuote,
  RotateCcw,
  Search,
  ShoppingBag,
  Sparkles,
  Star,
  X,
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import type { Review, Insight, Labels, DashboardData } from "../lib/types";
import { selectInsights } from "../lib/evidence";

type PageKey = "overview" | "pain" | "motivation" | "language" | "insights";
type Filters = {
  language: string;
  stars: string;
  sentiment: string;
  aspect: string;
  issue: string;
  scenario: string;
};

const INITIAL_FILTERS: Filters = {
  language: "all",
  stars: "all",
  sentiment: "all",
  aspect: "all",
  issue: "all",
  scenario: "all",
};

const PAGE_ITEMS: {
  key: PageKey;
  number: string;
  label: string;
  subtitle: string;
  icon: typeof BarChart3;
}[] = [
  { key: "overview", number: "01", label: "市场总览", subtitle: "样本与情绪", icon: BarChart3 },
  { key: "pain", number: "02", label: "产品痛点", subtitle: "问题与属性", icon: CircleDot },
  { key: "motivation", number: "03", label: "购买动机", subtitle: "场景与卖点", icon: ShoppingBag },
  { key: "language", number: "04", label: "跨语对照", subtitle: "英语 vs 西语", icon: Languages },
  { key: "insights", number: "05", label: "AI 洞察报告", subtitle: "证据到行动", icon: Lightbulb },
];

const sentimentColors: Record<string, string> = {
  positive: "#1c806b",
  negative: "#dc5a36",
  mixed: "#d3a333",
  neutral: "#6f7e86",
  uncertain: "#9f8fc2",
};

const polarityLabel: Record<string, string> = {
  positive: "正向",
  negative: "负向",
  mixed: "混合",
  neutral: "中性",
};

function countBy<T>(items: T[], key: (item: T) => string) {
  const counts = new Map<string, number>();
  items.forEach((item) => {
    const value = key(item);
    counts.set(value, (counts.get(value) || 0) + 1);
  });
  return [...counts.entries()].sort((a, b) => b[1] - a[1]);
}

function pct(value: number, total: number, digits = 1) {
  return total ? `${((value / total) * 100).toFixed(digits)}%` : "0.0%";
}

function labelOf(labels: Record<string, string>, code: string) {
  return labels[code] || code.replaceAll("_", " ");
}

function selectOptions(labels: Record<string, string>) {
  return Object.entries(labels).sort((a, b) => a[1].localeCompare(b[1], "zh-CN"));
}

function StarLine({ stars }: { stars: number }) {
  return (
    <span className="star-line" aria-label={`${stars} 星`}>
      {Array.from({ length: 5 }).map((_, index) => (
        <Star key={index} size={12} fill={index < stars ? "currentColor" : "none"} />
      ))}
    </span>
  );
}

function EvidenceButton({
  review,
  onOpen,
  compact = false,
}: {
  review: Review;
  onOpen: (review: Review) => void;
  compact?: boolean;
}) {
  return (
    <button className={`evidence-quote ${compact ? "compact" : ""}`} onClick={() => onOpen(review)}>
      <span className="quote-meta">
        <span>{review.language.toUpperCase()}</span>
        <StarLine stars={review.stars} />
        <span>{review.id}</span>
      </span>
      <span className="quote-text">“{review.body || review.title}”</span>
      <span className="trace-link">
        查看分析证据 <ChevronRight size={14} />
      </span>
    </button>
  );
}

function DistributionRow({
  label,
  value,
  total,
  color,
  detail,
}: {
  label: string;
  value: number;
  total: number;
  color: string;
  detail?: string;
}) {
  return (
    <div className="distribution-row">
      <div className="distribution-label">
        <span>{label}</span>
        <strong>{detail || pct(value, total)}</strong>
      </div>
      <div className="track">
        <span style={{ width: pct(value, total), background: color }} />
      </div>
      <span className="distribution-count">{value} 条</span>
    </div>
  );
}

function EmptyState() {
  return (
    <div className="empty-state">
      <FileSearch size={28} />
      <strong>当前筛选组合没有匹配评论</strong>
      <span>请放宽一个筛选条件后再查看。</span>
    </div>
  );
}

function OverviewPage({
  records,
  labels,
  onOpen,
}: {
  records: Review[];
  labels: Labels;
  onOpen: (review: Review) => void;
}) {
  const languages = countBy(records, (r) => r.language);
  const stars = countBy(records, (r) => String(r.stars)).sort((a, b) => Number(a[0]) - Number(b[0]));
  const sentiments = countBy(records, (r) => r.sentiment);
  const negative = sentiments.find(([key]) => key === "negative")?.[1] || 0;
  const highRating = records.filter((r) => r.stars >= 4).length;
  const avgConfidence = records.length
    ? records.reduce((sum, r) => sum + r.confidence, 0) / records.length
    : 0;
  const evidence = [...records]
    .sort((a, b) => b.intensity - a.intensity || a.stars - b.stars)
    .slice(0, 3);

  if (!records.length) return <EmptyState />;

  return (
    <section className="page-section">
      <div className="page-kicker">MARKET PULSE / 市场信号</div>
      <div className="headline-block">
        <div>
          <h1>均衡星级样本中，负向表达仍占 {pct(negative, records.length)}</h1>
          <p>当前筛选覆盖 {records.length} 条英语 / 西语评论；评分与文本情绪分开计算，避免只用星级替代消费者真实表达。</p>
        </div>
        <div className="headline-stamp">
          <span>可追溯评论</span>
          <strong>{records.length}</strong>
          <small>100% 保留原文</small>
        </div>
      </div>

      <div className="metric-strip">
        <div>
          <span>当前样本</span>
          <strong>{records.length}</strong>
          <small>条结构化评论</small>
        </div>
        <div>
          <span>高评分占比</span>
          <strong>{pct(highRating, records.length)}</strong>
          <small>4–5 星</small>
        </div>
        <div>
          <span>负向情绪占比</span>
          <strong>{pct(negative, records.length)}</strong>
          <small>基于文本判断</small>
        </div>
        <div>
          <span>平均置信度</span>
          <strong>{(avgConfidence * 100).toFixed(1)}%</strong>
          <small>模型字段均值</small>
        </div>
      </div>

      <div className="overview-grid">
        <article className="analysis-panel language-panel">
          <header>
            <span>语言覆盖</span>
            <strong>双语样本保持可比</strong>
          </header>
          <div className="language-split">
            {languages.map(([language, count], index) => (
              <div key={language} className={index === 0 ? "language-en" : "language-es"}>
                <span>{language === "en" ? "English" : "Español"}</span>
                <strong>{count}</strong>
                <small>{pct(count, records.length)} of current set</small>
              </div>
            ))}
          </div>
        </article>

        <article className="analysis-panel">
          <header>
            <span>评分分布</span>
            <strong>样本设计避免评分偏斜</strong>
          </header>
          <div className="star-histogram">
            {stars.map(([star, count]) => (
              <div key={star} className="star-column">
                <span className="star-bar" style={{ height: `${Math.max(10, (count / Math.max(...stars.map((s) => s[1]))) * 100)}%` }} />
                <strong>{count}</strong>
                <small>{star} 星</small>
              </div>
            ))}
          </div>
        </article>

        <article className="analysis-panel sentiment-panel">
          <header>
            <span>情绪分布</span>
            <strong>混合情绪不可忽略</strong>
          </header>
          <div className="distribution-list">
            {sentiments.map(([sentiment, count]) => (
              <DistributionRow
                key={sentiment}
                label={labelOf(labels.sentiments, sentiment)}
                value={count}
                total={records.length}
                color={sentimentColors[sentiment] || "#7b8790"}
              />
            ))}
          </div>
        </article>

        <article className="analysis-panel evidence-panel">
          <header>
            <span>高强度信号</span>
            <strong>从数字直达评论原文</strong>
          </header>
          <div className="evidence-stack">
            {evidence.map((review) => (
              <EvidenceButton key={review.id} review={review} onOpen={onOpen} compact />
            ))}
          </div>
        </article>
      </div>
    </section>
  );
}

function PainPage({
  records,
  labels,
  onOpen,
}: {
  records: Review[];
  labels: Labels;
  onOpen: (review: Review) => void;
}) {
  const issueMentions = records.flatMap((r) => r.issues.map((item) => ({ ...item, review: r })));
  const issues = countBy(issueMentions, (item) => item.code).slice(0, 8);
  const aspectMentions = records.flatMap((r) => r.aspects.map((item) => ({ ...item, review: r })));
  const aspectCodes = countBy(aspectMentions, (item) => item.code).slice(0, 8);
  const typical = records
    .filter((r) => r.sentiment === "negative" || r.aspects.some((a) => a.polarity === "negative"))
    .sort((a, b) => b.issues.length - a.issues.length || b.intensity - a.intensity)
    .slice(0, 4);
  const leader = issues[0];

  if (!records.length) return <EmptyState />;

  return (
    <section className="page-section">
      <div className="page-kicker">FRICTION MAP / 产品摩擦点</div>
      <div className="headline-block pain-headline">
        <div>
          <h1>{leader ? `${labelOf(labels.issues, leader[0])} 是当前第一问题信号` : "当前筛选下未识别明确问题"}</h1>
          <p>问题类型用于定位失败路径，产品属性用于解释问题落点；两者并列查看，避免把“哪里不好”和“为什么不好”混为一谈。</p>
        </div>
        <div className="headline-stamp signal">
          <span>问题提及</span>
          <strong>{issueMentions.length}</strong>
          <small>可回溯证据片段</small>
        </div>
      </div>

      <div className="two-column">
        <article className="analysis-panel ranked-panel">
          <header>
            <span>负向问题排行</span>
            <strong>优先处理高频失败路径</strong>
          </header>
          <ol className="rank-list">
            {issues.map(([code, count], index) => (
              <li key={code}>
                <span className="rank-number">{String(index + 1).padStart(2, "0")}</span>
                <div>
                  <strong>{labelOf(labels.issues, code)}</strong>
                  <div className="rank-track">
                    <span style={{ width: pct(count, issues[0]?.[1] || 1) }} />
                  </div>
                </div>
                <span>{count}</span>
              </li>
            ))}
          </ol>
        </article>

        <article className="analysis-panel aspect-panel">
          <header>
            <span>高频产品属性</span>
            <strong>正负口碑在同一属性上分化</strong>
          </header>
          <div className="aspect-balance-list">
            {aspectCodes.map(([code]) => {
              const mentions = aspectMentions.filter((item) => item.code === code);
              const positive = mentions.filter((item) => item.polarity === "positive").length;
              const negative = mentions.filter((item) => item.polarity === "negative").length;
              const base = positive + negative || 1;
              return (
                <div className="aspect-balance" key={code}>
                  <div>
                    <strong>{labelOf(labels.aspects, code)}</strong>
                    <span>{mentions.length} 次提及</span>
                  </div>
                  <div className="diverging-bar">
                    <span className="negative-side" style={{ width: `${(negative / base) * 100}%` }} />
                    <span className="positive-side" style={{ width: `${(positive / base) * 100}%` }} />
                  </div>
                  <small>
                    <span>负 {pct(negative, base, 0)}</span>
                    <span>正 {pct(positive, base, 0)}</span>
                  </small>
                </div>
              );
            })}
          </div>
        </article>
      </div>

      <article className="quote-ledger">
        <header>
          <div>
            <span>典型负向评论</span>
            <strong>消费者原话是问题定义的最后一跳</strong>
          </div>
          <small>{typical.length} 条高信息密度样本</small>
        </header>
        <div className="quote-grid">
          {typical.map((review) => (
            <EvidenceButton key={review.id} review={review} onOpen={onOpen} />
          ))}
        </div>
      </article>
    </section>
  );
}

function MotivationPage({
  records,
  labels,
  insights,
  onOpen,
}: {
  records: Review[];
  labels: Labels;
  insights: Insight[];
  onOpen: (review: Review) => void;
}) {
  const motivations = countBy(records.flatMap((r) => r.motivations), (item) => item.code).slice(0, 7);
  const scenarios = countBy(records.flatMap((r) => r.scenarios), (item) => item.code).slice(0, 7);
  const highReviews = records.filter((r) => r.stars >= 4);
  const highAspects = countBy(
    highReviews.flatMap((r) => r.aspects.filter((a) => a.polarity === "positive")),
    (item) => item.code,
  ).slice(0, 6);
  const marketing = selectInsights(insights, records)
    .filter(({ insight }) => insight.marketing_recommendation)
    .slice(0, 4);
  const evidence = highReviews
    .filter((r) => r.motivations.length || r.scenarios.length)
    .sort((a, b) => b.motivations.length + b.scenarios.length - (a.motivations.length + a.scenarios.length))
    .slice(0, 3);
  const leader = highAspects[0];

  if (!records.length) return <EmptyState />;

  return (
    <section className="page-section">
      <div className="page-kicker">DEMAND SIGNAL / 需求信号</div>
      <div className="headline-block motivation-headline">
        <div>
          <h1>{leader ? `高评分口碑最常落在“${labelOf(labels.aspects, leader[0])}”` : "当前筛选下高评分卖点信号有限"}</h1>
          <p>购买原因解释“为什么下单”，使用场景说明“在何时何地使用”，高评分属性才是可验证的内容卖点。</p>
        </div>
        <div className="headline-stamp green">
          <span>高评分评论</span>
          <strong>{highReviews.length}</strong>
          <small>4–5 星样本</small>
        </div>
      </div>

      <div className="motivation-grid">
        <article className="analysis-panel">
          <header>
            <span>高频购买原因</span>
            <strong>消费者为何开始尝试</strong>
          </header>
          <div className="signal-list">
            {motivations.length ? (
              motivations.map(([code, count], index) => (
                <div key={code}>
                  <span className="signal-index">{String(index + 1).padStart(2, "0")}</span>
                  <strong>{labelOf(labels.motivations, code)}</strong>
                  <span className="signal-value">{count}</span>
                </div>
              ))
            ) : (
              <p className="panel-note">当前筛选下没有明确购买动机标签。</p>
            )}
          </div>
        </article>

        <article className="analysis-panel">
          <header>
            <span>使用场景</span>
            <strong>内容创意从具体语境出发</strong>
          </header>
          <div className="scenario-map">
            {scenarios.length ? (
              scenarios.map(([code, count]) => (
                <div key={code}>
                  <span>{labelOf(labels.scenarios, code)}</span>
                  <strong>{count}</strong>
                  <small>{pct(count, records.length)}</small>
                </div>
              ))
            ) : (
              <p className="panel-note">当前筛选下没有明确使用场景标签。</p>
            )}
          </div>
        </article>

        <article className="analysis-panel selling-panel">
          <header>
            <span>高评分卖点</span>
            <strong>优先放大已有正向证据</strong>
          </header>
          <div className="selling-list">
            {highAspects.map(([code, count]) => (
              <DistributionRow
                key={code}
                label={labelOf(labels.aspects, code)}
                value={count}
                total={highAspects[0]?.[1] || 1}
                color="#187665"
                detail={`${count} 条`}
              />
            ))}
          </div>
        </article>
      </div>

      <div className="translation-board">
        <div className="translation-title">
          <span>可转化营销表达</span>
          <h2>从统计信号，到可验证的内容命题</h2><p>建议来自完整分析，仅展示当前筛选有证据支持的条目；筛选不会重新生成结论。</p>
        </div>
        <div className="translation-list">
          {!marketing.length && <p role="status">当前筛选没有可追溯的营销建议。</p>}
          {marketing.map(({ insight, matchedIds }, index) => (
            <div key={insight.insight_id}>
              <span>{String(index + 1).padStart(2, "0")}</span>
              <div>
                <strong>{insight.title}</strong>
                <p>{insight.marketing_recommendation}</p>
                <small>{matchedIds.length} 条当前证据 · 全量支持 {insight.data_evidence.support_reviews} 条</small>
              </div>
            </div>
          ))}
        </div>
      </div>

      {evidence.length > 0 && (
        <div className="evidence-ribbon">
          <span>购买语境原声</span>
          {evidence.map((review) => (
            <EvidenceButton key={review.id} review={review} onOpen={onOpen} compact />
          ))}
        </div>
      )}
    </section>
  );
}

function LanguagePage({
  records,
  labels,
  onOpen,
}: {
  records: Review[];
  labels: Labels;
  onOpen: (review: Review) => void;
}) {
  const groups = {
    en: records.filter((r) => r.language === "en"),
    es: records.filter((r) => r.language === "es"),
  };
  const analysis = (languageRecords: Review[]) => {
    const aspects = countBy(languageRecords.flatMap((r) => r.aspects), (item) => item.code).slice(0, 5);
    const speech = countBy(languageRecords.flatMap((r) => r.speechActs), (item) => item.code).slice(0, 5);
    const avgIntensity = languageRecords.length
      ? languageRecords.reduce((sum, r) => sum + r.intensity, 0) / languageRecords.length
      : 0;
    const complaints = languageRecords.filter((r) => r.speechActs.some((s) => s.code === "complaint")).length;
    const suggestions = languageRecords.filter((r) => r.speechActs.some((s) => s.code === "suggestion")).length;
    return { aspects, speech, avgIntensity, complaints, suggestions };
  };
  const en = analysis(groups.en);
  const es = analysis(groups.es);
  const examples = ["en", "es"]
    .map((language) =>
      records
        .filter((r) => r.language === language && r.speechActs.length)
        .sort((a, b) => b.intensity - a.intensity)[0],
    )
    .filter(Boolean) as Review[];

  if (!records.length) return <EmptyState />;

  return (
    <section className="page-section">
      <div className="page-kicker">CROSS-LANGUAGE LENS / 跨语镜像</div>
      <div className="headline-block language-headline">
        <div>
          <h1>英语与西语的关注对象接近，表达策略并不完全相同</h1>
          <p>对比属性焦点、情绪强度与言语行为，可以把“翻译”升级为面向市场语境的本地化表达。</p>
        </div>
        <div className="language-key">
          <span><i className="key-en" /> EN {groups.en.length}</span>
          <span><i className="key-es" /> ES {groups.es.length}</span>
        </div>
      </div>

      <div className="language-comparison">
        {(["en", "es"] as const).map((language) => {
          const stats = language === "en" ? en : es;
          const languageRecords = groups[language];
          return (
            <article key={language} className={`language-column ${language}`}>
              <header>
                <div>
                  <span>{language === "en" ? "ENGLISH MARKET" : "MERCADO ESPAÑOL"}</span>
                  <strong>{language === "en" ? "英语评论" : "西语评论"}</strong>
                </div>
                <span className="language-badge">{language.toUpperCase()}</span>
              </header>
              <div className="intensity-stat">
                <span>平均情绪强度</span>
                <strong>{stats.avgIntensity.toFixed(2)}<small>/ 3</small></strong>
                <div className="intensity-dots">
                  {[1, 2, 3].map((value) => (
                    <i key={value} className={stats.avgIntensity >= value - 0.5 ? "active" : ""} />
                  ))}
                </div>
              </div>
              <div className="focus-list">
                <span>TOP 关注属性</span>
                {stats.aspects.map(([code, count], index) => (
                  <div key={code}>
                    <b>{index + 1}</b>
                    <span>{labelOf(labels.aspects, code)}</span>
                    <strong>{pct(count, Math.max(1, languageRecords.length))}</strong>
                  </div>
                ))}
              </div>
              <div className="speech-summary">
                <span>表达方式</span>
                <div>
                  <strong>{pct(stats.complaints, languageRecords.length)}</strong>
                  <small>含投诉行为</small>
                </div>
                <div>
                  <strong>{pct(stats.suggestions, languageRecords.length)}</strong>
                  <small>含建议行为</small>
                </div>
              </div>
              <div className="speech-tags">
                {stats.speech.slice(0, 4).map(([code, count]) => (
                  <span key={code}>{labelOf(labels.speechActs, code)} · {count}</span>
                ))}
              </div>
            </article>
          );
        })}
      </div>

      <article className="localization-panel">
        <div className="localization-rule">
          <Languages size={22} />
          <div>
            <span>本地化启示</span>
            <strong>保留同一产品事实，按市场常见表达方式重写证据顺序</strong>
            <p>英语内容可先给结果和使用门槛；西语内容可增加体验过程与使用语境。该建议来自表达分布差异，不等同于对所有消费者的刻板假设。</p>
          </div>
        </div>
        <div className="bilingual-evidence">
          {examples.map((review) => (
            <EvidenceButton key={review.id} review={review} onOpen={onOpen} compact />
          ))}
        </div>
      </article>
    </section>
  );
}

function InsightsPage({
  records,
  insights,
  onOpen,
}: {
  records: Review[];
  insights: Insight[];
  onOpen: (review: Review) => void;
}) {
  const recordMap = useMemo(() => new Map(records.map((record) => [record.id, record])), [records]);
  const visibleInsights = selectInsights(insights, records);
  const [selectedId, setSelectedId] = useState<string>("");
  const selected = visibleInsights.find((item) => item.insight.insight_id === selectedId) || visibleInsights[0];

  if (!records.length || !selected) return <EmptyState />;
  const representative = selected.insight.representative_quotes
    .map((quote) => recordMap.get(quote.review_id))
    .filter(Boolean) as Review[];

  return (
    <section className="page-section insights-page">
      <div className="page-kicker">EVIDENCE BRIEF / 洞察简报</div>
      <div className="headline-block insight-headline">
        <div>
          <h1>完整分析 {insights.length} 条洞察 · 当前可追溯 {visibleInsights.length} 条</h1>
          <p>仅展示当前数据和筛选范围内能打开评论证据的洞察。公开样本不覆盖全部洞察；全量支持数来自完整分析，筛选不会重新生成结论。</p>
        </div>
        <div className="trace-status">
          <Sparkles size={18} />
          <div><strong>当前证据可打开</strong><span>{visibleInsights.length} / {insights.length} 条洞察有当前证据</span></div>
        </div>
      </div>

      <div className="insight-workbench">
        <aside className="insight-index">
          <div className="insight-index-head">
            <span>洞察目录</span>
            <strong>{visibleInsights.length} / {insights.length}</strong>
          </div>
          {visibleInsights.map(({ insight, matchedIds }, index) => (
            <button
              key={insight.insight_id}
              className={selected.insight.insight_id === insight.insight_id ? "active" : ""}
              onClick={() => setSelectedId(insight.insight_id)}
            >
              <span>{String(index + 1).padStart(2, "0")}</span>
              <div>
                <strong>{insight.title}</strong>
                <small>{matchedIds.length} 条当前证据</small>
              </div>
              <ChevronRight size={15} />
            </button>
          ))}
        </aside>

        <article className="insight-detail">
          <div className="insight-category">{selected.insight.category_name}</div>
          <h2>{selected.insight.title}</h2>
          <p className="cause-note">{selected.insight.possible_cause}</p>

          <div className="evidence-spine">
            <div className="spine-step">
              <span className="step-node">01</span>
              <div>
                <small>统计证据</small>
                <strong>{selected.matchedIds.length} 条当前筛选评论</strong>
                <p>全量支持 {selected.insight.data_evidence.support_reviews} 条；平均模型置信度 {(selected.insight.data_evidence.mean_model_confidence * 100).toFixed(1)}%。</p>
              </div>
            </div>
            <div className="spine-step">
              <span className="step-node">02</span>
              <div>
                <small>消费者原话</small>
                <strong>代表性证据片段</strong>
                <div className="spine-quotes">
                  {representative.length ? (
                    representative.map((review) => (
                      <EvidenceButton key={review.id} review={review} onOpen={onOpen} compact />
                    ))
                  ) : (
                    <EvidenceButton review={recordMap.get(selected.matchedIds[0])!} onOpen={onOpen} compact />
                  )}
                </div>
              </div>
            </div>
            <div className="spine-step action-step">
              <span className="step-node">03</span>
              <div>
                <small>业务动作</small>
                <strong>从证据出发，不做超范围承诺</strong>
                <div className="action-grid">
                  <div>
                    <span>产品建议</span>
                    <p>{selected.insight.product_recommendation}</p>
                  </div>
                  <div>
                    <span>内容营销</span>
                    <p>{selected.insight.marketing_recommendation}</p>
                  </div>
                  <div>
                    <span>选题方向</span>
                    <p>{selected.insight.content_topic}</p>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </article>
      </div>
    </section>
  );
}

function ReviewDrawer({
  records,
  selected,
  labels,
  onSelect,
  onClose,
}: {
  records: Review[];
  selected: Review | null;
  labels: Labels;
  onSelect: (review: Review) => void;
  onClose: () => void;
}) {
  const [query, setQuery] = useState("");
  const list = useMemo(() => {
    const normalized = query.trim().toLowerCase();
    return records
      .filter((review) =>
        !normalized
          ? true
          : `${review.id} ${review.title} ${review.body}`.toLowerCase().includes(normalized),
      )
      .slice(0, 80);
  }, [query, records]);

  const active = selected || list[0] || null;
  return (
    <div className="drawer-layer" role="dialog" aria-modal="true" aria-label="评论证据库">
      <button className="drawer-backdrop" onClick={onClose} aria-label="关闭评论证据库" />
      <aside className="review-drawer">
        <header className="drawer-header">
          <div>
            <span>EVIDENCE LIBRARY</span>
            <strong>评论证据库</strong>
          </div>
          <button className="icon-button" onClick={onClose} aria-label="关闭">
            <X size={20} />
          </button>
        </header>
        <div className="drawer-search">
          <Search size={16} />
          <input
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="搜索评论 ID 或原文"
            aria-label="搜索评论"
          />
          <span>{records.length} 条</span>
        </div>
        <div className="drawer-body">
          <nav className="review-list" aria-label="评论列表">
            {list.map((review) => (
              <button
                key={review.id}
                className={active?.id === review.id ? "active" : ""}
                onClick={() => onSelect(review)}
              >
                <span>{review.language.toUpperCase()} · {review.id}</span>
                <strong>{review.title || review.body.slice(0, 46)}</strong>
                <small>{review.body.slice(0, 100)}</small>
              </button>
            ))}
          </nav>
          {active ? (
            <article className="review-detail">
              <div className="review-meta">
                <span>{active.language.toUpperCase()}</span>
                <StarLine stars={active.stars} />
                <span>{labelOf(labels.sentiments, active.sentiment)}</span>
                <span>置信度 {(active.confidence * 100).toFixed(0)}%</span>
              </div>
              <h2>{active.title || "无标题评论"}</h2>
              <blockquote>{active.body}</blockquote>
              <div className="annotation-section">
                <span className="annotation-label">属性与观点证据</span>
                {active.aspects.length ? active.aspects.map((aspect, index) => (
                  <div className="annotation-row" key={`${aspect.code}-${index}`}>
                    <div>
                      <strong>{labelOf(labels.aspects, aspect.code)}</strong>
                      <span className={`polarity ${aspect.polarity}`}>{polarityLabel[aspect.polarity]}</span>
                    </div>
                    <p>{aspect.opinion}</p>
                    {aspect.evidence.map((evidence) => <q key={evidence}>{evidence}</q>)}
                  </div>
                )) : <p className="panel-note">未识别明确产品属性。</p>}
              </div>
              <div className="annotation-columns">
                <div>
                  <span className="annotation-label">问题类型</span>
                  {active.issues.length ? active.issues.map((item, index) => (
                    <div className="code-chip" key={`${item.code}-${index}`}>
                      <strong>{labelOf(labels.issues, item.code)}</strong>
                      <q>{item.evidence}</q>
                    </div>
                  )) : <small>无明确问题标签</small>}
                </div>
                <div>
                  <span className="annotation-label">使用语境</span>
                  {[...active.motivations, ...active.scenarios].length ? (
                    <>
                      {active.motivations.map((item, index) => (
                        <div className="code-chip" key={`m-${item.code}-${index}`}>
                          <strong>{labelOf(labels.motivations, item.code)}</strong><q>{item.evidence}</q>
                        </div>
                      ))}
                      {active.scenarios.map((item, index) => (
                        <div className="code-chip" key={`s-${item.code}-${index}`}>
                          <strong>{labelOf(labels.scenarios, item.code)}</strong><q>{item.evidence}</q>
                        </div>
                      ))}
                    </>
                  ) : <small>无明确动机或场景标签</small>}
                </div>
              </div>
              <footer>
                <span>原始评论 ID</span>
                <strong>{active.id}</strong>
                <small>每个判断均保留直接证据片段</small>
              </footer>
            </article>
          ) : (
            <EmptyState />
          )}
        </div>
      </aside>
    </div>
  );
}

export default function Home() {
  const [data, setData] = useState<DashboardData | null>(null);
  const [error, setError] = useState("");
  const [page, setPage] = useState<PageKey>("overview");
  const [filters, setFilters] = useState<Filters>(INITIAL_FILTERS);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [selectedReview, setSelectedReview] = useState<Review | null>(null);
  const [mobileNavOpen, setMobileNavOpen] = useState(false);

  useEffect(() => {
    const controller = new AbortController();
    const loadDashboardData = async () => {
      for (const candidate of [
        "/data/dashboard-data.json",
        "/data/dashboard-data.demo.json",
      ]) {
        try {
          const response = await fetch(candidate, { signal: controller.signal });
          if (!response.ok) continue;
          const value: unknown = await response.json();
          if (!value || typeof value !== "object") continue;
          const payload = value as Partial<DashboardData>;
          if (!Array.isArray(payload.records) || !Array.isArray(payload.insights) || !payload.meta || !payload.labels) continue;
          return payload as DashboardData;
        } catch (reason) {
          if (controller.signal.aborted) throw reason;
        }
      }
      throw new Error("正式数据包与演示数据包均不可用");
    };
    loadDashboardData()
      .then((payload) => { if (!controller.signal.aborted) setData(payload); })
      .catch((reason) => { if (!controller.signal.aborted) setError(String(reason)); });
    return () => controller.abort();
  }, []);

  const filtered = useMemo(() => {
    if (!data) return [];
    return data.records.filter((review) => {
      if (filters.language !== "all" && review.language !== filters.language) return false;
      if (filters.stars !== "all" && review.stars !== Number(filters.stars)) return false;
      if (filters.sentiment !== "all" && review.sentiment !== filters.sentiment) return false;
      if (filters.aspect !== "all" && !review.aspects.some((item) => item.code === filters.aspect)) return false;
      if (filters.issue !== "all" && !review.issues.some((item) => item.code === filters.issue)) return false;
      if (filters.scenario !== "all" && !review.scenarios.some((item) => item.code === filters.scenario)) return false;
      return true;
    });
  }, [data, filters]);

  const activeFilters = Object.values(filters).filter((value) => value !== "all").length;
  const openReview = (review: Review) => {
    setSelectedReview(review);
    setDrawerOpen(true);
  };

  if (error) {
    return <main className="loading-screen"><strong>数据加载失败</strong><span>{error}</span></main>;
  }
  if (!data) {
    return (
      <main className="loading-screen">
        <div className="loading-mark"><span /><span /><span /></div>
        <strong>正在装载评论证据</strong>
        <span>构建双语市场视图…</span>
      </main>
    );
  }

  const renderPage = () => {
    if (page === "overview") return <OverviewPage records={filtered} labels={data.labels} onOpen={openReview} />;
    if (page === "pain") return <PainPage records={filtered} labels={data.labels} onOpen={openReview} />;
    if (page === "motivation") return <MotivationPage records={filtered} labels={data.labels} insights={data.insights} onOpen={openReview} />;
    if (page === "language") return <LanguagePage records={filtered} labels={data.labels} onOpen={openReview} />;
    return <InsightsPage records={filtered} insights={data.insights} onOpen={openReview} />;
  };

  return (
    <main className="dashboard-shell">
      <aside className={`sidebar ${mobileNavOpen ? "mobile-open" : ""}`}>
        <div className="brand">
          <div className="brand-mark">CV</div>
          <div>
            <strong>Crossborder Voice</strong>
            <span>评论洞察 AGENT</span>
          </div>
          <button className="sidebar-close" onClick={() => setMobileNavOpen(false)} aria-label="关闭导航">
            <X size={18} />
          </button>
        </div>
        <nav>
          {PAGE_ITEMS.map((item) => {
            const Icon = item.icon;
            return (
              <button
                key={item.key}
                className={page === item.key ? "active" : ""}
                onClick={() => {
                  setPage(item.key);
                  setMobileNavOpen(false);
                }}
              >
                <span className="nav-number">{item.number}</span>
                <Icon size={18} />
                <span className="nav-copy"><strong>{item.label}</strong><small>{item.subtitle}</small></span>
                <ChevronRight size={15} className="nav-arrow" />
              </button>
            );
          })}
        </nav>
        <div className="dataset-seal">
          <span className="seal-dot" />
          <div>
            <strong>{data.meta.mode === "demo" ? "PUBLIC DEMO" : "DATASET LOCKED"}</strong>
            <small>
              {data.meta.mode === "demo"
                ? `${data.records.length} sample records · full analysis ${data.meta.fullDatasetRecords}`
                : `v11 · ${data.records.length} records`}
            </small>
          </div>
        </div>
        <div className="sidebar-foot">
          <span>Prompt {data.meta.promptVersion.replace("v9_", "v9 · ")}</span>
          <span>Schema {data.meta.schemaVersion}</span>
        </div>
      </aside>

      <div className="workspace"><p className="dataset-notice">模型标签仍需复核；已完成公开 10 条样本的单一 AI 评审。<a href="https://github.com/zugzwang-zg/crossborder-voice-agent/blob/main/reports/ai_review_2026-09-30.md" target="_blank" rel="noreferrer">查看发现与局限</a></p>
        <header className="topbar">
          <button className="mobile-menu" onClick={() => setMobileNavOpen(true)} aria-label="打开导航">
            <Menu size={20} />
          </button>
          <div className="filter-title">
            <Filter size={16} />
            <span>全局筛选</span>
            {activeFilters > 0 && <b>{activeFilters}</b>}
          </div>
          <div className="filters">
            <label>
              <span>语言</span>
              <select value={filters.language} onChange={(e) => setFilters({ ...filters, language: e.target.value })}>
                <option value="all">全部语言</option>
                <option value="en">English</option>
                <option value="es">Español</option>
              </select>
            </label>
            <label>
              <span>星级</span>
              <select value={filters.stars} onChange={(e) => setFilters({ ...filters, stars: e.target.value })}>
                <option value="all">全部星级</option>
                {[1, 2, 3, 4, 5].map((star) => <option key={star} value={star}>{star} 星</option>)}
              </select>
            </label>
            <label>
              <span>情绪</span>
              <select value={filters.sentiment} onChange={(e) => setFilters({ ...filters, sentiment: e.target.value })}>
                <option value="all">全部情绪</option>
                {selectOptions(data.labels.sentiments).map(([code, name]) => <option key={code} value={code}>{name}</option>)}
              </select>
            </label>
            <label>
              <span>产品属性</span>
              <select value={filters.aspect} onChange={(e) => setFilters({ ...filters, aspect: e.target.value })}>
                <option value="all">全部属性</option>
                {selectOptions(data.labels.aspects).map(([code, name]) => <option key={code} value={code}>{name}</option>)}
              </select>
            </label>
            <label>
              <span>痛点</span>
              <select value={filters.issue} onChange={(e) => setFilters({ ...filters, issue: e.target.value })}>
                <option value="all">全部痛点</option>
                {selectOptions(data.labels.issues).map(([code, name]) => <option key={code} value={code}>{name}</option>)}
              </select>
            </label>
            <label>
              <span>使用场景</span>
              <select value={filters.scenario} onChange={(e) => setFilters({ ...filters, scenario: e.target.value })}>
                <option value="all">全部场景</option>
                {selectOptions(data.labels.scenarios).map(([code, name]) => <option key={code} value={code}>{name}</option>)}
              </select>
            </label>
          </div>
          <div className="topbar-actions">
            {activeFilters > 0 && (
              <button className="reset-button" onClick={() => setFilters(INITIAL_FILTERS)}>
                <RotateCcw size={15} /> 清空
              </button>
            )}
            <button className="library-button" onClick={() => { setSelectedReview(null); setDrawerOpen(true); }}>
              <BookOpenText size={17} />
              <span>评论证据库</span>
              <b>{filtered.length}</b>
            </button>
          </div>
        </header>

        <div className="mobile-filter-summary">
          <span>当前样本 <strong>{filtered.length}</strong> 条</span>
          <button onClick={() => document.querySelector(".filters")?.scrollIntoView({ behavior: "smooth" })}>
            <Filter size={15} /> 筛选
          </button>
        </div>

        <div className="page-canvas">
          {renderPage()}
          <footer className="data-footer">
            <span><MessageSquareQuote size={14} /> {filtered.length} 条当前样本 · 原文可追溯</span>
            <span>数据源 {data.meta.source} · 统计为描述性结论，不作因果推断</span>
          </footer>
        </div>
      </div>

      {drawerOpen && (
        <ReviewDrawer
          records={filtered}
          selected={selectedReview}
          labels={data.labels}
          onSelect={setSelectedReview}
          onClose={() => setDrawerOpen(false)}
        />
      )}
    </main>
  );
}
