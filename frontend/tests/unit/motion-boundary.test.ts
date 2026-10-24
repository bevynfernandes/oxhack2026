import { readdirSync, readFileSync } from "node:fs";
import { resolve } from "node:path";
import { expect, it } from "vitest";
import ts from "typescript";

function sources(directory: string): string[] {
  return readdirSync(directory, { withFileTypes: true }).flatMap((entry) => {
    if (entry.name === "motion") return [];
    const path = resolve(directory, entry.name);
    return entry.isDirectory()
      ? sources(path)
      : /\.(tsx?|css)$/.test(path)
        ? [path]
        : [];
  });
}
function violations(path: string, source: string): string[] {
  if (path.endsWith(".css")) {
    return /@keyframes|\b(?:transition|animation)(?:-[\w-]+)?\s*:/.test(source)
      ? ["CSS motion outside shared library"]
      : [];
  }
  const found: string[] = [];
  const tree = ts.createSourceFile(
    path,
    source,
    ts.ScriptTarget.Latest,
    true,
    ts.ScriptKind.TSX,
  );
  const visit = (node: ts.Node) => {
    if (
      ts.isImportDeclaration(node) &&
      ts.isStringLiteral(node.moduleSpecifier) &&
      /^(motion|framer-motion)(\/|$)/.test(node.moduleSpecifier.text)
    )
      found.push("direct engine import");
    if (
      ts.isCallExpression(node) &&
      node.expression.kind === ts.SyntaxKind.ImportKeyword &&
      node.arguments[0] &&
      ts.isStringLiteral(node.arguments[0]) &&
      /^(motion|framer-motion)(\/|$)/.test(node.arguments[0].text)
    )
      found.push("dynamic engine import");
    if (ts.isJsxOpeningElement(node) || ts.isJsxSelfClosingElement(node)) {
      if (
        ["button", "input", "select", "details", "dialog"].includes(
          node.tagName.getText(tree),
        )
      )
        found.push("unshared interactive primitive");
      for (const attribute of node.attributes.properties) {
        if (
          ts.isJsxAttribute(attribute) &&
          [
            "animate",
            "initial",
            "exit",
            "transition",
            "whileTap",
            "whileHover",
            "layout",
            "layoutId",
          ].includes(attribute.name.getText(tree))
        )
          found.push("local animation settings");
      }
    }
    if (
      ts.isPropertyAssignment(node) &&
      [
        "transition",
        "animation",
        "animationDuration",
        "transitionDuration",
      ].includes(node.name.getText(tree).replaceAll('"', "")) &&
      node.initializer.kind !== ts.SyntaxKind.FalseKeyword
    )
      found.push("local animation configuration");
    ts.forEachChild(node, visit);
  };
  visit(tree);
  return found;
}
it("keeps engines, widget motion and CSS animation declarations inside the shared library", () => {
  const failures = sources(resolve("src")).flatMap((path) =>
    violations(path, readFileSync(path, "utf8")).map(
      (reason) => `${path}: ${reason}`,
    ),
  );
  expect(failures).toEqual([]);
});
it("rejects direct imports, local timing, and unshared controls", () => {
  expect(
    violations(
      "sample.tsx",
      'import { motion } from "motion/react"; const x = <motion.button transition={{ duration: 1 }} />;',
    ),
  ).toEqual(["direct engine import", "local animation settings"]);
  expect(violations("sample.tsx", "const x = <button>Go</button>;")).toEqual([
    "unshared interactive primitive",
  ]);
  expect(
    violations("sample.css", ".card { transition: opacity 100ms; }"),
  ).toEqual(["CSS motion outside shared library"]);
});
