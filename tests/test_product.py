"""Public asset and PWA contracts: no runtime directories or dynamic caches."""
import asyncio
import json
from pathlib import Path
import re
import struct
import unittest
from app import main


class ProductTests(unittest.TestCase):
    def test_asset_allowlist_and_mime(self):
        for asset, mime in main.PUBLIC_ASSETS.items():
            with self.subTest(asset=asset):
                response = asyncio.run(main.public_asset(asset))
                self.assertTrue(Path(response.path).is_file())
                self.assertEqual(response.media_type, mime)
                self.assertEqual(response.headers['cache-control'], 'no-cache')
                self.assertEqual(response.headers['x-content-type-options'], 'nosniff')

    def test_private_paths_are_rejected(self):
        for path in ('../main.py', '.env', 'omniforge.db', 'fonts/../../main.py', '/etc/passwd', 'sw.js'):
            with self.subTest(path=path), self.assertRaises(main.HTTPException) as error:
                asyncio.run(main.public_asset(path))
            self.assertEqual(error.exception.status_code, 404)

    def test_worker_root_scope_no_cache_and_mime(self):
        response = asyncio.run(main.service_worker())
        self.assertEqual(response.media_type, 'application/javascript')
        self.assertEqual(response.headers['service-worker-allowed'], '/')
        self.assertEqual(response.headers['cache-control'], 'no-cache')

    def test_dashboard_no_store(self):
        response = asyncio.run(main.dashboard())
        self.assertEqual(response.headers['cache-control'], 'no-store')

    def test_manifest_icons_and_dimensions(self):
        manifest = json.loads((main.STATIC_DIR / 'manifest.webmanifest').read_text())
        self.assertEqual(manifest['scope'], '/')
        self.assertEqual(manifest['display'], 'standalone')
        self.assertEqual(manifest['start_url'], '/#overview')
        for icon in manifest['icons']:
            filename = icon['src'].removeprefix('/assets/')
            data = (main.STATIC_DIR / filename).read_bytes()
            self.assertEqual(data[:8], b'\x89PNG\r\n\x1a\n')
            size = struct.unpack('>II', data[16:24])
            self.assertEqual(icon['sizes'], f'{size[0]}x{size[1]}')
        for filename, expected in [('favicon-32.png',32), ('apple-touch-icon.png',180)]:
            data = (main.STATIC_DIR / filename).read_bytes()
            self.assertEqual(struct.unpack('>II',data[16:24]), (expected,expected))
        self.assertTrue(any(i['purpose'] == 'maskable' for i in manifest['icons']))

    def test_static_only_worker_allowlist(self):
        worker = (main.STATIC_DIR / 'sw.js').read_text()
        assets = re.findall(r"'([^']+)'", re.search(r'const ASSETS = \[(.*?)\];',worker,re.S)[1])
        self.assertEqual(len(assets), 12)
        for path in assets:
            self.assertIn(path.removeprefix('/assets/'), main.PUBLIC_ASSETS)
            self.assertTrue(path.startswith('/assets/'))
        self.assertNotIn('/', assets)
        self.assertNotIn('/api/tools', assets)
        self.assertIn("credentials:'omit'", worker)
        self.assertIn("request.method !== 'GET'", worker)
        self.assertIn("request.headers.has('Authorization')", worker)
        self.assertNotIn('cache.put(request', worker)
        self.assertNotIn('localStorage', worker)

    def test_licensed_self_hosted_fonts(self):
        for filename in ('fonts/OFL-Manrope.txt','fonts/OFL-JetBrainsMono.txt'):
            self.assertIn('SIL OPEN FONT LICENSE', (main.STATIC_DIR / filename).read_text())
        css = (main.STATIC_DIR / 'product.css').read_text()
        self.assertRegex(css, r'font-display:\s*swap')
        self.assertNotIn('fonts.googleapis',css)

    def test_storage_and_security_copy(self):
        page = Path('app/templates/dashboard.html').read_text()
        self.assertEqual(page.count('localStorage.setItem('),1)
        self.assertIn("localStorage.setItem('omniforge-theme',preference)",page)
        self.assertIn('not ready for public exposure',page)
        self.assertIn('not GET /mcp',page)
        self.assertIn('not full Streamable HTTP',page)
        self.assertIn('isSecureContext',page)
