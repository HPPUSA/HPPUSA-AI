import { readFileSync } from "node:fs";
import { test, expect } from "@playwright/test";

const markedScript = readFileSync(
  new URL("../node_modules/marked/lib/marked.umd.js", import.meta.url),
  "utf8"
);
const purifyScript = readFileSync(
  new URL("../node_modules/dompurify/dist/purify.min.js", import.meta.url),
  "utf8"
);

test.beforeEach(async ({ page }) => {
  await page.route(
    "https://cdn.jsdelivr.net/npm/marked@18.1.3/lib/marked.umd.js",
    (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/javascript",
        body: markedScript
      })
  );
  await page.route(
    "https://cdn.jsdelivr.net/npm/dompurify@3.4.17/dist/purify.min.js",
    (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/javascript",
        body: purifyScript
      })
  );
});

test("loads the actual HPPUSA-AI page and frontend libraries", async ({ page }) => {
  await page.goto("/");

  await expect(page).toHaveTitle("HPPUSA AI | Home Assistant");
  await expect(page.getByRole("heading", { name: "HPPUSA AI" })).toBeVisible();
  await expect(page.locator("#question")).toBeVisible();
  await expect(page.getByRole("button", { name: "Send message" })).toBeEnabled();

  const globals = await page.evaluate(() => ({
    marked: typeof window.marked,
    domPurify: typeof window.DOMPurify,
    formatter: typeof window.formatReply
  }));

  expect(globals).toEqual({
    marked: "object",
    domPurify: "function",
    formatter: "function"
  });
});

test("blocks active markup in a real browser while preserving safe Markdown", async ({ page }) => {
  await page.goto("/");

  const result = await page.evaluate(() => {
    const attack =
      '<img src=x onerror="window.__hppusaXss=1">' +
      '<svg onload="window.__hppusaXss=2"><circle /></svg>' +
      '<script>window.__hppusaXss=3</script>' +
      '<a href="javascript:window.__hppusaXss=4">unsafe link</a>';
    const container = document.createElement("div");
    container.innerHTML = window.formatReply(attack);

    const safe = document.createElement("div");
    safe.innerHTML = window.formatReply(
      "**Safe formatting** and [a normal link](https://example.com)"
    );

    return {
      scriptCount: container.querySelectorAll("script").length,
      eventAttributes: [...container.querySelectorAll("*")].flatMap((element) =>
        [...element.attributes]
          .filter((attribute) => /^on/i.test(attribute.name))
          .map((attribute) => attribute.name)
      ),
      javascriptLinks: [...container.querySelectorAll("a")].filter((anchor) =>
        /^javascript:/i.test(anchor.getAttribute("href") || "")
      ).length,
      xssExecuted: window.__hppusaXss !== undefined,
      safeStrong: safe.querySelector("strong")?.textContent,
      safeLink: safe.querySelector("a")?.getAttribute("href")
    };
  });

  expect(result).toEqual({
    scriptCount: 0,
    eventAttributes: [],
    javascriptLinks: 0,
    xssExecuted: false,
    safeStrong: "Safe formatting",
    safeLink: "https://example.com"
  });
});

test("validates empty input and displays a mocked response safely", async ({ page }) => {
  await page.goto("/");

  await page.getByRole("button", { name: "Send message" }).click();
  await expect(page.locator("#status")).toHaveText("Please enter a question first.");

  await page.route("**/chat", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        reply: '**Safe reply** <img src=x onerror="window.__hppusaXss=5">'
      })
    })
  );

  await page.locator("#question").fill("Help me organize a home maintenance checklist");
  await page.getByRole("button", { name: "Send message" }).click();

  await expect(page.locator("#chat .message.user").last()).toHaveText(
    "Help me organize a home maintenance checklist"
  );
  const reply = page.locator("#chat .message.bot").last();
  await expect(reply.locator("strong")).toHaveText("Safe reply");
  await expect(reply.locator("img")).not.toHaveAttribute("onerror", /.+/);
  await expect(page.getByRole("button", { name: "Send message" })).toBeEnabled();
  await expect(page.locator("#status")).toHaveText("");
});
