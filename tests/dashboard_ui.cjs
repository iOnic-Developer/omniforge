// Dependency-free DOM harness; actual browser coverage lives in product_browser.cjs.
const assert = require("node:assert/strict");
const { test } = require("node:test");
const fs = require("node:fs");
const vm = require("node:vm");
const page = fs.readFileSync("app/templates/dashboard.html", "utf8");
class Element {
  constructor(tag = "div") {
    this.tagName = tag;
    this.value = "";
    this._disabled = false;
    this.children = [];
    this.handlers = {};
    this.attributes = {};
    this.dataset = {};
    this.style = {};
    this.className = "";
    this.hidden = false;
    this.scrollTop = 0;
    this.selectionStart = 0;
    this.selectionEnd = 0;
    this.classList = {
      toggle: (c, on) => {
        const set = new Set(this.className.split(" "));
        if (on ?? !set.has(c)) set.add(c);
        else set.delete(c);
        this.className = [...set].join(" ");
      },
      contains: (c) => this.className.split(" ").includes(c),
    };
  }
  set disabled(value) {
    this._disabled = value;
    if (value && this.document?.activeElement === this) this.document.activeElement = this.document.body;
  }
  get disabled() { return this._disabled; }
  addEventListener(name, fn) {
    (this.handlers[name] ||= []).push(fn);
  }
  async emit(name, event = {}) {
    for (const handler of this.handlers[name] || []) await handler(event);
  }
  append(...items) {
    this.children.push(...items);
  }
  replaceChildren(...items) {
    const descendants = e => [e,...e.children.flatMap(descendants)];
    if (this.document && this.children.flatMap(descendants).includes(this.document.activeElement))
      this.document.activeElement = this.document.body;
    this.children = items;
  }
  setAttribute(k, v) {
    this.attributes[k] = String(v);
  }
  getAttribute(k) {
    return this.attributes[k] ?? null;
  }
  removeAttribute(k) {
    delete this.attributes[k];
  }
  focus() {
    if (this.disabled) return;
    this.focused = true;
    if (this.document) this.document.activeElement = this;
  }
  showModal() {
    this.open = true;
  }
  close() {
    this.open = false;
  }
  reportValidity() {
    return true;
  }
  setSelectionRange(a, b) {
    this.selectionStart = a;
    this.selectionEnd = b;
  }
  setRangeText(text, a, b, mode) {
    this.value = this.value.slice(0, a) + text + this.value.slice(b);
    if (mode === "end")
      this.setSelectionRange(a + text.length, a + text.length);
  }
}
function harness(options = {}) {
  const document = {activeElement:null,body:new Element("body")};
  const elements = new Map(),
    selectors = new Map(),
    all = [];
  for (const match of page.matchAll(/<([\w-]+)([^>]+)>/g)) {
    const attrs = match[2];
    const id = attrs.match(/id="([^"]+)"/);
    if (!id && !attrs.includes("data-")) continue;
    const e = new Element(match[1]); e.document = document;
    all.push(e);
    if (id) elements.set("#" + id[1], e);
    for (const m of attrs.matchAll(/([\w-]+)="([^"]*)"/g)) {
      e.setAttribute(m[1], m[2]);
      if (m[1] === "class") e.className = m[2];
      if (m[1] === "name") selectors.set(`[name="${m[2]}"]`, e);
      if (m[1].startsWith("data-")) e.dataset[m[1].slice(5)] = m[2];
    }
    if (attrs.includes("data-new")) e.dataset.new = "";
    if (attrs.includes("data-templates")) e.dataset.templates = "";
  }
  const el = (s) =>
    selectors.get(s) ||
    elements.get(s) ||
    (elements.set(s, new Element()), elements.get(s));
  el("#toolFilter").value = "all";
  const descendants = () => {
    const output = [];
    const visit = (e) => {
      output.push(e);
      e.children.forEach(visit);
    };
    all.forEach(visit);
    return output;
  };
  const queryAll = (s) =>
    s === ".toggle"
      ? descendants().filter((e) => e.className === "toggle")
      : all.filter((e) =>
          s === "[data-page]"
            ? e.dataset.page
            : s === "[data-nav]"
              ? e.dataset.nav
              : s === "[data-new]"
                ? "new" in e.dataset
                : s === "[data-templates]"
                  ? "templates" in e.dataset
                  : false,
        );
  const calls = [];
  let tools = [],
    fail = null,
    hold = options.hold || null;
  const location = {
    origin: "http://localhost:8000",
    hash: options.hash || "#overview",
    reload() {
      this.reloaded = true;
    },
  };
  const context = vm.createContext({
    document: Object.assign(document, {
      querySelector: el,
      querySelectorAll: queryAll,
      createElement: (tag) => { const e = new Element(tag); e.document = document; return e; },
      addEventListener() {},
      documentElement: { dataset: {} },
    }),
    location,
    history: {
      pushState(_, __, hash) {
        location.hash = hash;
      },
      replaceState(_, __, hash) {
        location.hash = hash;
      },
    },
    navigator: { onLine: true },
    window: { addEventListener() {}, scrollTo() {}, isSecureContext: false },
    localStorage: {
      getItem() {
        return null;
      },
      setItem() {},
    },
    matchMedia: () => ({ matches: false, addEventListener() {} }),
    URL,
    clearTimeout() {},
    setTimeout() {
      return 1;
    },
    fetch: async (url, options = {}) => {
      calls.push({ url, options });
      if (hold) await hold;
      if (
        fail &&
        fail.url === url &&
        (fail.method || undefined) === options.method
      ) {
        const f = fail;
        fail = null;
        return {
          ok: false,
          status: f.status,
          json: async () => ({ detail: f.detail }),
        };
      }
      const name = decodeURIComponent(url.split("/")[3] || "");
      if (url === "/api/tools" && options.method === "POST") {
        const body = JSON.parse(options.body);
        if (tools.some((t) => t.name === body.name))
          return {
            ok: false,
            status: 409,
            json: async () => ({ detail: "Duplicate name" }),
          };
        const t = asTool(body, "id-" + tools.length);
        tools.push(t);
        return { ok: true, json: async () => ({ id: t.id, revision: "saved-revision" }) };
      }
      if (options.method === "PUT")
        tools = tools.map((t) =>
          t.name === name ? asTool(JSON.parse(options.body), t.id) : t,
        );
      if (options.method === "DELETE")
        tools = tools.filter((t) => t.name !== name);
      if (url.endsWith("/toggle"))
        tools = tools.map((t) =>
          t.name === name ? { ...t, is_active: !t.is_active } : t,
        );
      if (url.endsWith("/run"))
        return {
          ok: true,
          json: async () => ({
            stdout: '{"ok":true}',
            stderr: "",
            exit_code: 0,
            duration_ms: 12,
            timed_out: false,
          }),
        };
      if (url === "/api/config")
        return {
          ok: true,
          json: async () => ({
            mcp_path: "/mcp",
            transport: "limited HTTP JSON-RPC POST",
            auth_enabled: true,
            methods: ["initialize", "tools/list", "tools/call", "ping"],
            auth_configuration: "Configure locally",
          }),
        };
      return { ok: true, json: async () => ({ tools, revision: "saved-revision" }) };
    },
  });
  vm.runInContext(page.split("<script>")[1].split("</script>")[0], context);
  return {
    el,
    calls,
    context,
    run: (code) => vm.runInContext(code, context),
    get tools() {
      return tools;
    },
    set tools(value) {
      tools = value;
    },
    fail(value) {
      fail = value;
    },
    hold(promise) {
      hold = promise;
    },
  };
}
const asTool = (body, id = "saved") => ({
  ...body,
  id,
  requirements_json: JSON.stringify(body.requirements || []),
  json_schema_json: JSON.stringify(body.json_schema || {}),
  is_active: body.is_active ?? true,
});
const settle = () => new Promise((resolve) => setImmediate(resolve));
async function fresh() {
  const h = harness();
  await settle();
  return h;
}
const saved = () =>
  asTool({
    name: "bonusBall",
    description: "keep",
    language: "python3",
    code: "print(21)",
    json_schema: { type: "object", properties: { x: { type: "string" } } },
  });
function select(h, t = saved()) {
  h.tools = [t];
  h.context.selected = t;
  h.run("fillEditor(toolValues(selected),selected)");
  return t;
}
const status = (h) => h.el("#statusText").textContent || "";
const writes = (h) =>
  h.calls.filter((c) => ["POST", "PUT", "DELETE"].includes(c.options.method));
function change(h, key, value) {
  h.el(`[name="${key}"]`).value = value;
  h.run("updateState()");
}
async function confirm(h, pending, approved) {
  await settle();
  h.run(`finishConfirm(${approved})`);
  return pending;
}

test("overview and empty library initialize", async () => {
  const h = await fresh();
  assert.equal(h.run("route"), "overview");
  assert.equal(h.el("#totalCount").textContent, "0");
  assert.equal(h.el("#libraryEmpty").hidden, false);
});
test("new blank tool and cancellation preserve dirty draft", async () => {
  const h = await fresh();
  select(h);
  change(h, "code", "draft");
  await confirm(h, h.run("navigate('tools/new')"), false);
  assert.equal(h.run("current.id"), "saved");
  assert.equal(h.el('[name="code"]').value, "draft");
  await confirm(h, h.run("navigate('tools/new')"), true);
  assert.equal(h.run("current"), null);
  assert.equal(h.el('[name="code"]').value, "");
  assert.equal(h.el("#lineNumbers").textContent, "1");
});
test("exact four templates preserve code and requirements", async () => {
  const h = await fresh();
  const examples = JSON.parse(h.run("JSON.stringify(EXAMPLES)"));
  assert.equal(Object.keys(examples).length, 4);
  for (const [key, e] of Object.entries(examples)) {
    h.run("fillEditor()");
    await h.run(`loadExample('${key}')`);
    assert.equal(h.run("current"), null);
    assert.equal(h.el('[name="code"]').value, e.code);
    assert.equal(
      h.el('[name="requirements"]').value,
      e.requirements.join("\n"),
    );
    assert.equal(
      h.el("#lineNumbers").textContent.split("\n").length,
      e.code.split("\n").length,
    );
  }
});
test("template save creates, never overwrites selected tool", async () => {
  const h = await fresh();
  const t = select(h);
  await h.run("loadExample('python_basic')");
  await h.run("save()");
  assert.equal(writes(h)[0].options.method, "POST");
  assert.equal(t.code, "print(21)");
  assert.equal(h.run("dirty()"), false);
});
test("description edits count as dirty and prevent execution", async () => {
  const h = await fresh();
  select(h);
  change(h, "description", "changed");
  assert.equal(h.run("dirty()"), true);
  assert.equal(h.el("#runBtn").disabled, true);
  await h.run("runSaved()");
  assert.equal(
    h.calls.some((c) => c.url.endsWith("/run")),
    false,
  );
});
test("failed save keeps draft and identity", async () => {
  const h = await fresh();
  select(h);
  change(h, "code", "draft");
  h.fail({
    url: "/api/tools/bonusBall",
    method: "PUT",
    status: 500,
    detail: "Save failed",
  });
  await h.run("save()");
  assert.equal(h.run("current.id"), "saved");
  assert.equal(h.run("dirty()"), true);
  assert.equal(h.el('[name="code"]').value, "draft");
  assert.match(status(h), /Save failed/);
});
test("duplicate name has inline error and keeps draft", async () => {
  const h = await fresh();
  select(h);
  change(h, "name", "taken");
  h.fail({
    url: "/api/tools/bonusBall",
    method: "PUT",
    status: 409,
    detail: "Duplicate",
  });
  await h.run("save()");
  assert.equal(h.el("#nameError").hidden, false);
  assert.equal(h.el('[name="name"]').value, "taken");
  assert.equal(h.run("dirty()"), true);
});
test("successful save followed by failed refresh is still saved", async () => {
  const h = await fresh();
  select(h);
  change(h, "code", "print(22)");
  h.fail({ url: "/api/tools", status: 500, detail: "Refresh failed" });
  await h.run("save()");
  assert.equal(h.run("dirty()"), false);
  assert.equal(h.run("current.code"), "print(22)");
  assert.match(status(h), /saved, but/);
});
test("edits during save survive and remain dirty", async () => {
  const h = await fresh();
  select(h);
  change(h, "code", "submitted");
  let release;
  h.hold(
    new Promise((r) => {
      release = r;
    }),
  );
  const promise = h.run("save()");
  await settle();
  change(h, "code", "newer edit");
  h.hold(null);
  release();
  await promise;
  assert.equal(h.run("current.code"), "submitted");
  assert.equal(h.el('[name="code"]').value, "newer edit");
  assert.equal(h.run("dirty()"), true);
});
test("renames preserve identity, inactive state and input schema", async () => {
  const h = await fresh();
  select(h, { ...saved(), is_active: false });
  change(h, "name", "new");
  await h.run("save()");
  const body = JSON.parse(writes(h)[0].options.body);
  assert.equal(body.is_active, false);
  assert.equal(body.json_schema.properties.x.type, "string");
  assert.equal(h.run("current.id"), "saved");
  assert.equal(h.context.location.hash, "#tools/edit/new");
});
test("list refresh preserves draft, selection and baseline", async () => {
  const h = await fresh();
  select(h);
  change(h, "code", "draft\nsecond");
  h.el('[name="code"]').setSelectionRange(1, 4);
  await h.run("loadTools()");
  assert.equal(h.el('[name="code"]').value, "draft\nsecond");
  assert.equal(h.el('[name="code"]').selectionStart, 1);
  assert.equal(h.run("dirty()"), true);
});
test("toggle preserves draft and save respects toggled state", async () => {
  const h = await fresh();
  select(h);
  await h.run("loadTools()");
  change(h, "code", "draft");
  await h.el("#toolList").children[0].children[2].emit("click");
  assert.equal(h.run("current.is_active"), false);
  assert.equal(h.el('[name="code"]').value, "draft");
  await h.run("save()");
  assert.equal(JSON.parse(writes(h).at(-1).options.body).is_active, false);
});
test("toggle error is recoverable", async () => {
  const h = await fresh();
  select(h);
  await h.run("loadTools()");
  h.fail({
    url: "/api/tools/bonusBall/toggle",
    method: "POST",
    status: 500,
    detail: "Toggle failed",
  });
  await h.el("#toolList").children[0].children[2].emit("click");
  assert.equal(h.run("current.is_active"), true);
  assert.match(status(h), /Toggle failed/);
  assert.equal(h.el("#toolList").children[0].children[2].disabled, false);
});
test("built-in legacy rows are never exposed as editable scripts", async () => {
  const h = await fresh();
  h.tools = [asTool({ name: "omniforge_instructions", code: "legacy" })];
  await h.run("loadTools()");
  assert.equal(h.el("#toolList").children.length, 0);
  select(h, h.tools[0]);
  assert.equal(h.el("#saveBtn").disabled, true);
  await h.run("save()");
  assert.equal(writes(h).length, 0);
});
test("reserved new name is rejected without a request", async () => {
  const h = await fresh();
  change(h, "name", "omniforge_create_tool");
  change(h, "code", "print(1)");
  await h.run("save()");
  assert.equal(h.el("#nameError").hidden, false);
  assert.equal(writes(h).length, 0);
});
test("search and filters show relevant tools", async () => {
  const h = await fresh();
  h.tools = [
    saved(),
    asTool(
      {
        name: "nodeTool",
        description: "numbers",
        language: "node",
        code: "ok",
        is_active: false,
      },
      "node",
    ),
  ];
  await h.run("loadTools()");
  h.el("#toolSearch").value = "numbers";
  h.run("renderTools()");
  assert.equal(h.el("#toolList").children.length, 1);
  h.el("#toolFilter").value = "active";
  h.run("renderTools()");
  assert.equal(h.el("#toolList").children.length, 0);
  assert.equal(h.el("#emptyTitle").textContent, "No tools match your search");
});
test("run uses saved name and renders text not HTML", async () => {
  const h = await fresh();
  select(h);
  await h.run("runSaved()");
  assert.equal(writes(h)[0].url, "/api/tools/bonusBall/run");
  assert.match(h.el("#runSummary").textContent, /Succeeded/);
  h.run('showOutput("<img src=x onerror=bad()>",true)');
  assert.equal(
    h.el("#out").children[0].textContent,
    "<img src=x onerror=bad()>",
  );
  assert.equal(h.el("#out").children[0].children.length, 0);
});
test("run HTTP failure restores buttons", async () => {
  const h = await fresh();
  select(h);
  h.fail({
    url: "/api/tools/bonusBall/run",
    method: "POST",
    status: 500,
    detail: "Run failed",
  });
  await h.run("runSaved()");
  assert.match(h.el("#out").children[0].textContent, /Run failed/);
  assert.equal(h.el("#runBtn").disabled, false);
});
test("gutter, multi-line indentation and keyboard escape", async () => {
  const h = await fresh();
  const e = h.el('[name="code"]');
  e.value = "one\ntwo\nthree";
  h.run("updateGutter()");
  assert.equal(h.el("#lineNumbers").textContent, "1\n2\n3");
  e.setSelectionRange(0, 8);
  const tab = async (shiftKey = false, key = "Tab") => {
    let prevented = false;
    await e.emit("keydown", {
      key,
      shiftKey,
      preventDefault() {
        prevented = true;
      },
    });
    return prevented;
  };
  await tab();
  assert.equal(e.value, "  one\n  two\nthree");
  assert.equal(e.selectionEnd, 12);
  await tab(true);
  assert.equal(e.value, "one\ntwo\nthree");
  await tab(false, "Escape");
  assert.equal(await tab(), false);
  e.scrollTop = 77;
  await e.emit("scroll");
  assert.equal(h.el("#lineNumbers").scrollTop, 77);
});
test("example installation cancel and existing names are safe", async () => {
  const h = await fresh();
  await confirm(h, h.run("installExamples()"), false);
  assert.equal(writes(h).length, 0);
  const examples = JSON.parse(h.run("JSON.stringify(EXAMPLES)"));
  h.tools = [
    asTool({ ...examples.python_basic, code: "custom", is_active: false }),
  ];
  await confirm(h, h.run("installExamples()"), true);
  assert.equal(writes(h).length, 3);
  assert.equal(h.tools[0].code, "custom");
  assert.equal(h.tools[0].is_active, false);
  assert.match(status(h), /3 saved, 1 existing/);
  const count = writes(h).length;
  await confirm(h, h.run("installExamples()"), true);
  assert.equal(writes(h).length, count);
  assert.equal(
    h.calls.some((c) => c.url.endsWith("/run")),
    false,
  );
});
test("partial example failure and concurrent duplicates are reported", async () => {
  const h = await fresh();
  h.fail({
    url: "/api/tools",
    method: "POST",
    status: 500,
    detail: "Example failed",
  });
  await confirm(h, h.run("installExamples()"), true);
  assert.match(status(h), /example_python_basic.*Example failed/);
  h.tools = [];
  h.fail({
    url: "/api/tools",
    method: "POST",
    status: 409,
    detail: "Concurrent duplicate",
  });
  await confirm(h, h.run("installExamples()"), true);
  assert.match(status(h), /3 saved, 1 existing/);
});
test("delete cancellation/error/success do not wipe wrong draft", async () => {
  const h = await fresh();
  select(h);
  await confirm(h, h.run("deleteCurrent()"), false);
  assert.equal(writes(h).length, 0);
  h.fail({
    url: "/api/tools/bonusBall",
    method: "DELETE",
    status: 500,
    detail: "Delete failed",
  });
  await confirm(h, h.run("deleteCurrent()"), true);
  assert.equal(h.run("current.id"), "saved");
  await confirm(h, h.run("deleteCurrent()"), true);
  assert.equal(h.run("current"), null);
  assert.equal(h.run("route"), "tools");
});
test("offline prevents all unsafe actions and preserves draft", async () => {
  const h = await fresh();
  select(h);
  change(h, "code", "offline draft");
  h.context.navigator.onLine = false;
  h.run("updateNetwork()");
  assert.equal(h.el("#saveBtn").disabled, true);
  assert.equal(h.el("#runBtn").disabled, true);
  assert.equal(h.el("#offlineBanner").hidden, false);
  await h.run("save()");
  await h.run("runSaved()");
  assert.equal(writes(h).length, 0);
  assert.equal(h.el('[name="code"]').value, "offline draft");
});
test("connection metadata uses accurate auth template and safe errors", async () => {
  const h = await fresh();
  await h.run("loadConfig()");
  assert.equal(h.el("#endpointValue").value, "http://localhost:8000/mcp");
  assert.match(h.el("#authValue").textContent, /value hidden/);
  assert.match(h.el("#requestTemplate").textContent, /<YOUR_API_KEY>/);
  h.fail({
    url: "/api/config",
    status: 500,
    detail: [{ msg: "Invalid request", input: "sensitive code" }],
  });
  await h.run("loadConfig()");
  assert.match(h.el("#configErrorText").textContent, /Invalid request/);
  assert.doesNotMatch(h.el("#configErrorText").textContent, /sensitive code/);
});
test("deep links and dialog cancellation focus are intentional", async () => {
  const h = await fresh();
  h.tools = [saved()];
  await h.run("loadTools()");
  await h.run("navigate('tools/edit/bonusBall')");
  assert.equal(h.context.location.hash, "#tools/edit/bonusBall");
  assert.equal(h.el("#editorPage").hidden, false);
  assert.equal(h.el('[name="name"]').focused, true);
  const p = h.run('ask("Discard?","Draft")');
  assert.equal(h.el("#cancelConfirm").focused, true);
  await h.el("#confirmDialog").emit("cancel", { preventDefault() {} });
  assert.equal(await p, false);
  assert.equal(h.el("#confirmDialog").open, false);
});


test("startup deferred GET cannot refill a new draft", async () => {
  let release; const deferred = new Promise(r => {release = r;});
  const h = harness({hash:"#tools/new",hold:deferred});
  await settle(); change(h,"code","draft typed during startup");
  h.hold(null); release(); await settle();
  assert.equal(h.el('[name="code"]').value,"draft typed during startup");
  assert.equal(h.run("dirty()"),true);
});
test("navigation during startup fetch preserves the new editor", async () => {
  let release; const h = harness({hold:new Promise(r => {release=r;})});
  await settle(); await h.run("navigate('tools/new')"); change(h,"code","new draft");
  h.hold(null); release(); await settle();
  assert.equal(h.el('[name="code"]').value,"new draft");
});
test("confirmation blocks shortcut saves and all mutations", async () => {
  const h = await fresh(); select(h); change(h,"code","keep");
  const pending = h.run("deleteCurrent()"); await settle();
  assert.equal(h.el("#saveBtn").disabled,true);
  await h.run("save()"); await h.run("runSaved()"); await h.run("installExamples()");
  assert.equal(writes(h).length,0);
  await confirm(h,pending,false);
  assert.equal(h.el('[name="code"]').value,"keep");
});
test("delete captures target before asking and verifies it after approval", async () => {
  const h = await fresh(); select(h); const pending = h.run("deleteCurrent()");
  await settle(); select(h,asTool({name:"different",code:"print(2)"},"different"));
  await confirm(h,pending,true); assert.equal(writes(h).length,0);
});
test("focused toggle survives replacement; filtering away focuses search", async () => {
  const h=await fresh(); select(h); await h.run("loadTools()");
  let toggle=h.el("#toolList").children[0].children[2]; toggle.focus(); await toggle.emit("click");
  toggle=h.el("#toolList").children[0].children[2];
  assert.equal(h.context.document.activeElement,toggle);
  h.el("#toolFilter").value="active"; h.run("renderTools()");
  assert.equal(h.context.document.activeElement,h.el("#toolSearch"));
  h.el("#toolFilter").value="all"; h.el('[name="code"]').focus(); h.run("renderTools()");
  assert.equal(h.context.document.activeElement,h.el('[name="code"]'));
});
test("output remains explicitly previous after draft changes and save", async () => {
  const h=await fresh(); select(h); await h.run("runSaved()");
  change(h,"code","print(99)"); assert.match(h.el("#runSummary").textContent,/Previous version/);
  await h.run("save()"); assert.match(h.el("#runSummary").textContent,/Previous version/);
  await h.run("runSaved()"); assert.doesNotMatch(h.el("#runSummary").textContent,/Previous version/);
});
test("test inputs validate objects, send JSON and revision, remain ephemeral", async () => {
  const h=await fresh(); select(h,{...saved(),revision:"known"});
  for (const value of ["{", "[]", "null", "1", '"text"']) {
    h.el("#testInputs").value=value; await h.run("runSaved()");
    assert.equal(h.el("#testInputsError").hidden,false);
  }
  assert.equal(writes(h).length,0);
  h.el("#testInputs").value='{"x":"hello"}'; await h.run("runSaved()");
  const request=writes(h)[0]; assert.deepEqual(JSON.parse(request.options.body),{arguments:{x:"hello"}});
  assert.equal(request.options.headers["Content-Type"],"application/json");
  assert.equal(request.options.headers["If-Match"],"known");
  assert.equal(h.run("dirty()"),false);
  assert.match(h.el("#savedInputSchema").textContent,/properties/);
  h.el("#testInputs").value='{"x":"later"}'; await h.el("#testInputs").emit("input");
  assert.match(h.el("#runSummary").textContent,/Previous version/);
  h.fail({url:"/api/tools/bonusBall/run",method:"POST",status:422,detail:"Required argument"});
  await h.run("runSaved()"); assert.equal(h.el("#testInputs").value,'{"x":"later"}');
  select(h); assert.equal(h.el("#testInputs").value,"{}");
});
test("412 preserves draft and baseline revision, save adopts returned revision", async () => {
  const h=await fresh(); const original={...saved(),revision:"old"}; select(h,original);
  h.tools=[{...original,revision:"external",code:"external code"}];
  change(h,"code","my draft"); await h.run("loadTools()");
  assert.equal(h.run("current.revision"),"old");
  h.fail({url:"/api/tools/bonusBall",method:"PUT",status:412,detail:"stale"}); await h.run("save()");
  assert.equal(writes(h)[0].options.headers["If-Match"],"old");
  assert.match(status(h),/another tab\/client.*draft retained/);
  assert.equal(h.el('[name="code"]').value,"my draft"); assert.equal(h.el("#nameError").hidden,true);
  await h.run("save()"); assert.equal(h.run("current.revision"),"saved-revision");
});
test("delete and run 412 retain selection without undefined revision headers", async () => {
  const h=await fresh(); select(h,{...saved(),revision:"old"});
  h.fail({url:"/api/tools/bonusBall/run",method:"POST",status:412,detail:"stale"}); await h.run("runSaved()");
  assert.match(h.el("#out").children[0].textContent,/draft retained/);
  h.fail({url:"/api/tools/bonusBall",method:"DELETE",status:412,detail:"stale"});
  await confirm(h,h.run("deleteCurrent()"),true);
  assert.equal(writes(h).at(-1).options.headers["If-Match"],"old"); assert.equal(h.run("current.id"),"saved");
  select(h); await h.run("runSaved()"); assert.equal("If-Match" in writes(h).at(-1).options.headers,false);
});

test('edits during an in-flight run label the completed output previous',async () => {
  const h=await fresh(); select(h); let release;
  h.hold(new Promise(r => {release=r;})); const pending=h.run('runSaved()'); await settle();
  change(h,'code','newer draft'); h.hold(null); release(); await pending;
  assert.match(h.el('#runSummary').textContent,/Previous version.*Succeeded/);
  assert.equal(h.el('[name="code"]').value,'newer draft');
});
test('toggle cannot advance the selected revision and never steals newly moved focus',async () => {
  const h=await fresh(); select(h,{...saved(),revision:'known'}); await h.run('loadTools()');
  let release; h.hold(new Promise(r => {release=r;}));
  const toggle=h.el('#toolList').children[0].children[2]; toggle.focus(); const pending=toggle.emit('click');
  await settle(); h.el('#toolSearch').focus(); h.hold(null); release(); await pending;
  assert.equal(h.run('current.revision'),'known');
  assert.equal(h.context.document.activeElement,h.el('#toolSearch'));
});
