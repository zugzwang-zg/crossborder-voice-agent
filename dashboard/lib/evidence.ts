import type { Insight, Review } from "./types";

/** Select and rank existing conclusions by resolvable evidence in this scope. */
export function selectInsights(insights: Insight[], records: Pick<Review, "id">[]) {
  const ids = new Set(records.map((record) => record.id));
  return insights.map((insight) => ({
    insight,
    matchedIds: [...new Set(insight.data_evidence.source_review_ids)].filter((id) => ids.has(id)),
  })).filter(({ matchedIds }) => matchedIds.length > 0)
    .sort((a, b) => b.matchedIds.length - a.matchedIds.length);
}
