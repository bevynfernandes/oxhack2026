import { fireEvent, render, screen } from "@testing-library/react";
import { expect, it } from "vitest";
import CompanySpinner from "../../src/components/CompanySpinner";
import { MotionProvider } from "../../src/motion";

it.each(["elevenlabs.io", "github.com"])(
  "uses %s's own favicon inside the ring",
  (domain) => {
    const { container } = render(<CompanySpinner website={domain} />);
    const image = container.querySelector("img")!;
    expect(image).toHaveAttribute("src", `https://${domain}/favicon.ico`);
    expect(image).toHaveAttribute("referrerpolicy", "no-referrer");
    expect(image).toHaveAttribute("alt", "");
    expect(
      container.querySelector(".company-spinner__ring"),
    ).toBeInTheDocument();
  },
);

it("uses only the hostname and never forwards a website's query or path", () => {
  const { container } = render(
    <CompanySpinner website="https://www.github.com/features?token=private#details" />,
  );
  expect(container.querySelector("img")).toHaveAttribute(
    "src",
    "https://github.com/favicon.ico",
  );
});

it.each([
  undefined,
  "ElevenLabs",
  "https://user:password@github.com",
  "javascript:alert(1)",
  "localhost",
  "127.0.0.1",
  "private.local",
])(
  "keeps a local brand fallback for an unknown or unsupported website: %s",
  (website) => {
    const { container } = render(<CompanySpinner website={website} />);
    expect(container.querySelector("img")).not.toBeInTheDocument();
    expect(container.querySelector("svg")).toBeInTheDocument();
  },
);

it("falls back to favicon discovery, then a monogram if both images fail", () => {
  const { container } = render(<CompanySpinner website="elevenlabs.io" />);
  fireEvent.error(container.querySelector("img")!);
  expect(container.querySelector("img")).toHaveAttribute(
    "src",
    "https://www.google.com/s2/favicons?domain=elevenlabs.io&sz=64",
  );
  fireEvent.error(container.querySelector("img")!);
  expect(container.querySelector("img")).not.toBeInTheDocument();
  expect(container.querySelector(".company-spinner__favicon")).toHaveAttribute(
    "data-monogram",
    "E",
  );
  expect(container.querySelector(".company-spinner__ring")).toBeInTheDocument();
});

it("resets icon failures when the researched website changes", () => {
  const { container, rerender } = render(
    <CompanySpinner website="elevenlabs.io" />,
  );
  fireEvent.error(container.querySelector("img")!);
  fireEvent.error(container.querySelector("img")!);
  rerender(<CompanySpinner website="github.com" />);
  expect(container.querySelector("img")).toHaveAttribute(
    "src",
    "https://github.com/favicon.ico",
  );
});

it("keeps the existing status announcement without adding image text or live regions", () => {
  render(
    <p role="status">
      <CompanySpinner website="github.com" size="small" />
      Research in progress
    </p>,
  );
  expect(screen.getAllByRole("status")).toHaveLength(1);
  expect(screen.getByRole("status")).toHaveTextContent(
    /^Research in progress$/,
  );
  expect(screen.queryByRole("img")).not.toBeInTheDocument();
});

it("honours the shared motion preference and updates without replacing the logo", () => {
  const { container, rerender } = render(
    <MotionProvider reducedMotion={false}>
      <CompanySpinner website="github.com" />
    </MotionProvider>,
  );
  const image = container.querySelector("img");
  expect(container.querySelector(".company-spinner__ring")).toHaveAttribute(
    "data-reduced-motion",
    "false",
  );
  rerender(
    <MotionProvider reducedMotion>
      <CompanySpinner website="github.com" />
    </MotionProvider>,
  );
  expect(container.querySelector(".company-spinner__ring")).toHaveAttribute(
    "data-reduced-motion",
    "true",
  );
  expect(container.querySelector("img")).toBe(image);
});
