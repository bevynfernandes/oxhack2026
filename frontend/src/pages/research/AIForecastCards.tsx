import type { DTO } from "../../api/client";
import { SourceLink } from "../../components/Common";
import { MotionDisclosure } from "../../motion";
import { FORECAST_SOURCE, PRELOADED_FORECASTS } from "./preloadedForecasts";

const names = {
  growth: "Growth outlook",
  survival: "Survival outlook",
  financial_health: "Financial health",
};

/** Present dated AI-authored estimates without a live provider dependency. */
export default function AIForecastCards({
  profile,
}: {
  profile: Pick<DTO<"CompanyDetail">, "company" | "publication">;
}) {
  const cards = PRELOADED_FORECASTS[profile.company.company_id];
  if (profile.publication.source.snapshot_id !== FORECAST_SOURCE || !cards)
    return null;
  return (
    <>
      {cards.map((card) => (
        <section
          className="dossier-stat ai-forecast-card"
          data-outcome={card.outcome}
          key={card.outcome}
        >
          <div>
            <div className="forecast-card-meta">
              <span>AI OUTLOOK</span>
              <span>{card.months}-MONTH HORIZON</span>
            </div>
            <h3>{names[card.outcome]}</h3>
            <div className="stat-value">
              {card.score}
              <span className="stat-unit">/ 100</span>
            </div>
            <p className="forecast-score-label">AI outlook estimate</p>
            <div
              className="forecast-score-track"
              role="meter"
              aria-label={`${names[card.outcome]} index`}
              aria-valuemin={0}
              aria-valuemax={100}
              aria-valuenow={card.score}
            >
              <span style={{ width: `${card.score}%` }} />
            </div>
            <p className="forecast-rationale">{card.rationale}</p>
            <div className="forecast-caveat">
              <span>Key uncertainty</span>
              <p>{card.caveat}</p>
            </div>
            <div className="forecast-card-footer">
              <SourceLink url={card.source}>Supporting source</SourceLink>
              <span>25 OCT 2026</span>
            </div>
            <MotionDisclosure summary="About this estimate">
              <p>
                Prepared by an AI assistant from the saved 25 October 2026
                public inputs. These estimates are stored with the app and do
                not make live Gemini requests. Scores are subjective outlook
                indices, not calibrated probabilities or validated statistical
                forecasts.
              </p>
            </MotionDisclosure>
          </div>
        </section>
      ))}
    </>
  );
}
