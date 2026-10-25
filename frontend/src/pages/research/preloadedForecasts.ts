/** AI-authored, uncalibrated outlook estimates for the exact dated input bundle. */
export const FORECAST_SOURCE = "company-preloaded-20261025-v1";
export type PreparedForecast = {
  outcome: "growth" | "survival" | "financial_health";
  score: number;
  months: number;
  rationale: string;
  caveat: string;
  source: string;
};
export const PRELOADED_FORECASTS: Readonly<
  Partial<Record<string, readonly PreparedForecast[]>>
> = {
  qdrant: [
    {
      outcome: "growth",
      score: 76,
      months: 24,
      rationale:
        "SDK downloads increased from 3.14 million to 3.23 million across the saved adjacent 30-day windows. Its cloud offering and announced Series B support a constructive growth outlook.",
      caveat:
        "Downloads include automated use and do not establish revenue growth or paying customers.",
      source: "https://qdrant.tech/blog/series-b-announcement/",
    },
    {
      outcome: "survival",
      score: 84,
      months: 24,
      rationale:
        "The disclosed USD 50 million Series B, established open-source product and continuing SDK releases support a relatively resilient operating outlook.",
      caveat:
        "Cash burn, liabilities and runway are undisclosed; financing does not guarantee continued operation.",
      source: "https://qdrant.tech/blog/series-b-announcement/",
    },
    {
      outcome: "financial_health",
      score: 58,
      months: 12,
      rationale:
        "Announced financing and paid cloud offerings indicate access to capital and a commercial model. The estimate stays cautious because operating performance is not established.",
      caveat:
        "Revenue, operating cash flow and cash balances are unknown. This score does not establish profitability or solvency.",
      source: "https://qdrant.tech/pricing/",
    },
  ],
  weaviate: [
    {
      outcome: "growth",
      score: 72,
      months: 24,
      rationale:
        "The managed-cloud offering and disclosed Ricoh investment support expansion potential. Saved SDK downloads fell from 1.49 million to 1.31 million, tempering the growth outlook.",
      caveat:
        "A single SDK window is noisy and does not establish customer or revenue trends.",
      source: "https://www.ricoh.com/release/2026/0616_1",
    },
    {
      outcome: "survival",
      score: 86,
      months: 24,
      rationale:
        "The announced Series B and subsequent Ricoh investment provide financing context alongside an established product and commercial cloud offering.",
      caveat:
        "The Ricoh investment amount and current runway are undisclosed. The estimate cannot establish a probability of survival.",
      source: "https://www.ricoh.com/release/2026/0616_1",
    },
    {
      outcome: "financial_health",
      score: 60,
      months: 12,
      rationale:
        "Paid cloud offerings and disclosed external investment support a moderately constructive capital-access assessment, with substantial uncertainty about financial performance.",
      caveat:
        "Private revenue, operating cash flow and cash balances are unknown. Funding and product prices do not establish profitability.",
      source: "https://weaviate.io/pricing",
    },
  ],
};
