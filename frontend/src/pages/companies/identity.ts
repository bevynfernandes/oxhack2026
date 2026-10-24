/** Display a saved website's host without treating arbitrary input as identity proof. */
export function companyDomain(website: string | null): string | null {
  if (!website) return null;
  try {
    const url = new URL(website);
    if (
      !["https:", "http:"].includes(url.protocol) ||
      url.username ||
      url.password
    )
      return null;
    return url.hostname.toLowerCase().replace(/^www\./, "");
  } catch {
    return null;
  }
}

/** Domain-shaped searches require the exact saved host; names remain searchable. */
export function matchesCompanySearch(
  company: {
    display_name: string;
    segment: string;
    website_url: string | null;
  },
  query: string,
): boolean {
  const value = query.trim().toLowerCase();
  if (!value) return true;
  if (company.display_name.toLowerCase() === value) return true;
  if (value.includes(".") || value.includes("://")) {
    const host = companyDomain(
      value.includes("://") ? value : `https://${value}`,
    );
    return host !== null && host === companyDomain(company.website_url);
  }
  return `${company.display_name} ${company.segment}`
    .toLowerCase()
    .includes(value);
}
