# Explaining the Qdrant and Weaviate demonstration

## A short pitch

“We began with statistical baselines, including Ridge regression for SDK download
trends. Those local models still run. They answer narrow questions, such as demand
for a developer SDK, rather than predicting whether a whole company will succeed.
We added AI interpretation to bring public evidence together into a broader
company outlook. For this demonstration, the three outlook scores are AI-authored
estimates stored with the application, so the two company pages remain usable
without a live model provider. They are transparent, uncalibrated indices, not
probabilities of success.”

## Why the broader cards are different

- A next-month SDK download forecast is a different target from company revenue
  growth over 24 months. Downloads include automation and are not customers.
- Reliable survival and financial forecasts require dated company outcomes and
  comparable financial histories. That joined training cohort is not available.
- The financial proxy was trained on public issuers. Qdrant and Weaviate are
  private companies with missing revenue, operating cash flow and cash balances.
- Financing announcements, pricing pages, public releases and title sentiment
  provide context; they do not establish profitability, runway or solvency.
- Gemini is used elsewhere for evidence interpretation. Its live availability
  was unreliable during this implementation, including a temporary overload.
  These three cards therefore make no live provider request.

## What runs during the demonstration

1. The backend loads the exact, digest-verified public input bundle for Qdrant and
   Weaviate, with dates, source links and explicit missing values.
2. The existing portable SDK-demand model and title-sentiment classifier compute
   their experimental outputs from those inputs on profile reads.
3. The frontend presents the three AI-authored outlook indices associated only
   with that exact source snapshot. They do not carry over to unrelated companies,
   new research reports or future source publications.
4. Evidence drawers expose the source context and limitations. “About this
   estimate” describes how the broader scores were prepared.

Do not claim that Ridge was replaced by a validated LLM company-success model,
that Gemini generated the cards live, or that 84/100 means an 84% survival chance.
