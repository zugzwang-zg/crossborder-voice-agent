export type CodedEvidence = { code: string; evidence: string };
export type Aspect = {
  code: string;
  polarity: "positive" | "negative" | "mixed" | "neutral";
  evidence: string[];
  opinion: string;
};
export type Review = {
  id: string;
  language: "en" | "es";
  stars: number;
  title: string;
  body: string;
  sentiment: string;
  intensity: number;
  confidence: number;
  aspects: Aspect[];
  issues: CodedEvidence[];
  motivations: CodedEvidence[];
  scenarios: CodedEvidence[];
  speechActs: CodedEvidence[];
  actions: { audience: string; action: string; evidence: string }[];
  expectationGap: { present: boolean; type: string; evidence: string[] };
};
export type Insight = {
  insight_id: string;
  category: string;
  category_name: string;
  title: string;
  affected_audience: {
    languages: Record<string, number>;
    star_distribution: Record<string, number>;
  };
  data_evidence: {
    support_reviews: number;
    mean_model_confidence: number;
    source_review_ids: string[];
  };
  representative_quotes: {
    review_id: string;
    language: string;
    stars: number;
    quote: string;
  }[];
  possible_cause: string;
  product_recommendation: string;
  marketing_recommendation: string;
  content_topic: string;
  sample_size_and_confidence: {
    support_reviews: number;
    evidence_quotes: number;
    grade: string;
  };
};
export type Labels = {
  aspects: Record<string, string>;
  issues: Record<string, string>;
  motivations: Record<string, string>;
  scenarios: Record<string, string>;
  speechActs: Record<string, string>;
  expectationGaps: Record<string, string>;
  sentiments: Record<string, string>;
};
export type DashboardData = {
  meta: {
    title: string;
    source: string;
    generatedFrom: number;
    traceability: { status: string; insights_checked: number; failures: number };
    promptVersion: string;
    schemaVersion: string;
    mode?: "demo";
    fullDatasetRecords?: number;
  };
  labels: Labels;
  records: Review[];
  insights: Insight[];
};
