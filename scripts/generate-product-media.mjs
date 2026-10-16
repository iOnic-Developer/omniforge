#!/usr/bin/env node
/** Generate review media without network access or runtime dependencies.
 * npm package @resvg/resvg-js must be available to this script, or set
 * OMNIFORGE_RESVG_MODULE to its package directory / module file.
 * Optional --copy-fonts refreshes local TTFs AND their OFL licences from app/static.
 * SVG sources live in docs/site-assets; PNGs live in docs/assets.
 * Also reads the actual capture dimensions into index.html; never alters captures.
 */
import { readFile, writeFile, mkdir, copyFile } from "node:fs/promises";
import { createRequire } from "node:module";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import assert from "node:assert/strict";
const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const require = createRequire(import.meta.url);
let renderer;
try {
  renderer = require(process.env.OMNIFORGE_RESVG_MODULE || "@resvg/resvg-js");
} catch {
  throw new Error(
    "Install @resvg/resvg-js in your development environment, or set OMNIFORGE_RESVG_MODULE to its module path.",
  );
}
const Resvg = renderer.Resvg || renderer.default?.Resvg;
assert.equal(typeof Resvg, "function", "Resvg export is available");
const sources = join(root, "docs/site-assets");
const assets = join(root, "docs/assets");
const fonts = join(sources, "fonts");
await mkdir(fonts, { recursive: true });
await mkdir(assets, { recursive: true });
if (process.argv.includes("--copy-fonts")) {
  for (const name of [
    "manrope.ttf",
    "jetbrains-mono.ttf",
    "OFL-Manrope.txt",
    "OFL-JetBrainsMono.txt",
  ]) {
    await copyFile(join(root, "app/static/fonts", name), join(fonts, name));
  }
}
const mark = (x, y, size = 64) =>
  `<g transform="translate(${x} ${y}) scale(${size / 64})"><rect width="64" height="64" rx="4" fill="#116859"/><path fill="#f3f8f2" d="M16 16h32v10H26v12h12V28h10v20H16z"/></g>`;
const text = (
  x,
  y,
  size,
  content,
  fill = "#f5f7ec",
  weight = 500,
  family = "Manrope",
) =>
  `<text x="${x}" y="${y}" font-family="${family}" font-size="${size}" font-weight="${weight}" fill="${fill}">${content}</text>`;
const svg = (w, h, content, title) =>
  `<svg xmlns="http://www.w3.org/2000/svg" width="${w}" height="${h}" viewBox="0 0 ${w} ${h}" role="img" aria-labelledby="title"><title id="title">${title}</title>${content}</svg>\n`;
function brandMedia(w, h) {
  const social = w === 1200;
  const tx = social ? 64 : 72,
    titleY = social ? 238 : 226;
  const right = social ? 814 : 1130;
  return svg(
    w,
    h,
    `<rect width="${w}" height="${h}" fill="#153f36"/><path d="M${right - 40} 0V${h}" stroke="#4b6e5a"/>${mark(tx, 48, 48)}${text(tx + 64, 81, 27, "OmniForge", "#f5f7ec", 750)}${text(tx, 148, 12, "PYTHON + NODE / A WORKSPACE FOR YOUR TOOLS", "#c2d5c8", 500, "JetBrains Mono")}${text(tx, titleY, social ? 64 : 76, "Your scripts.", "#f5f7ec", 700)}${text(tx, titleY + 86, social ? 64 : 76, "Your AI’s tools.", "#d9e6bb", 700)}${text(tx, titleY + 146, 20, "Create something useful. Test the saved code.", "#c2d5c8")}${text(tx, titleY + 178, 20, "Discover enabled tools through limited HTTP JSON-RPC.", "#c2d5c8")}<path d="M${tx} ${h - 83}H${w - 64}" stroke="#75917d"/>${text(tx, h - 43, 12, "SELF-HOSTED · TRUSTED LAN ONLY", "#c2d5c8", 500, "JetBrains Mono")}${text(right, 147, 12, "THE SHORT PATH", "#c2d5c8", 500, "JetBrains Mono")}${[
      ["01", "Create"],
      ["02", "Test saved"],
      ["03", "Discover"],
    ]
      .map(
        ([n, label], i) =>
          `<rect x="${right}" y="${185 + i * 86}" width="${w - right - 42}" height="68" rx="4" fill="#102d27" stroke="#6d8b75"/>${text(right + 16, 225 + i * 86, 13, n, "#d9bb6e", 500, "JetBrains Mono")}${text(right + 54, 225 + i * 86, 19, label, "#f5f7ec", 600)}`,
      )
      .join("")}`,
    "OmniForge — Your scripts. Your AI’s tools.",
  );
}
const diagram = svg(
  1600,
  560,
  `<rect width="1600" height="560" fill="#f7f6ef"/>${mark(48, 40, 40)}${text(106, 69, 24, "OmniForge", "#153f36", 750)}${text(48, 133, 16, "ORDINARY SCRIPTS. AN EXPLICIT WORKFLOW.", "#52645c", 500, "JetBrains Mono")}${[
    [
      "01 / CREATE",
      "Write one useful script.",
      "Python or Node",
      "Named tool + package requirements",
    ],
    [
      "02 / TEST SAVED",
      "Inspect what actually ran.",
      "JSON input → stdout",
      "Save first. Review errors and timing.",
    ],
    [
      "03 / DISCOVER",
      "Let a client find the tool.",
      "POST /mcp · tools/list",
      "Limited HTTP JSON-RPC; check your client.",
    ],
  ]
    .map(([n, title, code, detail], i) => {
      const x = 48 + i * 510;
      return `<rect x="${x}" y="178" width="484" height="258" rx="4" fill="${i === 2 ? "#153f36" : "#fffef8"}" stroke="#9eafa0"/>${text(x + 24, 218, 13, n, i === 2 ? "#d9e6bb" : "#116859", 500, "JetBrains Mono")}${text(x + 24, 272, 27, title, i === 2 ? "#f5f7ec" : "#1e302a", 650)}${text(x + 24, 326, 17, code, i === 2 ? "#d9e6bb" : "#116859", 500, "JetBrains Mono")}${text(x + 24, 392, 16, detail, i === 2 ? "#c2d5c8" : "#52645c")}`;
    })
    .join(
      "",
    )}${text(48, 504, 15, "Trusted LAN only. Dashboard and management API are unauthenticated. Scripts share the application container.", "#52645c")}`,
  "Create, test saved code, discover — OmniForge workflow",
);
for (const [name, width, height, source] of [
  ["banner", 1600, 560, brandMedia(1600, 560)],
  ["social-preview", 1200, 630, brandMedia(1200, 630)],
  ["how-it-works", 1600, 560, diagram],
]) {
  const rendered = new Resvg(source, {
    font: {
      fontFiles: [
        join(fonts, "manrope.ttf"),
        join(fonts, "jetbrains-mono.ttf"),
      ],
      loadSystemFonts: false,
      defaultFontFamily: "Manrope",
    },
  })
    .render()
    .asPng();
  assert.equal(rendered.readUInt32BE(16), width);
  assert.equal(rendered.readUInt32BE(20), height);
  await writeFile(join(sources, `${name}.svg`), source);
  await writeFile(join(assets, `${name}.png`), rendered);
  console.log(
    `${name}: ${width}×${height}, SVG + PNG (${rendered.length} bytes)`,
  );
}
let html = await readFile(join(root, "docs/index.html"), "utf8");
html = await replaceAsync(
  html,
  /<img\b[^>]*src="assets\/screenshots\/[^"<>]+\.png"[^>]*>/g,
  async (tag) => {
    const src = tag.match(/src="([^"]+)"/)[1];
    const png = await readFile(join(root, "docs", src));
    assert.equal(png.subarray(0, 8).toString("hex"), "89504e470d0a1a0a");
    const w = png.readUInt32BE(16),
      h = png.readUInt32BE(20);
    console.log(`${src}: read actual capture ${w}×${h}`);
    return tag
      .replace(/width="\d+"/, `width="${w}"`)
      .replace(/height="\d+"/, `height="${h}"`);
  },
);
await writeFile(join(root, "docs/index.html"), html);
async function replaceAsync(str, re, fn) {
  const matches = [...str.matchAll(re)];
  const replacements = await Promise.all(matches.map((m) => fn(m[0])));
  let i = 0;
  return str.replace(re, () => replacements[i++]);
}
