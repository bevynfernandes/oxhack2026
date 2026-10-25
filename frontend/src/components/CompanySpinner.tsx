import { useState } from "react";
import { companyDomain } from "../pages/companies/identity";
import { MotionSpinnerRing } from "../motion";
import Icon from "./WorkspaceIcon";
import "./company-spinner.css";

/** Keep a website's favicon still while its surrounding activity ring rotates. */
export default function CompanySpinner({
  website,
  size = "regular",
}: {
  website?: string | null;
  size?: "small" | "regular";
}) {
  const host = website
    ? companyDomain(website.includes("://") ? website : `https://${website}`)
    : null;
  const domain =
    host &&
    host.includes(".") &&
    !/^[\d.]+$/.test(host) &&
    !/\.(local|localhost|internal|test|example|invalid)$/.test(host)
      ? host
      : null;
  return (
    <span
      className={`company-spinner company-spinner--${size}`}
      aria-hidden="true"
    >
      <MotionSpinnerRing className="company-spinner__ring" />
      <span className="company-spinner__core">
        {domain ? (
          <Favicon key={domain} domain={domain} />
        ) : (
          <Icon name="activity" />
        )}
      </span>
    </span>
  );
}

function Favicon({ domain }: { domain: string }) {
  const [attempt, setAttempt] = useState(0);
  const sources = [
    `https://${domain}/favicon.ico`,
    `https://www.google.com/s2/favicons?domain=${encodeURIComponent(domain)}&sz=64`,
  ];
  return (
    <span
      className="company-spinner__favicon"
      data-monogram={domain[0].toUpperCase()}
    >
      {attempt < sources.length && (
        <img
          src={sources[attempt]}
          alt=""
          referrerPolicy="no-referrer"
          draggable={false}
          onError={() => setAttempt((current) => current + 1)}
        />
      )}
    </span>
  );
}
