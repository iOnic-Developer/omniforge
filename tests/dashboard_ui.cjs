const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const page = fs.readFileSync('app/templates/dashboard.html', 'utf8');
const script = page.split('<script>')[1].split('</script>')[0];
class Element {
  constructor() {
    this.value = ''; this.style = {}; this.dataset = {}; this.children = []; this.handlers = {};
    this.attributes = {}; this.scrollTop = 0; this.selectionStart = 0; this.selectionEnd = 0;
    this.classes = new Set();
    this.classList = {
      remove: c => this.classes.delete(c), contains: c => this.classes.has(c),
      toggle: (c, on = !this.classes.has(c)) => on ? this.classes.add(c) : this.classes.delete(c)
    };
  }
  addEventListener(event, handler) { this.handlers[event] = handler; }
  replaceChildren(...items) { this.children = items; }
  append(...items) { this.children.push(...items); }
  appendChild(item) { this.children.push(item); }
  setAttribute(name, value) { this.attributes[name] = String(value); }
  getAttribute(name) { return this.attributes[name] ?? null; }
  focus() { this.focused = true; }
  showModal() { this.open = true; }
  close() { this.open = false; }
  setSelectionRange(start, end) { this.selectionStart = start; this.selectionEnd = end; }
  setRangeText(text, start, end, mode) {
    this.value = this.value.slice(0, start) + text + this.value.slice(end);
    if (mode === 'end') this.setSelectionRange(start + text.length, start + text.length);
  }
}
const elements = new Map();
const element = selector => { if (!elements.has(selector)) elements.set(selector, new Element()); return elements.get(selector); };
const fields = ['name', 'description', 'language', 'code', 'requirements'];
const field = name => element(`[name="${name}"]`);
element('#toolForm').reset = () => fields.forEach(f => { field(f).value = f === 'language' ? 'python3' : ''; });
for (const side of ['Left', 'Right']) element('#collapse' + side).setAttribute('aria-expanded', 'true');
let approve = true, failNext = null;
const calls = [];
let tools = [];
const asTool = (body, id) => ({...body, id, requirements_json: JSON.stringify(body.requirements || []), json_schema_json: JSON.stringify(body.json_schema || {})});
const response = (status, data) => ({ok: status < 400, status, text: async () => JSON.stringify(data)});
const context = vm.createContext({
  document: {
    querySelector: element,
    querySelectorAll: () => element('#toolList').children,
    createElement: () => new Element()
  },
  confirm: () => approve,
  fetch: async (url, options = {}) => {
    calls.push({url, options});
    if (failNext && url === failNext.url && options.method === failNext.method) {
      const error = failNext; failNext = null;
      return response(error.status, {detail: error.detail});
    }
    if (url === '/api/tools' && options.method === 'POST') {
      const body = JSON.parse(options.body);
      if (tools.some(t => t.name === body.name)) return response(409, {detail: 'Duplicate name'});
      tools.push(asTool(body, 'tool-' + tools.length));
    } else if (url.endsWith('/toggle')) {
      const name = decodeURIComponent(url.split('/')[3]);
      tools = tools.map(t => t.name === name ? {...t, is_active: !t.is_active} : t);
    } else if (options.method === 'PUT') {
      const name = decodeURIComponent(url.split('/')[3]);
      tools = tools.map(t => t.name === name ? asTool(JSON.parse(options.body), t.id) : t);
    } else if (options.method === 'DELETE') {
      const name = decodeURIComponent(url.split('/')[3]); tools = tools.filter(t => t.name !== name);
    }
    if (url === '/api/config') return response(200, {
      mcp_path: '/mcp', transport: 'HTTP JSON-RPC POST', auth_enabled: true,
      auth_configuration: 'Set the key locally', methods: ['tools/list', 'tools/call'], warnings: ['Trusted scripts only']
    });
    return response(200, url === '/api/tools' && !options.method ? {tools} : {ok: true});
  },
  URL, window: {location: {origin: 'http://localhost:8000'}}
});
vm.runInContext(script, context);
const run = code => vm.runInContext(code, context);
const click = selector => element(selector).handlers.click();
const output = () => element('#out').children[0]?.textContent || '';
const row = id => element('#toolList').children.find(li => li.dataset.toolId === id);
const writes = () => calls.filter(c => ['POST', 'PUT', 'DELETE'].includes(c.options.method));
const tab = (shiftKey = false, key = 'Tab') => {
  let prevented = false;
  field('code').handlers.keydown({key, shiftKey, preventDefault() { prevented = true; }});
  return prevented;
};
(async () => {
  await new Promise(resolve => setImmediate(resolve));
  const saved = asTool({name: 'bonusBall', description: 'keep', language: 'python3', code: 'print(21)', is_active: true}, 'saved');
  tools = [saved]; context.saved = saved;
  run('selectTool(saved)');
  approve = false;
  click('#newBtn');
  assert.equal(field('name').value, 'bonusBall', 'Cancelled reset preserves editor');
  assert.equal(run('current.id'), 'saved');
  approve = true;
  click('#newBtn');
  assert.equal(run('current'), null);
  assert.equal(field('name').value, '');
  assert.equal(element('#formTitle').textContent, 'New Tool');
  assert.equal(element('#delBtn').style.display, 'none');
  assert.equal(element('#out').style.display, 'none');
  assert.equal(element('#lineNumbers').textContent, '1');
  const examples = JSON.parse(run('JSON.stringify(EXAMPLES)'));
  assert.equal(Object.keys(examples).length, 4);
  for (const [key, example] of Object.entries(examples)) {
    element('#exampleSelect').value = key;
    click('#exampleBtn');
    assert.equal(run('current'), null);
    assert.equal(field('language').value, example.language);
    assert.equal(field('code').value, example.code);
    assert.equal(field('requirements').value, example.requirements.join('\n'));
    assert.equal(element('#lineNumbers').textContent.split('\n').length, example.code.split('\n').length);
  }
  await element('#toolForm').handlers.submit({preventDefault() {}});
  assert.equal(writes()[0].url, '/api/tools', 'New/example creates instead of updating');
  assert.equal(calls.some(call => call.options.method === 'PUT'), false);
  assert.equal(saved.code, 'print(21)', 'Existing tool remains unchanged');
  console.log('PASS: New reset/cancel, four example loads, create-only save and gutter updates');

  // Collapse controls remain usable; collapse and list refresh leave drafts intact.
  run('selectTool(saved)');
  field('code').value = 'draft\nsecond\n';
  field('description').value = 'unsaved description';
  field('code').setSelectionRange(1, 5);
  for (const side of ['Left', 'Right']) {
    click('#collapse' + side);
    assert.equal(element('#collapse' + side).getAttribute('aria-expanded'), 'false');
    assert.equal(element('#' + side.toLowerCase() + 'Panel').classList.contains('collapsed'), true);
    assert.equal(field('code').value, 'draft\nsecond\n');
    click('#collapse' + side);
    assert.equal(element('#collapse' + side).getAttribute('aria-expanded'), 'true');
  }
  await run('loadTools()');
  const toggle = row('saved').children[1];
  assert.equal(toggle.getAttribute('aria-checked'), 'true');
  await toggle.handlers.click();
  assert.equal(run('current.is_active'), false);
  assert.equal(field('code').value, 'draft\nsecond\n');
  assert.equal(field('description').value, 'unsaved description');
  assert.equal(field('code').selectionStart, 1);
  assert.equal(row('saved').classList.contains('active'), true);
  assert.equal(row('saved').children[1].getAttribute('aria-checked'), 'false');
  const toggleCall = calls.find(c => c.url.endsWith('/toggle'));
  assert.equal(toggleCall.url, '/api/tools/bonusBall/toggle');
  assert.equal(toggleCall.options.method, 'POST');
  await element('#toolForm').handlers.submit({preventDefault() {}});
  assert.equal(tools.find(t => t.id === 'saved').is_active, false, 'Saving draft must not undo the toggle');
  failNext = {url: '/api/tools/bonusBall/toggle', method: 'POST', status: 500, detail: 'Toggle failed'};
  await row('saved').children[1].handlers.click();
  assert.match(output(), /Toggle failed/);
  assert.equal(run('current.is_active'), false);
  assert.equal(row('saved').children[1].disabled, false);
  const builtin = asTool({name: 'omniforge_instructions', code: 'legacy', is_active: true}, 'builtin');
  tools.push(builtin); await run('loadTools()');
  const beforeBuiltin = calls.length;
  assert.equal(row('builtin').children[1].disabled, true);
  await row('builtin').children[1].handlers.click();
  assert.equal(calls.length, beforeBuiltin, 'Built-ins must not be toggled');
  tools = tools.filter(t => t.id !== 'builtin');
  console.log('PASS: collapse/expand, toggle/error/built-in guard, selection and draft preservation');

  field('code').value = 'one\ntwo\nthree';
  field('code').handlers.input();
  assert.equal(element('#lineNumbers').textContent, '1\n2\n3');
  field('code').scrollTop = 77; field('code').handlers.scroll();
  assert.equal(element('#lineNumbers').scrollTop, 77);
  field('code').setSelectionRange(0, 8); // ends at the start of line three
  assert.equal(tab(), true);
  assert.equal(field('code').value, '  one\n  two\nthree');
  assert.equal(field('code').selectionStart, 2);
  assert.equal(field('code').selectionEnd, 12);
  tab(true);
  assert.equal(field('code').value, 'one\ntwo\nthree');
  assert.equal(field('code').selectionStart, 0);
  assert.equal(field('code').selectionEnd, 8);
  field('code').setSelectionRange(1, 1); tab();
  assert.equal(field('code').value, 'o  ne\ntwo\nthree');
  assert.equal(field('code').selectionStart, 3);
  field('code').value = '  one'; field('code').setSelectionRange(2, 2); tab(true);
  assert.equal(field('code').value, 'one');
  assert.equal(field('code').selectionStart, 0);
  tab(false, 'Escape'); assert.equal(tab(), false, 'Escape + Tab allows keyboard navigation');
  click('#collapseRight'); field('name').handlers.invalid();
  assert.equal(element('#collapseRight').getAttribute('aria-expanded'), 'true', 'Required field validation opens settings');
  console.log('PASS: gutter input/scroll, caret and selection indent/unindent, keyboard exit, hidden-field validation');

  const existing = asTool({...examples.python_basic, code: 'keep my customized example', is_active: false}, 'existing-example');
  tools = [saved, existing];
  run('selectTool(saved)'); field('code').value = 'do not discard';
  approve = false;
  const beforeCancel = calls.length;
  await click('#installExamplesBtn');
  assert.equal(calls.length, beforeCancel, 'Cancelled installation has no API writes');
  approve = true;
  const beforeInstall = writes().length;
  await click('#installExamplesBtn');
  const installed = writes().slice(beforeInstall);
  assert.equal(installed.length, 3);
  assert.equal(installed.every(c => c.url === '/api/tools' && c.options.method === 'POST'), true);
  assert.equal(tools.find(t => t.id === 'existing-example').code, 'keep my customized example');
  assert.equal(tools.find(t => t.id === 'existing-example').is_active, false);
  assert.equal(field('code').value, 'do not discard');
  assert.equal(run('current.id'), 'saved');
  assert.match(output(), /3 saved, 1 existing names skipped/);
  const beforeRepeat = writes().length;
  await click('#installExamplesBtn');
  assert.equal(writes().length, beforeRepeat, 'Repeat installation skips all existing names');
  assert.match(output(), /0 saved, 4 existing names skipped/);
  tools = [saved];
  failNext = {url: '/api/tools', method: 'POST', status: 500, detail: 'Example save failed'};
  await click('#installExamplesBtn');
  assert.match(output(), /example_python_basic: HTTP 500: Example save failed/);
  assert.equal(element('#out').children[0].className, 'err');
  assert.equal(element('#installExamplesBtn').disabled, false);
  tools = [saved];
  failNext = {url: '/api/tools', method: 'POST', status: 409, detail: 'Concurrent duplicate'};
  await click('#installExamplesBtn');
  assert.match(output(), /3 saved, 1 existing names skipped/);
  assert.equal(element('#out').children[0].className, 'ok');
  assert.equal(calls.some(c => c.url.endsWith('/run')), false, 'Installation never runs scripts or packages');
  console.log('PASS: example install cancel/create/skip/repeat, partial errors, concurrent duplicate, no run');

  click('#helpBtn'); assert.equal(element('#helpDialog').open, true);
  click('#closeHelp'); assert.equal(element('#helpDialog').open, false);
  click('#tipsHelpBtn'); assert.equal(element('#helpDialog').open, true);
  await click('#configBtn');
  assert.equal(element('#configDialog').open, true);
  assert.match(element('#configContent').children[0].textContent, /value hidden/);
  click('#closeConfig'); assert.equal(element('#configDialog').open, false);
  console.log('PASS: help/example and config dialog controls');
})().catch(err => { console.error(err); process.exitCode = 1; });
