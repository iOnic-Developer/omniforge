const { test } = require("node:test");
const assert = require("node:assert/strict");
const vm = require("node:vm");
const fs = require("node:fs");
function worker() {
  const handlers = {},
    stores = new Map(),
    requests = [],
    deleted = [];
  let skipped = 0,
    claimed = 0;
  const cache = (name) => {
    if (!stores.has(name)) stores.set(name, new Map());
    const store = stores.get(name);
    return {
      put: async (k, v) => store.set(k, v),
      match: async (k) => store.get(k),
    };
  };
  const context = vm.createContext({
    URL,
    Response,
    self: {
      location: { origin: "https://forge.test" },
      addEventListener: (n, f) => (handlers[n] = f),
      skipWaiting() {
        skipped++;
      },
      clients: {
        claim: async () => {
          claimed++;
        },
      },
    },
    caches: {
      open: async (name) => cache(name),
      keys: async () => [...stores.keys()],
      delete: async (name) => {
        deleted.push(name);
        stores.delete(name);
      },
    },
    fetch: async (req, options) => {
      requests.push({ req, options });
      const path = typeof req === "string" ? req : new URL(req.url).pathname;
      const mime = path.endsWith(".html") ? "text/html" : path.endsWith(".css") ? "text/css" :
        path.endsWith(".svg") ? "image/svg+xml" : path.endsWith(".png") ? "image/png" :
        path.endsWith(".ttf") ? "font/ttf" : "application/manifest+json";
      return { ok: true, public: true, redirected:false, headers:new Headers({"Content-Type":mime}) };
    },
  });
  vm.runInContext(fs.readFileSync("app/static/sw.js", "utf8"), context);
  return {
    handlers,
    stores,
    requests,
    deleted,
    context,
    get skipped() {
      return skipped;
    },
    get claimed() {
      return claimed;
    },
    assets: JSON.parse(vm.runInContext("JSON.stringify(ASSETS)", context)),
    name: vm.runInContext("CACHE", context),
  };
}
async function install(w) {
  let pending;
  w.handlers.install({ waitUntil: (p) => (pending = p) });
  await pending;
}
function get(w, path, options = {}) {
  let handled = false,
    pending;
  w.handlers.fetch({
    request: {
      url: "https://forge.test" + path,
      method: "GET",
      mode: "cors",
      headers: new Headers(),
      ...options,
    },
    respondWith: (p) => {
      handled = true;
      pending = p;
    },
  });
  return { handled, pending };
}
test("precache is exactly public allowlist with credentials omitted", async () => {
  const w = worker();
  await install(w);
  assert.equal(w.stores.get(w.name).size, 12);
  assert.ok(w.requests.every((r) => r.options.credentials === "omit"));
  assert.ok(w.assets.every((p) => p.startsWith("/assets/")));
  assert.equal(w.skipped, 0);
});
test("API, MCP, POST, authorization, cross-origin and query assets bypass cache", async () => {
  const w = worker();
  await install(w);
  for (const [path, options] of [
    ["/api/tools", {}],
    ["/mcp", {}],
    ["/anything", { method: "POST" }],
    [
      "/assets/product.css",
      { headers: new Headers({ Authorization: "Bearer test-placeholder" }) },
    ],
    ["/assets/product.css", { url: "https://other.test/assets/product.css" }],
    ["/assets/product.css?private=yes", {}],
    ["/unknown", {}],
  ])
    assert.equal(get(w, path, options).handled, false, path);
});
test("successful navigation is never stored", async () => {
  const w = worker();
  await install(w);
  const result = get(w, "/", { mode: "navigate" });
  assert.equal(result.handled, true);
  assert.equal((await result.pending).ok, true);
  assert.equal(w.stores.get(w.name).has("/"), false);
});
test("failed navigation gets generic offline page only", async () => {
  const w = worker();
  await install(w);
  const fallback = { generic: true };
  w.stores.get(w.name).set("/assets/offline.html", fallback);
  w.context.fetch = async () => {
    throw new Error("offline");
  };
  const result = get(w, "/", { mode: "navigate" });
  assert.equal(await result.pending, fallback);
  assert.equal(w.stores.get(w.name).size, 12);
});
test("static cache serves without caching arbitrary responses", async () => {
  const w = worker();
  await install(w);
  const count = w.requests.length;
  assert.equal((await get(w, "/assets/product.css").pending).public, true);
  assert.equal(w.requests.length, count);
  w.stores.get(w.name).delete("/assets/product.css");
  await get(w, "/assets/product.css").pending;
  assert.equal(w.stores.get(w.name).has("/assets/product.css"), false);
});
test("activation removes only previous OmniForge caches and claims clients", async () => {
  const w = worker();
  await install(w);
  w.stores.set("omniforge-public-old", new Map());
  w.stores.set("other-app-cache", new Map());
  let pending;
  w.handlers.activate({ waitUntil: (p) => (pending = p) });
  await pending;
  assert.deepEqual(w.deleted, ["omniforge-public-old"]);
  assert.ok(w.stores.has("other-app-cache"));
  assert.equal(w.claimed, 1);
});
test("updates require explicit skip-waiting message", async () => {
  const w = worker();
  await install(w);
  w.handlers.message({ data: { type: "UNRELATED" } });
  assert.equal(w.skipped, 0);
  w.handlers.message({ data: { type: "SKIP_WAITING" } });
  assert.equal(w.skipped, 1);
});

for (const [label,response] of [
  ["redirect",{ok:true,redirected:true,headers:new Headers({"Content-Type":"text/html"})}],
  ["login HTML instead of CSS",{ok:true,redirected:false,headers:new Headers({"Content-Type":"text/html"})}],
  ["missing MIME",{ok:true,redirected:false,headers:new Headers()}],
  ["bad status",{ok:false,redirected:false,headers:new Headers({"Content-Type":"text/css"})}]
]) test(`precache rejects ${label}`,async () => {
  const w=worker(); const original=w.context.fetch;
  w.context.fetch=async (path,options) => path==="/assets/product.css" ? response : original(path,options);
  await assert.rejects(install(w),/Unexpected public asset response/);
  assert.equal(w.stores.get(w.name).has("/assets/product.css"),false);
});
test("precache requests disallow following redirects",async () => {
  const w=worker(); await install(w);
  assert.ok(w.requests.every(r => r.options.redirect==="error"));
});
