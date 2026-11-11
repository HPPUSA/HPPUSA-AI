import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { JSDOM } from "jsdom";
import createDOMPurify from "dompurify";
import { marked } from "marked";

const appPath = fileURLToPath(new URL("../App.py", import.meta.url));
const appSource = readFileSync(appPath, "utf8");
const pageMatch = appSource.match(/PAGE = """([\s\S]*?)"""/);

assert.ok(pageMatch, "Could not locate the PAGE template in App.py");

const html = pageMatch[1].replace(
  /<script src="[^"]+"><\/script>/g,
  ""
);

const dom = new JSDOM(html, {
  runScripts: "dangerously",
  beforeParse(window) {
    window.marked = marked;
    window.DOMPurify = createDOMPurify(window);
  }
});

try {
  const { window } = dom;
  assert.equal(typeof window.formatReply, "function");

  const attack =
    '<img src=x onerror="window.__xss=1">' +
    '<svg onload="window.__xss=2"><circle /></svg>' +
    '<script>window.__xss=3</script>' +
    '<a href="javascript:window.__xss=4">unsafe link</a>';

  const rendered = window.formatReply(attack);
  const container = window.document.createElement("div");
  container.innerHTML = rendered;

  assert.equal(container.querySelector("script"), null, "script element survived");
  assert.equal(container.querySelector("img"), null, "unsafe image element survived");
  assert.equal(container.querySelector("svg"), null, "unsafe SVG element survived");

  for (const element of container.querySelectorAll("*")) {
    for (const attribute of element.attributes) {
      assert.ok(
        !/^on/i.test(attribute.name),
        `event-handler attribute survived: ${attribute.name}`
      );
      assert.ok(
        !/^javascript:/i.test(attribute.value.trim()),
        `javascript URL survived: ${attribute.value}`
      );
    }
  }

  assert.equal(window.__xss, undefined, "an injected script executed");

  const benign = window.formatReply(
    "**Safe formatting** and [a normal link](https://example.com)"
  );
  const safeContainer = window.document.createElement("div");
  safeContainer.innerHTML = benign;

  assert.equal(
    safeContainer.querySelector("strong")?.textContent,
    "Safe formatting"
  );
  assert.equal(
    safeContainer.querySelector("a")?.getAttribute("href"),
    "https://example.com"
  );

  console.log("Frontend XSS checks passed: unsafe markup blocked; safe Markdown retained.");
} finally {
  dom.window.close();
}
