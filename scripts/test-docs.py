#!/usr/bin/env python3
"""Dependency-free unittest harness; application dependencies must already exist.

Run with the application's Python from any working directory. Uses TestClient
when httpx is available, otherwise real loopback HTTP through Uvicorn. No
package installation, provider calls, production environment or production DB.
"""
from __future__ import annotations

import importlib.util
import json
import logging
import os
from pathlib import Path
import re
import shutil
import socket
import struct
import subprocess
import sys
import tempfile
import time
import unittest
from html.parser import HTMLParser
from urllib.error import HTTPError, URLError
from urllib.parse import unquote, urlsplit
from urllib.request import ProxyHandler, Request, build_opener

ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = (('slugify', 'slugify.py'), ('summarize-json', 'summarize-json.cjs'))
KEY = 'docs-tests-disposable-key-not-a-credential'
HTTP = None
TEMP = None
ORIGINAL_ENV = None
ENV = None
TRANSPORT = None
LINK_COUNT = 0


def load_json(path):
    return json.loads(path.read_text(encoding='utf-8'))


def fixture(stem):
    directory = ROOT / 'examples'
    return (load_json(directory / (stem + '.tool.json')),
            load_json(directory / (stem + '.input.json')),
            load_json(directory / (stem + '.expected.json')))


class LocalHTTP:
    def __init__(self, env):
        self.process = None
        self.client = None
        if importlib.util.find_spec('httpx') is not None:
            # Environment is already isolated before either application import.
            sys.path.insert(0, str(ROOT))
            from fastapi.testclient import TestClient
            from app.main import app
            self.client = TestClient(app)
            self.client.__enter__()
            self.transport = 'FastAPI TestClient'
            return
        self.transport = 'Uvicorn + urllib (real loopback HTTP)'
        with socket.socket() as sock:
            sock.bind(('127.0.0.1', 0))
            port = sock.getsockname()[1]
        self.base = 'http://127.0.0.1:' + str(port)
        self.opener = build_opener(ProxyHandler({}))
        self.process = subprocess.Popen(
            [sys.executable, '-m', 'uvicorn', 'app.main:app', '--host',
             '127.0.0.1', '--port', str(port), '--log-level', 'critical',
             '--no-access-log'], cwd=ROOT, env=env,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        for _ in range(150):
            if self.process.poll() is not None:
                raise RuntimeError('Isolated test server exited; verify existing application dependencies')
            try:
                if self.request('GET', '/api/config')[0] == 200:
                    return
            except (URLError, TimeoutError, ConnectionError):
                time.sleep(0.1)
        self.close()
        raise RuntimeError('Isolated test server did not become ready')

    def request(self, method, path, body=None, headers=None):
        headers = {'Content-Type': 'application/json', **(headers or {})}
        if self.client is not None:
            response = self.client.request(method, path, json=body, headers=headers)
            return response.status_code, response.json()
        data = None if body is None else json.dumps(body).encode()
        request = Request(self.base + path, data=data, headers=headers, method=method)
        try:
            response = self.opener.open(request, timeout=10)
        except HTTPError as exc:
            response = exc
        with response:
            return response.code, json.loads(response.read())

    def close(self):
        if self.client is not None:
            self.client.__exit__(None, None, None)
        if self.process is not None:
            self.process.terminate()
            try:
                self.process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=5)


def setUpModule():
    global TEMP, ORIGINAL_ENV, ENV, HTTP, TRANSPORT
    TEMP = tempfile.TemporaryDirectory(prefix='omniforge-docs-')
    root = Path(TEMP.name)
    # Deliberate allowlist: never inherit tokens, proxies, provider credentials,
    # PYTHONPATH from another checkout, or existing OMNIFORGE configuration.
    ENV = {key: os.environ[key] for key in ('PATH', 'LANG', 'LC_ALL', 'TZ') if key in os.environ}
    ENV.update({
        'HOME': str(root), 'TMPDIR': str(root), 'PYTHONPATH': str(ROOT),
        'PYTHONDONTWRITEBYTECODE': '1', 'PYTHONNOUSERSITE': '1',
        'OMNIFORGE_DB_PATH': str(root / 'data' / 'test.db'),
        'OMNIFORGE_SCRATCH_ROOT': str(root / 'scratch'),
        'OMNIFORGE_LIB_ROOT': str(root / 'lib'),
        'OMNIFORGE_API_KEY': KEY,
        'OMNIFORGE_MAX_SCRIPT_TIMEOUT_MS': '3000',
    })
    ORIGINAL_ENV = dict(os.environ)
    os.environ.clear()
    os.environ.update(ENV)
    sys.dont_write_bytecode = True
    logging.disable(logging.CRITICAL)  # negative cases must not log request values
    try:
        HTTP = LocalHTTP(ENV)
        TRANSPORT = HTTP.transport
    except Exception:
        tearDownModule()
        raise


def tearDownModule():
    if HTTP is not None:
        HTTP.close()
    if ORIGINAL_ENV is not None:
        os.environ.clear()
        os.environ.update(ORIGINAL_ENV)
    if TEMP is not None:
        TEMP.cleanup()


class ExampleChecks(unittest.TestCase):
    def test_payload_code_and_input_schema(self):
        # Validate with the same validator used by the API, not a home-grown subset.
        sys.path.insert(0, str(ROOT))
        from app.tool_authoring import ToolIn, validate_arguments
        for stem, script in EXAMPLES:
            with self.subTest(example=stem):
                payload, arguments, _ = fixture(stem)
                self.assertEqual(payload['code'], (ROOT / 'examples' / script).read_text())
                self.assertEqual(payload['requirements'], [])
                self.assertEqual(ToolIn.model_validate(payload).json_schema, payload['json_schema'])
                validate_arguments(arguments, payload['json_schema'])

    def test_python_stdout(self):
        self.check_direct('slugify', sys.executable, 'slugify.py')

    def test_node_commonjs_stdout(self):
        self.assertIsNotNone(shutil.which('node'), 'Node is required; no dependency installs are attempted')
        self.check_direct('summarize-json', 'node', 'summarize-json.cjs')

    def check_direct(self, stem, runtime, script):
        _, arguments, expected = fixture(stem)
        result = subprocess.run([runtime, str(ROOT / 'examples' / script)],
                                input=json.dumps(arguments), text=True, capture_output=True,
                                cwd=TEMP.name, env=ENV, timeout=10)
        self.assertEqual(result.returncode, 0, 'Fixture subprocess failed (stderr deliberately not echoed)')
        self.assertEqual(result.stderr, '', 'Fixture must not log to stderr')
        self.assertEqual(json.loads(result.stdout), expected)


class APIChecks(unittest.TestCase):
    def setUp(self):
        status, body = HTTP.request('GET', '/api/tools')
        self.assertEqual(status, 200)
        for tool in body['tools']:
            self.assertEqual(HTTP.request('DELETE', '/api/tools/' + tool['name'])[0], 200)
        scratch = Path(ENV['OMNIFORGE_SCRATCH_ROOT'])
        if scratch.exists():
            shutil.rmtree(scratch)
        self.payloads = [fixture(stem) for stem, _ in EXAMPLES]
        self.revisions = {}
        for payload, _, _ in self.payloads:
            # Refuse installers before any API request can execute a fixture.
            self.assertEqual(payload['requirements'], [])
            status, body = HTTP.request('POST', '/api/tools', payload)
            self.assertEqual(status, 200)
            self.assertTrue(body['ok'])
            self.revisions[payload['name']] = body['revision']

    def rpc(self, method, params=None, authenticated=True):
        return HTTP.request('POST', '/mcp',
                            {'jsonrpc': '2.0', 'id': 1, 'method': method, 'params': params or {}},
                            {'Authorization': 'Bearer ' + KEY} if authenticated else {})

    def assert_not_executed(self):
        scratch = Path(ENV['OMNIFORGE_SCRATCH_ROOT'])
        self.assertFalse(scratch.exists() and any(scratch.iterdir()),
                         'Rejected requests or saves must not reach the real runner')

    def test_http_create_preserves_actual_schemas(self):
        status, body = HTTP.request('GET', '/api/tools')
        self.assertEqual(status, 200)
        tools = {tool['name']: tool for tool in body['tools']}
        self.assertEqual(len(tools), 2)
        for payload, _, _ in self.payloads:
            tool = tools[payload['name']]
            self.assertEqual(json.loads(tool['json_schema_json']), payload['json_schema'])
            self.assertEqual(json.loads(tool['requirements_json']), [])
            self.assertEqual(tool['code'], payload['code'])
        self.assert_not_executed()

    def test_http_authoring_rejects_mcp_schema_field(self):
        payload = dict(self.payloads[0][0], name='wrong_http_schema_field')
        payload['inputSchema'] = payload.pop('json_schema')
        self.assertEqual(HTTP.request('POST', '/api/tools', payload)[0], 422)
        self.assert_not_executed()

    def test_duplicate_create_409_without_execution(self):
        for payload, _, _ in self.payloads:
            self.assertEqual(HTTP.request('POST', '/api/tools', payload)[0], 409)
        self.assert_not_executed()

    def test_run_test_valid_real_outputs(self):
        for payload, arguments, expected in self.payloads:
            with self.subTest(tool=payload['name']):
                status, body = HTTP.request('POST', '/api/tools/' + payload['name'] + '/run',
                                            {'arguments': arguments})
                self.assertEqual(status, 200)
                self.assertEqual(body['exit_code'], 0)
                self.assertFalse(body['timed_out'])
                self.assertEqual(body['stderr'], '')
                self.assertEqual(json.loads(body['stdout']), expected)

    def test_invalid_inputs_422_without_execution_or_value_echo(self):
        cases = [('slugify', {}), ('slugify', {'text': 42}),
                 ('slugify', {'text': ''}), ('slugify', {'text': 'ok', 'extra': KEY}),
                 ('summarize_json', {}), ('summarize_json', {'numbers': ['not-number']}),
                 ('summarize_json', {'numbers': [True]})]
        for name, arguments in cases:
            with self.subTest(tool=name, case=cases.index((name, arguments))):
                status, body = HTTP.request('POST', '/api/tools/' + name + '/run',
                                            {'arguments': arguments})
                self.assertEqual(status, 422)
                self.assertTrue(KEY not in json.dumps(body), 'Validation must not echo sensitive values')
        self.assert_not_executed()

    def test_mcp_auth_and_two_examples_plus_two_helpers(self):
        self.assertEqual(self.rpc('tools/list', authenticated=False)[0], 401)
        status, body = self.rpc('tools/list')
        self.assertEqual(status, 200)
        tools = {tool['name']: tool for tool in body['result']['tools']}
        self.assertEqual(set(tools), {'slugify', 'summarize_json',
                                     'omniforge_instructions', 'omniforge_create_tool'})
        for payload, _, _ in self.payloads:
            self.assertEqual(tools[payload['name']]['inputSchema'], payload['json_schema'])
        status, instructions = self.rpc('tools/call', {'name': 'omniforge_instructions', 'arguments': {}})
        self.assertEqual(status, 200)
        self.assertFalse(instructions['result']['isError'])
        self.assertIn('contract', json.loads(instructions['result']['content'][0]['text']))
        self.assert_not_executed()

    def test_mcp_real_execution(self):
        for payload, arguments, expected in self.payloads:
            status, body = self.rpc('tools/call', {'name': payload['name'], 'arguments': arguments})
            self.assertEqual(status, 200)
            self.assertFalse(body['result']['isError'])
            self.assertEqual(json.loads(body['result']['content'][0]['text']), expected)

    def test_mcp_authoring_input_schema_and_no_execution(self):
        payload = dict(self.payloads[0][0])
        payload['name'] = 'authored_slug'
        payload['inputSchema'] = payload.pop('json_schema')
        status, body = self.rpc('tools/call', {'name': 'omniforge_create_tool', 'arguments': payload})
        self.assertEqual(status, 200)
        self.assertFalse(body['result']['isError'])
        saved = json.loads(body['result']['content'][0]['text'])
        self.assertFalse(saved['executed'])
        tools = self.rpc('tools/list')[1]['result']['tools']
        self.assertEqual(next(t for t in tools if t['name'] == payload['name'])['inputSchema'],
                         payload['inputSchema'])
        wrong = dict(self.payloads[0][0], name='wrong_schema_field')
        status, rejected = self.rpc('tools/call', {'name': 'omniforge_create_tool', 'arguments': wrong})
        self.assertEqual(status, 200)
        self.assertTrue(rejected['result']['isError'])
        status, invalid = self.rpc('tools/call', {'name': 'authored_slug', 'arguments': {'text': KEY, 'extra': KEY}})
        self.assertEqual(status, 200)
        self.assertTrue(invalid['result']['isError'])
        self.assertTrue(KEY not in json.dumps(invalid), 'MCP validation must not echo sensitive values')
        self.assert_not_executed()

    def test_if_match_rejects_stale_save_and_run(self):
        payload = dict(self.payloads[0][0])
        path = '/api/tools/' + payload['name']
        old = self.revisions[payload['name']]
        payload['description'] += ' updated by isolated check'
        status, body = HTTP.request('PUT', path, payload, {'If-Match': old})
        self.assertEqual(status, 200)
        self.assertNotEqual(body['revision'], old)
        self.assertEqual(HTTP.request('PUT', path, payload, {'If-Match': old})[0], 412)
        self.assertEqual(HTTP.request('POST', path + '/run', {'arguments': {'text': 'valid'}},
                                      {'If-Match': old})[0], 412)
        tools = HTTP.request('GET', '/api/tools')[1]['tools']
        self.assertEqual(next(t for t in tools if t['name'] == payload['name'])['description'],
                         payload['description'])
        self.assert_not_executed()


class References(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []
        self.images = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        for key in ('href', 'src', 'poster'):
            if attrs.get(key):
                self.links.append(attrs[key])
        if tag == 'img':
            self.images.append(attrs)


def prose(text):
    # Examples, shell commands, placeholder URLs and HTML templates in fenced
    # code are not navigational links. Immutable review evidence is not scanned.
    return re.sub(r'^\s*(`{3,}|~{3,}).*?^\s*\1\s*$', '', text, flags=re.M | re.S)


def resolve_link(source, target):
    parsed = urlsplit(target)
    if parsed.scheme or parsed.netloc:
        # Private wiki URLs still need real page names; no network requests.
        match = re.match(r'https://github\.com/iOnic-Developer/omniforge/wiki(?:/([^?#]+))?', target, re.I)
        if match:
            return ROOT / 'docs/wiki' / (unquote(match.group(1) or 'Home').removesuffix('.md') + '.md')
        return None
    if not parsed.path:
        return None
    path = (source.parent / unquote(parsed.path)).resolve()
    if not path.exists() and source.parent == ROOT / 'docs/wiki' and not path.suffix:
        path = path.with_suffix('.md')
    return path


class DocumentationChecks(unittest.TestCase):
    def test_local_links_and_wiki_page_names(self):
        global LINK_COUNT
        files = [ROOT / 'README.md', ROOT / 'DOCKERHUB.md']
        files += sorted(p for p in (ROOT / 'docs').rglob('*.md')
                        if 'review' not in p.relative_to(ROOT / 'docs').parts)
        files += sorted((ROOT / 'examples').glob('*.md'))
        files += [ROOT / 'docs/index.html']
        broken = []
        count = 0
        for source in files:
            text = prose(source.read_text(encoding='utf-8'))
            parser = References()
            parser.feed(text)
            targets = parser.links + re.findall(r'!?\[[^\]\n]*\]\(\s*<?([^\s)>]+)>?(?:\s+"[^"]*")?\s*\)', text)
            targets += re.findall(r'^\s*\[[^\]]+\]:\s*<?([^\s>]+)>?', text, re.M)
            for target in targets:
                path = resolve_link(source, target)
                if path is not None:
                    count += 1
                    if not path.exists():
                        broken.append(str(source.relative_to(ROOT)) + ': ' + target)
        LINK_COUNT = count
        self.assertFalse(broken, 'Broken local links:\n' + '\n'.join(broken))

    def test_dockerhub_links_use_approved_public_destinations(self):
        text = (ROOT / 'DOCKERHUB.md').read_text()
        urls = re.findall(r'https?://[^\s)<>]+', text)
        public_roots = (
            'https://ionic-developer.github.io/omniforge/site/',
            'https://github.com/iOnic-Developer/omniforge',
            'https://raw.githubusercontent.com/iOnic-Developer/omniforge/',
        )
        for url in urls:
            if 'github' in urlsplit(url).hostname:
                self.assertTrue(url.startswith(public_roots), 'Unexpected publication destination')
        self.assertIn(public_roots[0], text)
        self.assertNotRegex(text, r'(?i)\b(?:public (?:live )?demo|hosted demo|live demo (?:at|available))\b')
        self.assertIn('unauthenticated', text)
        self.assertIn('127.0.0.1:8000:8000', text)

    def test_html_png_dimensions_and_bundled_font_licenses(self):
        for source in (ROOT / 'docs').rglob('*'):
            if source.suffix not in ('.md', '.html') or 'review' in source.relative_to(ROOT / 'docs').parts:
                continue
            parser = References()
            parser.feed(prose(source.read_text()))
            for image in parser.images:
                path = resolve_link(source, image.get('src', ''))
                if path is None or path.suffix.lower() != '.png' or not path.exists():
                    continue
                with path.open('rb') as stream:
                    header = stream.read(24)
                self.assertEqual(header[:8], b'\x89PNG\r\n\x1a\n')
                width, height = struct.unpack('>II', header[16:24])
                self.assertGreater(width * height, 0)
                if image.get('width', '').isdigit() and image.get('height', '').isdigit():
                    self.assertAlmostEqual(int(image['width']) / int(image['height']), width / height,
                                           places=2, msg=str(source.relative_to(ROOT)) + ': PNG aspect ratio mismatch')
        fonts = ROOT / 'docs/site-assets/fonts'
        for font, license_name in [('manrope.ttf', 'OFL-Manrope.txt'),
                                   ('jetbrains-mono.ttf', 'OFL-JetBrainsMono.txt')]:
            self.assertTrue((fonts / font).is_file())
            self.assertIn('SIL OPEN FONT LICENSE', (fonts / license_name).read_text())


if __name__ == '__main__':
    suite = unittest.defaultTestLoader.loadTestsFromModule(sys.modules[__name__])
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    print('Transport:', TRANSPORT or 'startup failed')
    print('Local documentation/image references checked:', LINK_COUNT)
    print('Actual results: tests=%d failures=%d errors=%d skipped=%d' %
          (result.testsRun, len(result.failures), len(result.errors), len(result.skipped)))
    sys.exit(not result.wasSuccessful())
