#!/usr/bin/env node
/** Static checks use Node built-ins only. Full run requires the existing dev
 * dependencies playwright and @axe-core/playwright. No package changes needed.
 * Overrides: OMNIFORGE_PLAYWRIGHT_MODULE, OMNIFORGE_AXE_MODULE (module paths),
 * OMNIFORGE_CHROMIUM_EXECUTABLE (optional), OMNIFORGE_PAGE_TEST_OUTPUT (optional).
 * --static-only runs the built-in checks but does NOT count as browser acceptance.
 * Serves only the page and explicitly public demo assets on ephemeral loopback;
 * never serves docs/review, source code, or any application/production endpoint.
 */
import assert from "node:assert/strict";
import { readFile, stat, mkdir } from "node:fs/promises";
import { createServer } from "node:http";
import { createRequire } from "node:module";
import { dirname, extname, join, resolve, sep } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";
const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const docs = join(root, "docs");
const html = await readFile(join(docs, "index.html"), "utf8");
const css = await readFile(join(docs, "site.css"), "utf8");
const js = await readFile(join(docs, "site.js"), "utf8");
const ids = [...html.matchAll(/\bid="([^"]+)"/g)].map((m) => m[1]);
assert.equal(new Set(ids).size, ids.length, "unique IDs");
assert.equal((html.match(/<h1\b/g) || []).length, 1, "one H1");
assert.match(html, /<meta name="robots" content="noindex, nofollow">/);
assert.doesNotMatch(
  html,
  /rel="(?:canonical|preconnect|dns-prefetch)"|og:url|https?:\/\/(?:fonts\.|.*github\.io)/i,
);
assert.doesNotMatch(
  html,
  /docs\/review|review\/2026|demo\.gif|chatgpt|only latest|only.*tag.*latest/i,
);
assert.ok(
  html.indexOf('id="boundaries"') < html.indexOf('id="start"'),
  "constraints before installation",
);
for (const phrase of [
  "unauthenticated",
  "127.0.0.1:8000:8000",
  "OMNIFORGE_API_KEY:?",
  "export OMNIFORGE_API_KEY",
  "not full Streamable HTTP",
  "not been live-verified",
  "inherit the app’s environment",
  "HTTPS or localhost",
])
  assert.ok(html.includes(phrase), `honest copy: ${phrase}`);
assert.doesNotMatch(
  js,
  /\bfetch\s*\(|XMLHttpRequest|serviceWorker|localStorage|innerHTML/,
);
assert.doesNotMatch(css, /@import|https?:/);
const refs = [...html.matchAll(/\b(?:href|src)="([^"]+)"/g)]
  .map((m) => m[1])
  .filter(
    (s) =>
      s.startsWith("#") ||
      /^(?:assets\/|site-assets\/|wiki\/|site\.(?:css|js))/.test(s),
  );
for (const ref of refs) {
  if (ref.startsWith("#"))
    assert.ok(ids.includes(ref.slice(1)), `anchor ${ref}`);
  else assert.ok((await stat(join(docs, ref))).isFile(), `local file ${ref}`);
}
for (const m of css.matchAll(/url\(['"]?([^)'"\s]+)['"]?\)/g))
  assert.ok((await stat(join(docs, m[1]))).isFile(), `font ${m[1]}`);
for (const match of html.matchAll(/<img\b[^>]*>/g)) {
  const tag = match[0];
  assert.match(tag, /\balt="[^"]*"/, "image alt");
  assert.match(tag, /\bwidth="\d+"/);
  assert.match(tag, /\bheight="\d+"/);
  const src = tag.match(/src="([^"]+)"/)[1];
  if (src.endsWith(".png")) {
    const png = await readFile(join(docs, src));
    assert.equal(
      png.readUInt32BE(16),
      Number(tag.match(/width="(\d+)"/)[1]),
      `${src} width`,
    );
    assert.equal(
      png.readUInt32BE(20),
      Number(tag.match(/height="(\d+)"/)[1]),
      `${src} height`,
    );
  }
}
for (const [name, w, h] of [
  ["banner", 1600, 560],
  ["social-preview", 1200, 630],
  ["how-it-works", 1600, 560],
]) {
  const b = await readFile(join(docs, "assets", `${name}.png`));
  assert.equal(b.readUInt32BE(16), w);
  assert.equal(b.readUInt32BE(20), h);
  assert.match(
    await readFile(join(docs, "site-assets", `${name}.svg`), "utf8"),
    /<svg/,
  );
}
for (const name of [
  "manrope.ttf",
  "jetbrains-mono.ttf",
  "OFL-Manrope.txt",
  "OFL-JetBrainsMono.txt",
])
  assert.deepEqual(
    await readFile(join(docs, "site-assets/fonts", name)),
    await readFile(join(root, "app/static/fonts", name)),
    `original local font/licence: ${name}`,
  );
assert.deepEqual(
  await readFile(join(docs, "site-assets/mark.svg")),
  await readFile(join(root, "app/static/mark.svg")),
  "original square identity",
);
const external = [...html.matchAll(/(?:href|src)="(https?:[^"<>]+)"/g)].map(
  (m) => m[1],
);
assert.ok(
  external.every((s) => s === "https://hub.docker.com/r/dbzocchi/omniforge"),
  "only Docker Hub outbound CTA",
);
console.log(
  "PASS static: local assets, primary links, exact PNG sizes, identity/fonts/licences, private metadata, safe local-bind copy.",
);
if (process.argv.includes("--static-only")) {
  console.log("Browser acceptance NOT RUN (--static-only).");
  process.exit(0);
}
const require = createRequire(import.meta.url);
function load(spec, label) {
  try {
    return require(spec);
  } catch {
    throw new Error(
      `${label} is required for full acceptance. Install existing devDependencies or supply its OMNIFORGE_*_MODULE override. Browser tests are never silently skipped.`,
    );
  }
}
const pw = load(
  process.env.OMNIFORGE_PLAYWRIGHT_MODULE || "playwright",
  "Playwright",
);
const chromium = pw.chromium || pw.default?.chromium;
const axe = load(
  process.env.OMNIFORGE_AXE_MODULE || "@axe-core/playwright",
  "axe",
);
const AxeBuilder = axe.AxeBuilder || axe.default?.AxeBuilder || axe.default;
assert.equal(
  typeof AxeBuilder,
  "function",
  "named/default AxeBuilder resolution",
);
const types = {
  ".html": "text/html; charset=utf-8",
  ".css": "text/css",
  ".js": "text/javascript",
  ".svg": "image/svg+xml",
  ".png": "image/png",
  ".ttf": "font/ttf",
  ".txt": "text/plain",
  ".md": "text/plain",
};
const server = createServer(async (req, res) => {
  try {
    const name =
      decodeURIComponent(new URL(req.url, "http://localhost").pathname).replace(
        /^\//,
        "",
      ) || "index.html";
    assert.ok(
      /^(?:index\.html|site\.(?:css|js)|site-assets\/[\w./-]+|assets\/[\w./-]+|wiki\/[\w-]+\.md)$/.test(
        name,
      ),
    );
    const path = resolve(docs, name);
    assert.ok(path.startsWith(docs + sep));
    const body = await readFile(path);
    res.writeHead(200, {
      "Content-Type": types[extname(path)] || "application/octet-stream",
      "Cache-Control": "no-store",
    });
    res.end(body);
  } catch {
    res.writeHead(404);
    res.end("Not found");
  }
});
let browser;
const errors = [],
  remote = [],
  missing = [],
  consoleErrors = [];
await new Promise((r) => server.listen(0, "127.0.0.1", r));
const base = `http://127.0.0.1:${server.address().port}`;
try {
  browser = await chromium.launch({
    headless: true,
    ...(process.env.OMNIFORGE_CHROMIUM_EXECUTABLE
      ? { executablePath: process.env.OMNIFORGE_CHROMIUM_EXECUTABLE }
      : {}),
  });
  for (const colorScheme of ["light", "dark"])
    for (const viewport of [
      { width: 375, height: 812 },
      { width: 812, height: 375 },
      { width: 768, height: 1024 },
      { width: 1440, height: 1000 },
    ]) {
      const context = await browser.newContext({
        viewport,
        colorScheme,
        reducedMotion: "reduce",
      });
      await context.route("**/*", (route) => {
        const u = route.request().url();
        if (!u.startsWith(base + "/")) {
          remote.push(u);
          return route.abort();
        }
        return route.continue();
      });
      const page = await context.newPage();
      page.on("pageerror", (e) => errors.push(e.message));
      page.on("console", (m) => {
        if (m.type() === "error") consoleErrors.push(m.text());
      });
      page.on("response", (r) => {
        if (r.status() >= 400) missing.push(r.url());
      });
      await page.goto(base, { waitUntil: "networkidle" });
      await page.evaluate(() => document.fonts.ready);
      for (const image of await page.locator("img").all())
        await image.scrollIntoViewIfNeeded();
      await page.evaluate(async () => {
        await Promise.all([...document.images].map((i) => i.decode()));
      });
      const wide = await page.evaluate(
        () => document.documentElement.scrollWidth > innerWidth + 1,
      );
      assert.equal(wide, false, `no overflow ${viewport.width} ${colorScheme}`);
      const short = await page.locator("a,button,summary").evaluateAll((els) =>
        els
          .filter((e) => {
            const r = e.getBoundingClientRect();
            return (
              r.width > 0 && r.height > 0 && (r.height < 44 || r.width < 44)
            );
          })
          .map((e) => ({
            text: e.textContent.trim(),
            width: e.getBoundingClientRect().width,
            height: e.getBoundingClientRect().height,
          })),
      );
      assert.deepEqual(
        short,
        [],
        `44px targets ${viewport.width} ${colorScheme}`,
      );
      const summary = page.locator("summary");
      await summary.focus();
      await page.keyboard.press("Enter");
      assert.equal(await page.locator("details").getAttribute("open"), "");
      await page.keyboard.press("Enter");
      const result = await new AxeBuilder({ page })
        .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"])
        .analyze();
      assert.deepEqual(
        result.violations.map((v) => ({
          id: v.id,
          nodes: v.nodes.map((n) => ({
            target: n.target,
            summary: n.failureSummary,
          })),
        })),
        [],
        `axe ${viewport.width} ${colorScheme}`,
      );
      await page.goto(base, { waitUntil: "networkidle" });
      await page.keyboard.press("Tab");
      assert.equal(
        await page.locator(":focus").textContent(),
        "Skip to content",
      );
      await page.keyboard.press("Enter");
      assert.equal(new URL(page.url()).hash, "#main");
      let tabs = 0;
      const seen = new Set();
      for (let i = 0; i < 60; i++) {
        await page.keyboard.press("Tab");
        const focused = await page.evaluate(() => {
          const e = document.activeElement;
          return {
            key: e.tagName + e.textContent,
            outline: parseFloat(getComputedStyle(e).outlineWidth),
            tag: e.tagName,
          };
        });
        if (focused.tag === "BODY") break;
        assert.ok(focused.outline >= 2, "visible keyboard focus");
        seen.add(focused.key);
        tabs++;
      }
      assert.ok(tabs > 15 && seen.size > 15, "keyboard reaches page controls");
      const copy = page.getByRole("button", { name: "Copy pull command" });
      await copy.focus();
      await page.keyboard.press("Enter");
      await page.waitForFunction(
        () => document.querySelector("#copy-status").textContent.length > 0,
      );
      assert.match(
        await page.locator("#copy-status").textContent(),
        /copied|Clipboard unavailable/,
      );
      await page.getByRole("link", { name: /Start locally/ }).click();
      assert.equal(new URL(page.url()).hash, "#start");
      assert.equal(
        await page.evaluate(
          () =>
            getComputedStyle(document.querySelector(".primary"))
              .transitionDuration,
        ),
        "0s",
        "reduced motion",
      );
      await context.setOffline(true);
      await summary.click();
      assert.equal(await page.locator("details").getAttribute("open"), "");
      assert.equal(
        await page.locator("h1").count(),
        1,
        "offline open page retains content",
      );
      if (process.env.OMNIFORGE_PAGE_TEST_OUTPUT) {
        await mkdir(process.env.OMNIFORGE_PAGE_TEST_OUTPUT, {
          recursive: true,
        });
        await page.evaluate(() => scrollTo(0, 0));
        await page.screenshot({
          path: join(
            process.env.OMNIFORGE_PAGE_TEST_OUTPUT,
            `page-${viewport.width}-${colorScheme}.png`,
          ),
          fullPage: true,
        });
      }
      await context.close();
      console.log(
        `PASS browser ${viewport.width}×${viewport.height} ${colorScheme}: axe, targets, keyboard, anchors, copy, offline, reduced motion, no overflow.`,
      );
    }
  const zoom = await browser.newContext({
    viewport: { width: 720, height: 600 },
  });
  const zp = await zoom.newPage();
  await zp.goto(base);
  await zp.addStyleTag({ content: "html{font-size:200%}" });
  assert.equal(
    await zp.evaluate(
      () => document.documentElement.scrollWidth > innerWidth + 1,
    ),
    false,
    "200% text at half desktop width",
  );
  await zoom.close();
  console.log("PASS 200% text resize at 720px (half desktop width).");
  const nojs = await browser.newContext({
    javaScriptEnabled: false,
    viewport: { width: 375, height: 812 },
  });
  const np = await nojs.newPage();
  await np.goto(base);
  assert.equal(await np.locator("h1").count(), 1);
  assert.equal(
    await np.getByRole("button").count(),
    0,
    "copy controls hidden without JavaScript",
  );
  await np.locator("summary").click();
  assert.equal(await np.locator("details").getAttribute("open"), "");
  await np.getByRole("link", { name: /Start locally/ }).click();
  assert.equal(new URL(np.url()).hash, "#start");
  await nojs.close();
  console.log(
    "PASS no-JavaScript: content, links and disclosure remain usable.",
  );
  const offline = await browser.newContext({ offline: true });
  const op = await offline.newPage();
  op.on("pageerror", (e) => errors.push(e.message));
  await op.goto(pathToFileURL(join(docs, "index.html")).href);
  await op.evaluate(() => document.fonts.ready);
  assert.equal(await op.locator("h1").count(), 1);
  assert.equal(
    await op.evaluate(() => document.fonts.check("16px Manrope")),
    true,
  );
  await op.locator("summary").click();
  assert.equal(await op.locator("details").getAttribute("open"), "");
  await offline.close();
  console.log(
    "PASS fully offline file-open: page, stylesheet, fonts and disclosure.",
  );
  assert.deepEqual(remote, [], "zero remote asset/network requests");
  assert.deepEqual(missing, [], "no missing browser assets");
  assert.deepEqual(errors, [], "no browser JS errors");
  assert.deepEqual(consoleErrors, [], "no browser console errors");
  console.log(
    "PASS external requests: 0; console page errors: 0; missing assets: 0.",
  );
} finally {
  if (browser) await browser.close();
  await new Promise((r) => server.close(r));
}
