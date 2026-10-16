#!/usr/bin/env node
/** Development-only real-app capture. No mocks, production data or package installs. */
import assert from 'node:assert/strict';
import {spawn, spawnSync} from 'node:child_process';
import {mkdtemp, mkdir, readFile, writeFile, rm} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import path from 'node:path';
import {fileURLToPath, pathToFileURL} from 'node:url';
import {randomUUID, createHash} from 'node:crypto';
import net from 'node:net';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const python = process.env.OMNIFORGE_CAPTURE_PYTHON || path.join(root, '.venv/bin/python');
let playwright;
try { playwright = await import('playwright'); }
catch {
  const fallback = process.env.OMNIFORGE_CAPTURE_PLAYWRIGHT || '/workspace/omniforge/node_modules/playwright/index.mjs';
  playwright = await import(pathToFileURL(path.resolve(fallback)).href);
}
const temp = await mkdtemp(path.join(tmpdir(), 'omniforge-product-'));
const output = path.join(root, 'docs/assets/screenshots');
const token = randomUUID(); // Ephemeral fixture only; never inserted into the DOM or manifest.
const cleanEnv = {
  PATH: `${path.dirname(python)}:${path.dirname(process.execPath)}:/usr/local/bin:/usr/bin:/bin`,
  HOME: temp, TMPDIR: temp, LANG: 'C.UTF-8',
  PYTHONNOUSERSITE: '1', PYTHONDONTWRITEBYTECODE: '1',
  OMNIFORGE_DB_PATH: path.join(temp, 'data/fixture.sqlite'),
  OMNIFORGE_LIB_ROOT: path.join(temp, 'lib'),
  OMNIFORGE_SCRATCH_ROOT: path.join(temp, 'scratch'),
  OMNIFORGE_API_KEY: token,
};
const schema = properties => ({type:'object', properties, required:Object.keys(properties), additionalProperties:false});
const samples = [
  {
    name:'slugify_text', language:'python3', description:'Turn a title into a clean URL slug. Python standard library only.',
    code:`import json, re, sys, unicodedata\n\ndata = json.load(sys.stdin)\ntext = unicodedata.normalize("NFKD", data["text"])\ntext = text.encode("ascii", "ignore").decode().lower()\nslug = re.sub(r"[^a-z0-9]+", "-", text).strip("-")\nprint(json.dumps({"slug": slug}))\n`,
    json_schema:schema({text:{type:'string'}}),
    input:{text:'Build useful tools, simply!'}, expected:{slug:'build-useful-tools-simply'},
  },
  {
    name:'summarize_json', language:'node', description:'List sorted keys and value types in a JSON object. No npm packages.',
    code:`const fs = require("node:fs");\nconst {record} = JSON.parse(fs.readFileSync(0, "utf8"));\nconst keys = Object.keys(record).sort();\nconst types = keys.map(key => ({key, type:\n  record[key] === null ? "null" :\n  Array.isArray(record[key]) ? "array" : typeof record[key]}));\nconsole.log(JSON.stringify({fields: keys.length, types}));\n`,
    json_schema:schema({record:{type:'object'}}),
    input:{record:{title:'Sample report',items:[1,2,3],ready:true}},
    expected:{fields:3,types:[{key:'items',type:'array'},{key:'ready',type:'boolean'},{key:'title',type:'string'}]},
  },
  {
    name:'summarize_csv', language:'python3', description:'Summarize sample CSV quantities and totals using Python csv and decimal. No packages.',
    code:`import csv, io, json, sys\nfrom decimal import Decimal\n\ndata = json.load(sys.stdin)\nreader = csv.DictReader(io.StringIO(data["csv"]))\nif reader.fieldnames != ["item", "quantity", "price"]:\n    print("Example error: CSV needs item,quantity,price headers.", file=sys.stderr)\n    sys.exit(2)\nrows = list(reader)\nquantity = sum(int(row["quantity"]) for row in rows)\ntotal = sum((int(r["quantity"]) * Decimal(r["price"])\n             for r in rows), Decimal("0"))\nprint(json.dumps({"rows": len(rows), "quantity": quantity,\n                  "total": format(total, ".2f")}))\n`,
    json_schema:schema({csv:{type:'string'}}),
    input:{csv:'item,quantity,price\nNotebook,3,4.50\nPencil,6,0.75\nFolder,2,2.00\n'},
    expected:{rows:3,quantity:11,total:'22.00'},
  },
];
let server, browser;
const issues = [], blocked = [], results = [], shots = [], frames = [];
let origin;
async function api(url, body, headers = {}) {
  const response = await fetch(origin + url, {method:body ? 'POST' : 'GET', headers:{'Content-Type':'application/json',...headers}, body:body ? JSON.stringify(body) : undefined});
  assert.equal(response.status, 200, `${url}: HTTP ${response.status}`);
  return response.json();
}
async function stopServer() {
  if (!server || server.exitCode !== null) return;
  await new Promise(resolve => {
    const timer = setTimeout(() => server.kill('SIGKILL'), 3000);
    server.once('exit', () => {clearTimeout(timer);resolve();});
    server.kill('SIGTERM');
  });
}
try {
  await mkdir(output, {recursive:true});
  const port = await new Promise((resolve,reject) => {
    const socket = net.createServer(); socket.on('error',reject);
    socket.listen(0,'127.0.0.1',() => {const p=socket.address().port;socket.close(()=>resolve(p));});
  });
  origin = `http://127.0.0.1:${port}`;
  server = spawn(python, ['-m','uvicorn','app.main:app','--host','127.0.0.1','--port',String(port),'--no-access-log'], {cwd:root,env:cleanEnv,stdio:'ignore'});
  let startupError;
  server.once('error', error => {startupError=error;});
  let ready = false;
  for (let i=0;i<100;i++) {
    if (startupError) throw startupError;
    if (server.exitCode !== null) throw new Error('Temporary app exited before readiness');
    try {const r=await fetch(origin+'/api/config');if(r.ok){ready=true;break;}} catch {}
    await new Promise(resolve=>setTimeout(resolve,100));
  }
  assert.ok(ready,'Temporary app readiness timeout');
  const spec = await api('/openapi.json'); assert.equal(spec.info.version,'0.1.0');
  const config = await api('/api/config'); assert.equal(config.auth_enabled,true);
  assert.ok(!JSON.stringify(config).includes(token));
  const unauthorized = await fetch(origin+'/mcp',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({jsonrpc:'2.0',id:1,method:'ping'})});
  assert.equal(unauthorized.status,401); // Expected authentication check, not a crash.
  for (const sample of samples) {
    const {input,expected,...tool} = sample;
    await api('/api/tools',{...tool,requirements:[],is_active:true});
    const run = await api(`/api/tools/${tool.name}/run`,{arguments:input});
    assert.equal(run.exit_code,0); assert.equal(run.stderr,''); assert.equal(run.timed_out,false);
    assert.deepEqual(JSON.parse(run.stdout),expected);
    results.push({tool:tool.name,arguments:input,stdout:run.stdout,exit_code:run.exit_code});
  }
  assert.equal((await api('/api/tools')).tools.length,3);
  const rpc=await api('/mcp',{jsonrpc:'2.0',id:2,method:'tools/list'},{Authorization:`Bearer ${token}`});
  assert.equal(rpc.result.tools.length,5);
  browser = await playwright.chromium.launch({headless:true,env:{PATH:cleanEnv.PATH,HOME:temp,TMPDIR:temp,LANG:'C.UTF-8'}});
  const context = await browser.newContext({viewport:{width:1440,height:1000},deviceScaleFactor:1,colorScheme:'light',serviceWorkers:'block'});
  await context.route('**/*', async route => {
    if (new URL(route.request().url()).origin !== origin) {blocked.push('external request blocked');await route.abort();}
    else await route.continue();
  });
  const page = await context.newPage();
  page.on('pageerror',error=>issues.push(error.message));
  page.on('response',response=>{if(response.status()>=400)issues.push(`HTTP ${response.status()} ${new URL(response.url()).pathname}`);});
  async function navigate(route) {
    await page.goto(origin+'/#'+route,{waitUntil:'networkidle'});
    await page.evaluate(()=>document.fonts.ready);
    await page.locator('#totalCount').filter({hasText:'3'}).waitFor({state:'attached'});
    // Documentation annotation only, not a claimed product feature.
    await page.evaluate(()=>{
      document.querySelector('#capture-fixture-label')?.remove();
      const badge=document.createElement('div'); badge.id='capture-fixture-label';
      badge.textContent='Example workspace · sample tools';
      Object.assign(badge.style,{position:'fixed',top:'5px',right:'8px',zIndex:'9999',font:'11px sans-serif',background:'#edf2f7',color:'#243248',padding:'3px 7px',borderRadius:'4px',pointerEvents:'none'});
      document.body.append(badge);
    });
  }
  async function privacyCheck() {
    const content=await page.evaluate(()=>document.documentElement.outerHTML+'\n'+Array.from(document.querySelectorAll('input,textarea')).map(e=>e.value).join('\n'));
    assert.ok(!content.includes(token),'Fixture credential leaked into DOM');
    assert.ok(!/192\.168\.|10\.0\.0\.|[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}/i.test(content),'Private address/email in DOM');
  }
  async function capture(file,alt,{fullPage=false,scroll=0}={}) {
    await privacyCheck();
    await page.evaluate(y=>window.scrollTo(0,y),scroll);
    await page.waitForTimeout(100);
    const bytes=await page.screenshot({path:path.join(output,file),fullPage,animations:'disabled'});
    const geometry=await page.evaluate(()=>({viewport:{width:innerWidth,height:innerHeight},scrollY,documentHeight:document.documentElement.scrollHeight}));
    shots.push({file,alt,width:bytes.readUInt32BE(16),height:bytes.readUInt32BE(20),route:new URL(page.url()).hash,theme:await page.locator('#themeSelect').inputValue(),fullPage,...geometry,sha256:createHash('sha256').update(bytes).digest('hex')});
  }
  async function frame() {
    await privacyCheck();
    const file=path.join(temp,`frame-${frames.length}.png`);
    await page.screenshot({path:file,animations:'disabled'});frames.push(file);
  }
  async function runUI(sample,input=sample.input,exit=0) {
    await navigate('tools/edit/'+sample.name);
    assert.equal(await page.locator('#toolCode').inputValue(),sample.code);
    assert.deepEqual(JSON.parse(await page.locator('#savedInputSchema').textContent()),sample.json_schema);
    await page.locator('#testInputs').fill(JSON.stringify(input,null,2));
    const responsePromise=page.waitForResponse(r=>r.url()===origin+`/api/tools/${sample.name}/run` && r.request().method()==='POST');
    await page.locator('#runBtn').click();
    const response=await responsePromise;assert.equal(response.status(),200);
    const result=await response.json();assert.equal(result.exit_code,exit);
    await page.locator('#runSummary').filter({hasText:exit===0?'Succeeded':'Failed'}).waitFor();
    if(exit===0) {
      assert.deepEqual(JSON.parse(result.stdout),sample.expected);
      assert.deepEqual(JSON.parse(await page.locator('#out pre').innerText()),sample.expected);
    }
    else {assert.equal(result.stderr,'Example error: CSV needs item,quantity,price headers.');assert.equal(result.stdout,'');assert.match(await page.locator('#out').innerText(),/Example error: CSV needs item,quantity,price headers/);}
    results.push({via:'UI Run / Test',tool:sample.name,arguments:input,stdout:result.stdout,stderr:result.stderr,exit_code:result.exit_code});
  }
  await navigate('overview'); await page.locator('#themeSelect').selectOption('light');
  await capture('overview-desktop.png','Real OmniForge 0.1.0 overview: three saved, enabled sample tools and two built-in helpers.');await frame();
  await page.locator('#themeSelect').selectOption('dark');
  await capture('overview-dark-desktop.png','The same isolated example workspace in the dark theme.');
  await page.locator('#themeSelect').selectOption('light');await navigate('tools');
  await capture('tools-desktop.png','Actual library of Python slug, Node JSON and Python CSV sample tools; no installed packages.');
  await page.locator('#toolSearch').fill('summarize');await frame();
  await runUI(samples[1]);
  await page.locator('#saveBtn').click();await page.locator('#saveState').filter({hasText:'saved'}).waitFor();
  await page.locator('#testInputs').scrollIntoViewIfNeeded();await frame();
  await runUI(samples[2]);
  await capture('studio-desktop.png','Saved Python CSV tool, standard-library source, JSON inputs and real stdout: three rows, quantity eleven, total 22.00.',{fullPage:true});
  await page.locator('.output').scrollIntoViewIfNeeded();await frame();
  await runUI(samples[2],{csv:'invalid example'},2);
  await capture('studio-error-desktop.png','Controlled schema-valid CSV input runs the saved Python script: actual exit code 2 and safe explanatory stderr.',{fullPage:true});
  await navigate('connect');await page.locator('#configContent').waitFor();
  assert.match(await page.locator('#requestTemplate').innerText(),/YOUR_API_KEY/);
  await capture('connect-desktop.png','Real Connect screen with fixture auth enabled, loopback endpoint and safe Authorization placeholder; no token displayed.',{fullPage:true});await frame();
  await navigate('help');await capture('help-desktop.png','Actual Help page with first-tool guidance, templates and security limitations.');
  await page.setViewportSize({width:375,height:900});
  await navigate('overview');await capture('overview-mobile.png','Actual overview at 375 by 900 CSS pixels with mobile navigation.');
  await navigate('tools');await capture('tools-mobile.png','Three real saved standard-library sample tools in the phone library at 375 by 900.');
  await runUI(samples[1]);await capture('studio-mobile.png','Saved Node JSON tool on a 375 by 900 viewport, with schema-valid JSON and genuine successful subprocess output.',{fullPage:true});
  assert.deepEqual(issues,[],'Browser runtime or HTTP errors');assert.deepEqual(blocked,[],'Unexpected external browser requests');
  const gif=path.join(temp,'demo.gif');
  const pillow=spawnSync(python,['-c',`from PIL import Image\nimport sys\nframes = [Image.open(p).convert("RGB") for p in sys.argv[2:]]\nframes = [im.resize((900, 625)) for im in frames]\nframes[0].save(sys.argv[1], save_all=True, append_images=frames[1:], duration=[1600]*len(frames), loop=0, optimize=False)`,gif,...frames],{env:cleanEnv,cwd:temp,encoding:'utf8'});
  const gifRefreshed=pillow.status===0;
  if(gifRefreshed) await writeFile(path.join(root,'docs/assets/demo.gif'),await readFile(gif));
  const git = args => {const p=spawnSync('git',args,{cwd:root,encoding:'utf8'});assert.equal(p.status,0);return p.stdout.trim();};
  const appFiles=['app/main.py','app/tool_authoring.py','app/templates/dashboard.html','app/runner.py','app/static/product.css'];
  const snapshotFields={};for(const f of appFiles)snapshotFields[f]=createHash('sha256').update(await readFile(path.join(root,f))).digest('hex');
  const manifest={formatVersion:2,provenance:{capturedAt:new Date().toISOString(),sourceCommit:git(['rev-parse','HEAD']),baseRevision:git(['rev-parse','4ae443d']),appVersion:spec.info.version,snapshotFields,source:'Actual worktree app via loopback uvicorn; no mocked API or fabricated output',annotation:'Example workspace · sample tools is a capture-only DOM badge, not product UI',data:'Temporary SQLite, library and scratch; three fixed baked-in examples, two actual built-in helpers',desktop:{width:1440,height:1000},mobile:{width:375,height:900},deviceScaleFactor:1,externalBrowserRequests:blocked.length,browserErrors:issues,expectedUnauthenticatedMcpStatus:401,gifSha256:createHash('sha256').update(await readFile(path.join(root,'docs/assets/demo.gif'))).digest('hex'),gif:gifRefreshed?'Refreshed from actual browser frames':'Historical GIF preserved; Pillow unavailable; NOT a new capture'},runs:results,screenshots:shots};
  await writeFile(path.join(output,'manifest.json'),JSON.stringify(manifest,null,2)+'\n');
  const table=shots.map(s=>`| ${s.file} | ${s.fullPage?'Full page':'Viewport'} | ${s.alt} |`).join('\n');
  await writeFile(path.join(root,'docs/media/SCREENSHOTS.md'),`# Actual product screenshots\n\nGenerated by \`scripts/capture-product.mjs\` from the real worktree app, version ${spec.info.version}. Base application revision: \`4ae443d\`. Exact source commit, file hashes, inputs, stdout, stderr, exit codes, image hashes and viewport metadata are in \`docs/assets/screenshots/manifest.json\`. No product files are changed.\n\n## Reproduce\n\nFrom the repository root, with existing dependencies and Chromium installed (the script installs nothing):\n\n\`\`\`sh\nnode scripts/capture-product.mjs\n\`\`\`\n\nDefaults: Python at \`.venv/bin/python\`, local Playwright import, then the existing workspace Playwright at \`/workspace/omniforge/node_modules/playwright/index.mjs\`. For this docs worktree, use:\n\n\`\`\`sh\nOMNIFORGE_CAPTURE_PYTHON=/workspace/omniforge/.venv/bin/python \\\nOMNIFORGE_CAPTURE_PLAYWRIGHT=/workspace/omniforge/node_modules/playwright/index.mjs \\\nnode scripts/capture-product.mjs\n\`\`\`\n\nBoth overrides can point to equivalent existing local installations elsewhere. No dependency installs, external data calls, production databases or credentials are used. Python and Node examples execute as real app subprocesses with temporary SQLite, library, home and scratch directories and an explicit environment allowlist; inherited secrets are excluded. The temporary server binds only to loopback. Browser requests outside its origin are blocked and asserted to be zero. Browser and server close and temporary data is removed in finally.\n\n## Capture contract\n\nDesktop viewport is 1440 × 1000; phone is 375 × 900, DPR 1. Studio captures include the full page so saved source, JSON inputs and actual stdout/stderr remain inspectable; Connect is also full page. Other screenshots are viewport captures. The visible **Example workspace · sample tools** badge is a capture-only annotation, not a product feature. There are exactly three saved tools and the app's actual two built-in helpers, not fabricated library metrics.\n\nSchemas are seeded through the real API's \`json_schema\` field; the studio shows them read-only. Every example is verified through the real execution API; screenshots of results use the actual **Run / Test** button. The error example is valid against its schema but has incorrect CSV headers, so the script itself prints the safe error and exits 2. MCP authentication is enabled with an ephemeral dummy fixture credential that is never placed in the DOM. The expected unauthenticated MCP POST 401 is tested outside the browser; readiness uses the real config API, not a nonexistent health endpoint.\n\n| File | Extent | Alt / content |\n| --- | --- | --- |\n${table}\n\n## Demo and consumers\n\n${gifRefreshed?'The GIF is refreshed from real browser frames: overview, filtered library, saved Node studio, genuine CSV stdout, and Connect. Pillow was already available; no package install was performed.':'The existing GIF is historical and was preserved unchanged because the optional Pillow encoder was unavailable. It must not be represented as a refreshed capture.'}\n\nExisting screenshot paths are preserved. README and landing-page markup are outside this change: their historical static dimensions and pinned-package wording are not authoritative for these new no-package captures. Use this manifest for current dimensions and alt descriptions. The GIF is a sampled walkthrough, not a continuous screen recording. Sample source and data are development fixtures baked into the capture script, never production tools.\n`);
  console.log(JSON.stringify({screenshots:shots.length,verifiedRuns:results.length,externalBrowserRequests:blocked.length,browserErrors:issues.length,gifRefreshed,sourceCommit:manifest.provenance.sourceCommit}));
} finally {
  try { if(browser) await browser.close(); }
  finally { try { await stopServer(); } finally { await rm(temp,{recursive:true,force:true}); } }
}
