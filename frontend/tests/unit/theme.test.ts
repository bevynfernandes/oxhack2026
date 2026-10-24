import { readFileSync } from "node:fs";
import { expect, it } from "vitest";

const css = readFileSync("src/theme/theme.css", "utf8");
const tokens = Object.fromEntries(
  [...css.matchAll(/--theme-([\w-]+):\s*(#[0-9a-f]{6})/g)].map((match) => [
    match[1],
    match[2],
  ]),
);
function luminance(hex: string) {
  const channels = hex
    .slice(1)
    .match(/../g)!
    .map((value) => {
      const channel = Number.parseInt(value, 16) / 255;
      return channel <= 0.04045
        ? channel / 12.92
        : ((channel + 0.055) / 1.055) ** 2.4;
    });
  return channels[0] * 0.2126 + channels[1] * 0.7152 + channels[2] * 0.0722;
}
function contrast(foreground: string, background: string) {
  const a = luminance(tokens[foreground]);
  const b = luminance(tokens[background]);
  return (Math.max(a, b) + 0.05) / (Math.min(a, b) + 0.05);
}

it.each([
  ["text", "canvas"],
  ["text", "surface"],
  ["text", "raised"],
  ["muted", "canvas"],
  ["muted", "surface"],
  ["muted", "raised"],
  ["accent", "canvas"],
  ["accent", "surface"],
  ["accent", "selected"],
  ["canvas", "accent"],
  ["text", "action"],
  ["text", "action-hover"],
  ["warning", "warning-surface"],
  ["danger", "danger-surface"],
  ["positive", "surface"],
])("keeps %s text on %s at WCAG AA contrast", (foreground, background) => {
  expect(contrast(foreground, background)).toBeGreaterThanOrEqual(4.5);
});
it.each(["canvas", "surface", "raised"])(
  "keeps input boundaries distinguishable on %s",
  (surface) => {
    expect(contrast("control-line", surface)).toBeGreaterThanOrEqual(3);
  },
);
