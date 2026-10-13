const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const page = fs.readFileSync('app/templates/dashboard.html', 'utf8');
const script = page.split('<script>')[1].split('</script>')[0];
class Element {
  constructor() {
    this.value = ''; this.style = {}; this.dataset = {}; this.children = []; this.handlers = {};
    this.classes = new Set();
    this.classList = { remove: c => this.classes.delete(c), toggle: (c, on) => on ? this.classes.add(c) : this.classes.delete(c) };
  }
  addEventListener(event, handler) { this.handlers[event] = handler; }
  replaceChildren(...items) { this.children = items; }
  append(...items) { this.children.push(...items); }
  appendChild(item) { this.children.push(item); }
  focus() { this.focused = true; }
}
const elements = new Map();
const element = selector => { if (!elements.has(selector)) elements.set(selector, new Element()); return elements.get(selector); };
const fields = ['name', 'description', 'language', 'code', 'requirements'];
element('#toolForm').reset = () => fields.forEach(f => { element(`[name="${f}"]`).value = f === 'language' ? 'python3' : ''; });
let approve = true;
const calls = [];
let tools = [];
const context = vm.createContext({
  document: {
    querySelector: element,
    querySelectorAll: () => element('#toolList').children,
    createElement: () => new Element()
  },
  confirm: () => approve,
  fetch: async (url, options = {}) => {
    calls.push({url, options});
    if (url === '/api/tools' && options.method === 'POST') {
      const body = JSON.parse(options.body);
      tools = [{...body, id: 'new', requirements_json: JSON.stringify(body.requirements), json_schema_json: JSON.stringify(body.json_schema)}];
    }
    return {ok: true, status: 200, text: async () => JSON.stringify(url === '/api/tools' && !options.method ? {tools} : {ok: true})};
  },
  URL, window: {location: {origin: 'http://localhost:8000'}}
});
vm.runInContext(script, context);
(async () => {
  await new Promise(resolve => setImmediate(resolve));
  const saved = {id: 'saved', name: 'bonusBall', description: 'keep', language: 'python3', code: 'print(21)', requirements_json: '[]', json_schema_json: '{}', is_active: true};
  context.saved = saved;
  vm.runInContext('selectTool(saved)', context);
  approve = false;
  element('#newBtn').handlers.click();
  assert.equal(element('[name="name"]').value, 'bonusBall', 'Cancelled reset must preserve editor');
  approve = true;
  element('#newBtn').handlers.click();
  assert.equal(vm.runInContext('current', context), null);
  assert.equal(element('[name="name"]').value, '');
  assert.equal(element('#formTitle').textContent, 'New Tool');
  assert.equal(element('#delBtn').style.display, 'none');
  assert.equal(element('#out').style.display, 'none');
  const examples = JSON.parse(vm.runInContext('JSON.stringify(EXAMPLES)', context));
  assert.equal(Object.keys(examples).length, 4);
  for (const [key, example] of Object.entries(examples)) {
    element('#exampleSelect').value = key;
    element('#exampleBtn').handlers.click();
    assert.equal(vm.runInContext('current', context), null);
    assert.equal(element('[name="language"]').value, example.language);
    assert.equal(element('[name="code"]').value, example.code);
    assert.equal(element('[name="requirements"]').value, example.requirements.join('\n'));
  }
  await element('#toolForm').handlers.submit({preventDefault() {}});
  const write = calls.find(call => call.options.method === 'POST');
  assert.equal(write.url, '/api/tools', 'Saving after New/example must CREATE, not update existing tool');
  assert.equal(calls.some(call => call.options.method === 'PUT'), false);
  assert.equal(saved.code, 'print(21)', 'Existing tool remains unchanged');
  console.log('PASS: New Tool reset/cancel, four template selections, POST creation preserves existing tool');
})().catch(err => { console.error(err); process.exitCode = 1; });
