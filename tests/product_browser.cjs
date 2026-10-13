/* Run with local Playwright + axe-core installed; starts an isolated temporary DB.
   Never point this suite at a live server. See docs/product-design.md. */
const { test, before, after } = require("node:test");
const assert = require("node:assert/strict");
const { chromium } = require("playwright");
const AxeBuilder = require("@axe-core/playwright").default;
const { spawn } = require("node:child_process");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const net = require("node:net");
const root = path.resolve(__dirname, "..");
const screenshots =
  process.env.OMNIFORGE_SCREENSHOTS ||
  path.join(os.tmpdir(), "omniforge-product-screenshots");
let browser, server, base, temp;
const errors = [];
before(async () => {
  temp = fs.mkdtempSync(path.join(os.tmpdir(), "omniforge-product-test-"));
  fs.mkdirSync(screenshots, { recursive: true });
  const probe = net.createServer();
  await new Promise((r) => probe.listen(0, "127.0.0.1", r));
  const port = probe.address().port;
  await new Promise((r) => probe.close(r));
  base = `http://127.0.0.1:${port}`;
  server = spawn(
    process.env.OMNIFORGE_TEST_PYTHON || path.join(root, ".venv/bin/python"),
    [
      "-m",
      "uvicorn",
      "app.main:app",
      "--host",
      "127.0.0.1",
      "--port",
      String(port),
    ],
    {
      cwd: root,
      env: {
        ...process.env,
        OMNIFORGE_DB_PATH: path.join(temp, "test.db"),
        OMNIFORGE_LIB_ROOT: path.join(temp, "lib"),
        OMNIFORGE_SCRATCH_ROOT: path.join(temp, "runs"),
        OMNIFORGE_API_KEY: "",
      },
      stdio: "ignore",
    },
  );
  let ready = false;
  for (let n = 0; n < 100; n++) {
    try {
      if ((await fetch(base + "/api/config")).ok) {
        ready = true;
        break;
      }
    } catch {}
    await new Promise((r) => setTimeout(r, 100));
  }
  assert.ok(ready, "test server starts");
  browser = await chromium.launch({ headless: true });
});
after(async () => {
  if (browser) await browser.close();
  if (server) server.kill();
  if (temp) fs.rmSync(temp, { recursive: true, force: true });
  console.log("Screenshots:", screenshots);
  assert.deepEqual(errors, [], "No uncaught browser errors");
});
async function newPage(options = {}) {
  const context = await browser.newContext(options);
  const page = await context.newPage();
  page.on("pageerror", (e) => errors.push(e.message));
  await page.goto(base);
  await page
    .locator("#connectionState")
    .filter({ hasText: "Workspace online" })
    .waitFor();
  await page.evaluate(() => document.fonts.ready);
  return { page, context };
}
async function route(page, target) {
  await page.locator(`[data-nav="${target}"]`).click();
  await page.locator(`[data-page="${target}"]`).waitFor({ state: "visible" });
}
async function noOverflow(page) {
  assert.ok(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
    "no horizontal page overflow",
  );
}
async function audit(page) {
  const result = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"])
    .analyze();
  assert.deepEqual(
    result.violations.map((v) => ({
      id: v.id,
      nodes: v.nodes.map((n) => n.target),
    })),
    [],
    "axe WCAG A/AA checks",
  );
}
async function safeClose(context) {
  await context.close();
}
for (const width of [375, 768, 1440])
  for (const theme of ["light", "dark"])
    test(`layout, navigation, accessibility ${width}px ${theme}`, async () => {
      const { page, context } = await newPage({
        viewport: { width, height: 900 },
        colorScheme: theme,
        reducedMotion: "reduce",
      });
      for (const screen of ["overview", "tools", "connect", "help"]) {
        await route(page, screen);
        if (screen === "connect")
          await page.locator("#configContent").waitFor({ state: "visible" });
        await noOverflow(page);
        await audit(page);
        await page.screenshot({
          path: path.join(screenshots, `${screen}-${width}-${theme}.png`),
          fullPage: true,
        });
      }
      await route(page, "tools");
      await page.locator("#newBtn").click();
      await page.locator("#editorPage").waitFor({ state: "visible" });
      await page.locator("#toolName").fill("screenshot_example");
      await page
        .locator("#toolDescription")
        .fill("Return a predictable greeting as JSON.");
      await page
        .locator("#toolCode")
        .fill(
          'import json\n\nprint(json.dumps({"message": "Hello from OmniForge", "ok": True}))\n',
        );
      await noOverflow(page);
      await audit(page);
      await page.screenshot({
        path: path.join(screenshots, `editor-${width}-${theme}.png`),
        fullPage: true,
      });
      await safeClose(context);
    });
test("first tool template → save → run → toggle → search → delete", async () => {
  const { page, context } = await newPage();
  await page.locator("#overviewPage [data-templates]").click();
  await page.locator('#templateDialog [data-example="python_basic"]').click();
  await page.locator("#toolName").fill("browser_greeting");
  await page.locator("#saveBtn").click();
  await page.waitForFunction(
    () =>
      document.querySelector("#saveState").textContent.includes("saved") &&
      !document.querySelector("#runBtn").disabled,
  );
  assert.match(page.url(), /#tools\/edit\/browser_greeting$/);
  await page.locator("#runBtn").click();
  await page.locator("#runSummary").filter({ hasText: "Succeeded" }).waitFor();
  assert.match(await page.locator("#out").innerText(), /"ok": true/);
  await route(page, "tools");
  await page
    .locator(".tool-row")
    .filter({ hasText: "browser_greeting" })
    .getByRole("switch")
    .click();
  await page.getByRole("switch", { name: "Enable browser_greeting" }).waitFor();
  await page.locator("#toolSearch").fill("browser_greeting");
  assert.equal(await page.locator(".tool-row").count(), 1);
  await page.locator(".tool-open").click();
  await page.locator("#delBtn").click();
  await page.locator("#cancelConfirm").click();
  assert.ok(await page.locator("#editorPage").isVisible());
  await page.locator("#delBtn").click();
  await page.locator("#acceptConfirm").click();
  await page.locator("#toolsPage").waitFor({ state: "visible" });
  assert.equal(
    (await (await fetch(base + "/api/tools")).json()).tools.length,
    0,
  );
  await safeClose(context);
});
test("dirty route and browser back guards, native dialog focus", async () => {
  const { page, context } = await newPage();
  await route(page, "tools");
  await page.locator("#newBtn").click();
  await page.locator("#toolName").fill("unsaved");
  await page.locator("#toolCode").fill("print(1)");
  await page.locator('[data-nav="connect"]').click();
  await page.locator("#confirmDialog").waitFor({ state: "visible" });
  assert.equal(
    await page.evaluate(() => document.activeElement.id),
    "cancelConfirm",
  );
  await page.keyboard.press("Escape");
  assert.equal(await page.locator("#toolName").inputValue(), "unsaved");
  assert.match(page.url(), /#tools\/new$/);
  await page.goBack();
  await page.locator("#confirmDialog").waitFor({ state: "visible" });
  await page.locator("#cancelConfirm").click();
  assert.match(page.url(), /#tools\/new$/);
  assert.equal(await page.locator("#toolCode").inputValue(), "print(1)");
  await page.locator('[data-nav="help"]').click();
  await page.locator("#acceptConfirm").click();
  await page.locator("#helpPage").waitFor({ state: "visible" });
  await safeClose(context);
});
test("keyboard indentation, save shortcut and Escape Tab exit", async () => {
  const { page, context } = await newPage();
  await route(page, "tools");
  await page.locator("#newBtn").click();
  await page.locator("#toolName").fill("keyboard_tool");
  await page.locator("#toolCode").fill("print(1)");
  await page.locator("#toolCode").focus();
  await page.keyboard.press("Home");
  await page.keyboard.press("Tab");
  assert.equal(await page.locator("#toolCode").inputValue(), "  print(1)");
  await page.keyboard.press("Shift+Tab");
  assert.equal(await page.locator("#toolCode").inputValue(), "print(1)");
  await page.keyboard.press("Escape");
  await page.keyboard.press("Tab");
  assert.notEqual(
    await page.evaluate(() => document.activeElement.id),
    "toolCode",
  );
  await page.keyboard.press("Control+s");
  await page.locator("#runBtn").waitFor({ state: "visible" });
  await page.waitForFunction(() => !document.querySelector("#runBtn").disabled);
  await safeClose(context);
});
test("API failure and duplicate names preserve input and recover", async () => {
  const { page, context } = await newPage();
  await route(page, "tools");
  await page.locator("#newBtn").click();
  await page.locator("#toolName").fill("keyboard_tool");
  await page.locator("#toolCode").fill('print("draft")');
  await page.locator("#saveBtn").click();
  await page.locator("#nameError").waitFor({ state: "visible" });
  assert.equal(await page.locator("#toolCode").inputValue(), 'print("draft")');
  await page.locator("#toolName").fill("error_tool");
  await page.route("**/api/tools", async (r) => {
    if (r.request().method() === "POST")
      await r.fulfill({
        status: 500,
        contentType: "application/json",
        body: JSON.stringify({
          detail: [
            { msg: "Save unavailable", input: "PRIVATE_SUBMITTED_VALUE" },
          ],
        }),
      });
    else await r.continue();
  });
  await page.locator("#saveBtn").click();
  await page
    .locator("#statusText")
    .filter({ hasText: "Save unavailable" })
    .waitFor();
  assert.doesNotMatch(
    await page.locator("#statusText").innerText(),
    /PRIVATE_SUBMITTED/,
  );
  assert.equal(await page.locator("#toolCode").inputValue(), 'print("draft")');
  await page.unroute("**/api/tools");
  await page.locator("#saveBtn").click();
  await page.waitForFunction(() => !document.querySelector("#runBtn").disabled);
  await safeClose(context);
});
test("online-only actions, actual offline navigation, no dynamic cache entries", async () => {
  const { page, context } = await newPage();
  await page.evaluate(async () => {
    await navigator.serviceWorker.ready;
  });
  await page.waitForFunction(() => !!navigator.serviceWorker.controller);
  await route(page, "tools");
  await page.locator("#newBtn").click();
  await page.locator("#toolCode").fill("offline draft");
  await context.setOffline(true);
  await page.locator("#offlineBanner").waitFor({ state: "visible" });
  assert.ok(await page.locator("#saveBtn").isDisabled());
  assert.ok(await page.locator("#runBtn").isDisabled());
  assert.equal(await page.locator("#toolCode").inputValue(), "offline draft");
  const cached = await page.evaluate(async () => {
    const result = [];
    for (const name of await caches.keys()) {
      const cache = await caches.open(name);
      for (const req of await cache.keys())
        result.push(new URL(req.url).pathname);
    }
    return result;
  });
  assert.equal(cached.length, 12);
  assert.ok(cached.every((p) => p.startsWith("/assets/")));
  assert.ok(
    !cached.some(
      (p) => p.startsWith("/api") || p.startsWith("/mcp") || p === "/",
    ),
  );
  // Explicitly leave synthetic draft, then verify fallback after a real navigation failure.
  await page.evaluate(() => {
    fillEditor();
  });
  await page.reload();
  await page
    .getByRole("heading", { name: "Your workspace is online." })
    .waitFor();
  assert.equal(await page.locator("#toolCode").count(), 0);
  assert.match(await page.locator("body").innerText(), /never cached/);
  await context.setOffline(false);
  await safeClose(context);
});
test("system theme tracks browser changes, mobile landscape and large text", async () => {
  const { page, context } = await newPage({
    viewport: { width: 768, height: 375 },
    colorScheme: "light",
    reducedMotion: "reduce",
  });
  await page.locator("#themeSelect").selectOption("system");
  await page.emulateMedia({ colorScheme: "dark" });
  await page.waitForFunction(
    () => document.documentElement.dataset.theme === "dark",
  );
  assert.equal(
    await page.evaluate(() => document.documentElement.dataset.theme),
    "dark",
  );
  await page.addStyleTag({
    content: "html{font-size:125%}body{font-size:20px}",
  });
  await route(page, "help");
  await noOverflow(page);
  await page.screenshot({
    path: path.join(screenshots, "landscape-large-text-dark.png"),
    fullPage: true,
  });
  await safeClose(context);
});
test("install eligibility and update affordance never force-discard drafts", async () => {
  const { page, context } = await newPage();
  assert.equal(await page.locator("#installBtn").isVisible(), false);
  await page.evaluate(() => {
    const e = new Event("beforeinstallprompt", { cancelable: true });
    e.prompt = async () => {};
    e.userChoice = Promise.resolve({ outcome: "dismissed" });
    window.dispatchEvent(e);
  });
  assert.equal(await page.locator("#installBtn").isVisible(), true);
  await page.locator("#installBtn").click();
  assert.equal(await page.locator("#installBtn").isVisible(), false);
  await route(page, "tools");
  await page.locator("#newBtn").click();
  await page.locator("#toolCode").fill("keep this draft");
  await page.evaluate(() => {
    waitingWorker = {
      postMessage() {
        window.syntheticUpdateAccepted = true;
      },
    };
    document.querySelector("#updateBtn").hidden = false;
  });
  await page.locator("#updateBtn").click();
  await page.locator("#confirmDialog").waitFor({ state: "visible" });
  await page.locator("#cancelConfirm").click();
  assert.equal(await page.locator("#toolCode").inputValue(), "keep this draft");
  assert.equal(
    await page.evaluate(() => window.syntheticUpdateAccepted),
    undefined,
  );
  await safeClose(context);
});
test("add all examples skips existing names without execution", async () => {
  const { page, context } = await newPage();
  await route(page, "help");
  const runs = [];
  page.on("request", (r) => {
    if (r.url().endsWith("/run")) runs.push(r.url());
  });
  await page.locator("#installExamplesBtn").click();
  await page.locator("#acceptConfirm").click();
  await page
    .locator("#statusText")
    .filter({ hasText: "4 saved, 0 existing names skipped" })
    .waitFor();
  await page.locator("#installExamplesBtn").click();
  await page.locator("#acceptConfirm").click();
  await page
    .locator("#statusText")
    .filter({ hasText: "0 saved, 4 existing names skipped" })
    .waitFor();
  assert.deepEqual(runs, []);
  await safeClose(context);
});
test("populated tool library remains usable and accessible across six layouts", async () => {
  for (const width of [375, 768, 1440])
    for (const theme of ["light", "dark"]) {
      const { page, context } = await newPage({
        viewport: { width, height: 900 },
        colorScheme: theme,
      });
      await route(page, "tools");
      assert.ok((await page.locator(".tool-row").count()) >= 4);
      await noOverflow(page);
      await audit(page);
      await page.screenshot({
        path: path.join(screenshots, `library-populated-${width}-${theme}.png`),
        fullPage: true,
      });
      await safeClose(context);
    }
});

// Mock API fixtures isolate these UI regressions from concurrent backend work.
async function reviewFixture() {
  const session = await newPage(); const {page} = session;
  const tool = {id:'review-fixture',name:'review_fixture',description:'Review fixture',language:'python3',
    code:'print(1)',requirements_json:'[]',json_schema_json:JSON.stringify({type:'object',properties:{x:{type:'string'}},required:['x']}),is_active:true,revision:'review-v1'};
  const requests=[];
  await page.route('**/api/tools**', async r => {
    const request=r.request(), url=new URL(request.url());
    if (url.pathname==='/api/tools' && request.method()==='GET') {
      await r.fulfill({json:{tools:[tool]}}); return;
    }
    requests.push(request);
    if (url.pathname.endsWith('/toggle')) { tool.is_active=!tool.is_active; tool.revision='review-toggle'; }
    if (request.method()==='PUT') {
      const body=request.postDataJSON(); Object.assign(tool,body,{revision:'review-v2'});
      tool.requirements_json=JSON.stringify(body.requirements); tool.json_schema_json=JSON.stringify(body.json_schema);
    }
    await r.fulfill({json:url.pathname.endsWith('/run') ? {stdout:'{"ok":true}',stderr:'',exit_code:0,duration_ms:1,timed_out:false} : {revision:tool.revision}});
  });
  await page.evaluate(() => loadTools()); await route(page,'tools'); await page.locator('.tool-open').click();
  await page.locator('#editorPage').waitFor({state:'visible'});
  return {...session,tool,requests};
}
test('deferred startup GET preserves draft typed on initial new route', async () => {
  const context=await browser.newContext(); const page=await context.newPage();
  page.on('pageerror',e => errors.push(e.message));
  let release; const held=new Promise(r => {release=r;});
  await page.route('**/api/tools',async r => {await held; await r.fulfill({json:{tools:[]}});});
  await page.goto(base+'/#tools/new',{waitUntil:'domcontentloaded'});
  await page.locator('#toolCode').fill('startup draft'); release();
  await page.locator('#connectionState').filter({hasText:'Workspace online'}).waitFor();
  assert.equal(await page.locator('#toolCode').inputValue(),'startup draft');
  await safeClose(context);
});
test('delete dialog blocks save shortcut and retains snapshotted target', async () => {
  const {page,context,requests}=await reviewFixture();
  await page.locator('#toolCode').fill('print(2)'); await page.locator('#delBtn').click();
  await page.keyboard.press('Control+s'); await page.evaluate(() => save());
  assert.equal(requests.length,0); assert.ok(await page.locator('#saveBtn').isDisabled());
  await page.locator('#cancelConfirm').click();
  assert.equal(await page.locator('#toolCode').inputValue(),'print(2)');
  await safeClose(context);
});
test('toggle keeps switch focus; filtered-away switch lands on search', async () => {
  const {page,context}=await reviewFixture(); await route(page,'tools');
  await page.getByRole('switch').focus(); await page.keyboard.press('Space');
  await page.getByRole('switch',{name:'Enable review_fixture'}).waitFor();
  await page.waitForFunction(() => document.activeElement.getAttribute('role')==='switch' && !document.activeElement.disabled);
  await page.evaluate(() => {document.querySelector('#toolFilter').value='active'; renderTools();});
  assert.equal(await page.evaluate(() => document.activeElement.id),'toolSearch');
  await safeClose(context);
});
test('test JSON is validated inline, transmitted, and previous output is attributed', async () => {
  const {page,context,requests}=await reviewFixture();
  await page.locator('#advancedSettings summary').click();
  assert.match(await page.locator('#savedInputSchema').innerText(),/required/);
  for (const invalid of ['{','[]','null','"scalar"']) {
    await page.locator('#testInputs').fill(invalid); await page.locator('#runBtn').click();
    assert.ok(await page.locator('#testInputsError').isVisible());
  }
  assert.equal(requests.length,0);
  await page.locator('#testInputs').fill('{"x":"hello"}'); await page.locator('#runBtn').click();
  await page.locator('#runSummary').filter({hasText:'Succeeded'}).waitFor();
  const run=requests.find(r => r.url().endsWith('/run'));
  assert.deepEqual(run.postDataJSON(),{arguments:{x:'hello'}});
  assert.equal(run.headers()['if-match'],'review-v1');
  assert.match(run.headers()['content-type'],/application\/json/);
  await page.locator('#toolCode').fill('print(3)');
  assert.match(await page.locator('#runSummary').innerText(),/Previous version/);
  await page.locator('#saveBtn').click(); await page.waitForFunction(() => !document.querySelector('#runBtn').disabled);
  assert.match(await page.locator('#runSummary').innerText(),/Previous version/);
  assert.equal(await page.locator('#testInputs').inputValue(),'{"x":"hello"}');
  await page.locator('#testInputs').fill('{"x":"different"}');
  assert.match(await page.locator('#runSummary').innerText(),/Previous version/);
  await safeClose(context);
});
test('revision 412 preserves draft, input, identity and actionable recovery', async () => {
  const {page,context}=await reviewFixture();
  await page.locator('#toolCode').fill('my retained draft'); await page.locator('#testInputs').fill('{"x":"retained"}');
  let revision;
  await page.route('**/api/tools/review_fixture',async r => {
    revision=r.request().headers()['if-match'];
    await r.fulfill({status:412,json:{detail:'Changed elsewhere'}});
  });
  await page.locator('#saveBtn').click(); await page.locator('#statusText').filter({hasText:'draft retained'}).waitFor();
  assert.equal(revision,'review-v1'); assert.equal(await page.locator('#toolCode').inputValue(),'my retained draft');
  assert.equal(await page.locator('#testInputs').inputValue(),'{"x":"retained"}');
  assert.equal(await page.locator('#nameError').isVisible(),false);
  assert.match(await page.locator('#statusText').innerText(),/copy your draft first/);
  assert.match(page.url(),/#tools\/edit\/review_fixture$/);
  await safeClose(context);
});
test('landscape rail scrolls and simultaneous mobile install/update controls wrap', async () => {
  const {page,context}=await newPage({viewport:{width:768,height:375}});
  assert.equal(await page.locator('.rail').evaluate(el => getComputedStyle(el).overflowY),'auto');
  await page.locator('#themeSelect').scrollIntoViewIfNeeded();
  assert.ok(await page.locator('#themeSelect').isVisible());
  await page.setViewportSize({width:375,height:667});
  await page.evaluate(() => {document.querySelector('#installBtn').hidden=false;document.querySelector('#updateBtn').hidden=false;});
  await noOverflow(page);
  assert.equal(await page.locator('.top-actions').evaluate(el => getComputedStyle(el).flexWrap),'wrap');
  await safeClose(context);
});
