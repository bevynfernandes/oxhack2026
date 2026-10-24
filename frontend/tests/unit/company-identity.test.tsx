import { describe, expect, it } from "vitest";
import {
  companyDomain,
  matchesCompanySearch,
} from "../../src/pages/companies/identity";
const company = {
  display_name: "Example Labs",
  segment: "developer-tools",
  website_url: "https://www.example.com/",
};
describe("saved company identity search", () => {
  it("matches names, sectors and normalized exact domains", () => {
    for (const query of [
      " Labs ",
      "developer",
      "example.com",
      "WWW.EXAMPLE.COM",
      "https://example.com/about",
    ])
      expect(matchesCompanySearch(company, query)).toBe(true);
  });
  it("does not substitute similar domains or accept credential-bearing URLs", () => {
    for (const query of [
      "example.com.attacker.test",
      "other.example.com",
      "https://user@example.com",
      "https://",
    ])
      expect(matchesCompanySearch(company, query)).toBe(false);
  });
  it("keeps unavailable and invalid websites distinct from matching identity", () => {
    expect(companyDomain(null)).toBeNull();
    expect(companyDomain("javascript:alert(1)")).toBeNull();
    expect(
      matchesCompanySearch({ ...company, website_url: null }, "example.com"),
    ).toBe(false);
    expect(
      matchesCompanySearch({ ...company, website_url: null }, "Example Labs"),
    ).toBe(true);
  });
});
