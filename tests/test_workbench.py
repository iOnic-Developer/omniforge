"""Workbench contracts, actual ASGI paths and asset safety; no browser simulation."""
import asyncio
import json
from pathlib import Path
import re
import struct
import unittest

from types import SimpleNamespace
from urllib.parse import unquote
from app import main


class WorkbenchTests(unittest.TestCase):
    def test_manifest_and_asset_http_contracts(self):
        async def request(path):
            messages = []
            async def receive():
                return {'type': 'http.request', 'body': b'', 'more_body': False}
            async def send(message):
                messages.append(message)
            scope = {'type': 'http', 'asgi': {'version': '3.0'}, 'http_version': '1.1',
                     'method': 'GET', 'scheme': 'http', 'path': unquote(path),
                     'raw_path': path.encode(), 'query_string': b'', 'root_path': '',
                     'headers': [], 'client': ('test', 1234), 'server': ('test', 80)}
            await main.app(scope, receive, send)
            start = next(m for m in messages if m['type'] == 'http.response.start')
            body = b''.join(m.get('body', b'') for m in messages if m['type'] == 'http.response.body')
            return SimpleNamespace(status_code=start['status'], content=body,
                                   text=body.decode('utf-8', errors='replace'),
                                   headers={k.decode(): v.decode() for k, v in start['headers']})
        async def check():
            response = await request('/manifest.webmanifest')
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.headers['content-type'], 'application/manifest+json')
            manifest = json.loads(response.text)
            self.assertEqual(manifest['scope'], '/')
            self.assertEqual(manifest['start_url'], '/')
            self.assertEqual(manifest['display'], 'standalone')
            self.assertEqual({i['sizes'] for i in manifest['icons']}, {'192x192', '512x512'})
            self.assertTrue(any(i['purpose'] == 'maskable' for i in manifest['icons']))
            for icon in manifest['icons']:
                image = await request(icon['src'])
                self.assertEqual(image.status_code, 200)
                self.assertEqual(image.headers['content-type'], 'image/png')
                self.assertTrue(image.content.startswith(b'\x89PNG\r\n\x1a\n'))
                width, height = struct.unpack('>II', image.content[16:24])
                self.assertEqual(f'{width}x{height}', icon['sizes'])
            svg = await request('/static/forge.svg')
            self.assertEqual(svg.status_code, 200)
            self.assertIn('image/svg+xml', svg.headers['content-type'])
            self.assertIn('viewBox="0 0 32 32"', svg.text)
            for path in ['/static/test.db', '/static/dashboard.html', '/static/.env', '/static/%2e%2e%2fmain.py']:
                self.assertEqual((await request(path)).status_code, 404)
            dashboard = await request('/')
            self.assertEqual(dashboard.status_code, 200)
            self.assertIn('href="/manifest.webmanifest"', dashboard.text)
        asyncio.run(check())

    def test_no_sensitive_offline_cache_or_fake_execution(self):
        page = Path('app/templates/dashboard.html').read_text()
        self.assertNotIn('serviceWorker.register', page)
        self.assertNotIn('caches.open', page)
        self.assertNotIn('indexedDB', page)
        self.assertNotIn('backgroundSync', page)
        self.assertIn('current HTTP LAN address is not installable', page)
        self.assertIn('online execution only', page)
        self.assertEqual(set(main.STATIC_TYPES), {'forge.svg', 'icon-192.png', 'icon-512.png', 'icon-maskable-512.png'})

    def test_semantic_themes_and_radius_ceiling(self):
        page = Path('app/templates/dashboard.html').read_text()
        css = page.split('<style>')[1].split('</style>')[0]
        self.assertIn('--radius:4px', css)
        for radius in re.findall(r'border-radius:([^;]+)', css):
            self.assertIn(radius, {'var(--radius)', '0'})
        self.assertIn(':root[data-theme="dark"]', css)
        self.assertIn("localStorage.getItem('omniforge.theme')", page)
        self.assertIn("themeMedia.addEventListener('change'", page)
        for target in ['themeSelect', 'toolName', 'toolCode', 'toolRequirements']:
            self.assertIn('for="' + target + '"', page)
        for label in ['New tool', 'Help and examples', 'MCP configuration']:
            self.assertIn('aria-label="' + label + '"', page)

    def test_theme_text_contrast(self):
        page = Path('app/templates/dashboard.html').read_text()
        css = page.split('<style>')[1].split('</style>')[0]
        def luminance(color):
            rgb = [int(color[i:i+2], 16) / 255 for i in (1, 3, 5)]
            rgb = [v/12.92 if v <= .04045 else ((v+.055)/1.055)**2.4 for v in rgb]
            return sum(a*b for a, b in zip(rgb, (.2126, .7152, .0722)))
        def ratio(a, b):
            low, high = sorted([luminance(a), luminance(b)])
            return (high+.05)/(low+.05)
        for block in re.findall(r':root[^{}]*\{([^}]+)\}', css):
            tokens = dict(re.findall(r'--([\w-]+):(#[0-9a-f]{6})(?=;)', block))
            for text in ['text', 'muted', 'accent', 'green', 'red']:
                for background in ['bg', 'card', 'editor', 'accent-soft']:
                    self.assertGreaterEqual(ratio(tokens[text], tokens[background]), 4.5, (text, background, tokens))
            self.assertGreaterEqual(ratio(tokens['card'], tokens['accent']), 4.5)

    def test_logo_is_original_vector_not_remote_or_emoji(self):
        svg = Path('app/static/forge.svg').read_text()
        self.assertIn('<polygon', svg)
        self.assertNotIn('<image', svg)
        self.assertNotIn('<script', svg)
        self.assertIn('/static/forge.svg', Path('app/templates/dashboard.html').read_text())
