#!/usr/bin/env python3
"""Build only explicitly approved public documentation into _site/site/."""
from __future__ import annotations

import hashlib
import html
from html.parser import HTMLParser
import json
from pathlib import Path
import posixpath
import re
import shutil
import tempfile
import textwrap
from urllib.parse import unquote, urlsplit

import markdown

ROOT = Path(__file__).resolve().parents[1]
BASE = 'https://ionic-developer.github.io/omniforge/site/'
GUIDES = (
    'Installation', 'Getting-Started', 'Writing-Tools', 'Testing-Tools',
    'Connecting-MCP-Clients', 'MCP-Protocol-Support',
    'Security-and-Limitations', 'PWA-and-Themes',
)
CAPTURES = (
    'connect-desktop', 'help-desktop', 'overview-dark-desktop',
    'overview-desktop', 'overview-mobile', 'studio-desktop',
    'studio-error-desktop', 'studio-mobile', 'tools-desktop', 'tools-mobile',
)
# No directory walks: even fonts, SVGs and captures are named individually.
ASSETS = (
    'site.css', 'site.js', 'site-docs.css',
    'assets/banner.png', 'assets/how-it-works.png',
    'assets/logo.png', 'assets/social-preview.png',
    *(f'assets/screenshots/{name}.png' for name in CAPTURES),
    'site-assets/banner.svg', 'site-assets/how-it-works.svg',
    'site-assets/mark.svg', 'site-assets/social-preview.svg',
    'site-assets/fonts/manrope.ttf', 'site-assets/fonts/jetbrains-mono.ttf',
    'site-assets/fonts/OFL-Manrope.txt', 'site-assets/fonts/OFL-JetBrainsMono.txt',
)
FORBIDDEN = re.compile(
    r'192\.168\.0\.180|\bNucNas\b|LibreChat-Workspace|'
    r'/workspace/|/mnt/user/appdata/(?!omniforge(?:/|\b))|'
    r'gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|'
    r'-----BEGIN (?:RSA |OPENSSH |EC )?PRIVATE KEY-----', re.I,
)


def read_source(relative):
    path = ROOT / relative
    if path.is_symlink() or not path.is_file():
        raise ValueError(f'Missing or symlinked approved input: {relative}')
    if not path.resolve().is_relative_to(ROOT):
        raise ValueError('Input escapes repository')
    return path.read_bytes()


class PublicLinks(HTMLParser):
    """Rewrite rendered markup only; never rewrite code examples or raw source."""

    def __init__(self, source):
        super().__init__(convert_charrefs=False)
        self.source = source
        self.output = []
        self.anchors = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag in ('pre', 'table'):
            attrs['tabindex'] = '0'  # Keyboard access to horizontally scrolling content.
        if any(key.lower().startswith('on') for key in attrs):
            raise ValueError('Event handler in published markup')
        if tag in ('a', 'img'):
            key = 'href' if tag == 'a' else 'src'
            target = attrs.get(key, '')
            parsed = urlsplit(target)
            if parsed.scheme or parsed.netloc:
                if tag == 'img' or parsed.scheme not in ('https', 'http', 'mailto'):
                    raise ValueError('Unsupported public URL')
            elif parsed.path:
                resolved = posixpath.normpath(posixpath.join(
                    posixpath.dirname(self.source), unquote(parsed.path)))
                guide = Path(resolved).stem
                if resolved == 'docs/wiki/Home.md':
                    attrs[key] = '../index.html'
                elif resolved == f'docs/wiki/{guide}.md' and guide in GUIDES:
                    attrs[key] = guide + '.html' + ('#' + parsed.fragment if parsed.fragment else '')
                elif resolved.startswith('docs/') and resolved[5:] in ASSETS:
                    attrs[key] = '../' + resolved[5:]
                elif tag == 'a':
                    self.anchors.append(False)
                    self.output.append('<span class="repository-required">')
                    return
                else:
                    raise ValueError('Image not in public allowlist')
        if tag == 'a':
            self.anchors.append(True)
        self.output.append('<' + tag + ''.join(
            ' ' + key + ('="' + html.escape(value, quote=True) + '"' if value is not None else '')
            for key, value in attrs.items()) + '>')

    def handle_endtag(self, tag):
        if tag == 'a' and not self.anchors.pop():
            self.output.append(' (repository access required)</span>')
        else:
            self.output.append('</' + tag + '>')

    def handle_data(self, data):
        self.output.append(data)

    def handle_entityref(self, name):
        self.output.append('&' + name + ';')

    def handle_charref(self, name):
        self.output.append('&#' + name + ';')

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)


def guide_page(name, source):
    # Reviewed screenshot wrappers become ordinary Markdown; all other raw HTML
    # is escaped by disabling Markdown's raw-HTML stash and inline processor.
    source = re.sub(
        r'<p align="center"><img src="([^"]+)" alt="([^"]+)" width="\d+"></p>',
        lambda m: '![' + m[2] + '](' + m[1] + ')', source,
    )
    # Python-Markdown only recognises top-level fenced blocks. Preserve the
    # source's three-space list examples as standalone, readable code blocks.
    source = re.sub(r'^ {3}```[^\n]*\n.*?^ {3}```[ \t]*$',
                    lambda m: '\n' + textwrap.dedent(m[0]) + '\n',
                    source, flags=re.M | re.S)
    md = markdown.Markdown(extensions=['fenced_code', 'tables', 'toc'])
    md.preprocessors.deregister('html_block')
    md.inlinePatterns.deregister('html')
    body = md.convert(source)
    links = PublicLinks(f'docs/wiki/{name}.md')
    links.feed(body)
    title = re.search(r'^# (.+)$', source, re.M)[1]
    navigation = ''.join(
        f'<a href="{item}.html"' + (' aria-current="page"' if item == name else '') +
        f'>{html.escape(item.replace("-", " "))}</a>' for item in GUIDES
    )
    return f'''<!doctype html>
<html lang="en-GB"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(title)} — OmniForge</title>
<meta name="robots" content="index, follow">
<link rel="canonical" href="{BASE}guides/{name}.html">
<link rel="icon" href="../site-assets/mark.svg" type="image/svg+xml">
<link rel="stylesheet" href="../site.css"><link rel="stylesheet" href="../site-docs.css">
</head><body><a class="skip" href="#main">Skip to content</a>
<header class="wrap guide-header"><a class="brand" href="../index.html">OmniForge</a><p>Product guides · Trusted local networks only</p></header>
<div class="wrap guide-layout"><nav class="guide-nav" aria-label="Product guides">{navigation}</nav>
<main id="main" class="guide-content">{''.join(links.output)}</main></div>
<footer class="wrap guide-footer">© 2026 OmniForge. All rights reserved.</footer></body></html>
'''


def landing(source):
    source = re.sub(r'<!--.*?-->', '', source, flags=re.S)
    source = source.replace('content="noindex, nofollow"', 'content="index, follow"')
    source = source.replace('<meta property="og:type"',
                            f'<link rel="canonical" href="{BASE}">\n  <meta property="og:url" content="{BASE}">\n  <meta property="og:type"')
    source = source.replace('content="assets/social-preview.png"',
                            f'content="{BASE}assets/social-preview.png"')
    source = source.replace('Private repository · Product-page review · No public hosting configured',
                            'Self-hosted Python and Node tool workspace')
    source = source.replace('Private repository · Access required.<br>Prepared for review only. No hosting or deployment enabled.',
                            '© 2026 OmniForge. All rights reserved.')
    source = source.replace('These relative Markdown links are private repository documentation, not a publicly hosted documentation site.',
                            'Practical guides for installing, writing and testing trusted tools.')
    source = source.replace('aria-label="Private documentation"', 'aria-label="Product documentation"')
    source = source.replace('Private installation guide', 'Installation guide')
    source = source.replace('local review build', 'documented workspace')
    source = re.sub(r'href="wiki/([A-Za-z-]+)\.md(#[^"]*)?"',
                    lambda m: 'href="guides/' + m[1] + '.html' + (m[2] or '') + '"', source)
    if re.search(r'private.repository|no public hosting|no hosting or deployment|wiki/[^" ]+\.md', source, re.I):
        raise ValueError('Untransformed landing-page metadata or links')
    return source


class References(HTMLParser):
    def __init__(self):
        super().__init__()
        self.refs = []
        self.ids = set()

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if attrs.get('id'):
            if attrs['id'] in self.ids:
                raise ValueError('Duplicate HTML id')
            self.ids.add(attrs['id'])
        self.refs.extend(attrs[key] for key in ('href', 'src') if attrs.get(key))


def validate(stage, expected):
    actual = {p.relative_to(stage).as_posix() for p in stage.rglob('*') if p.is_file()}
    if actual != expected:
        raise ValueError('Output differs from explicit allowlist')
    pages = {}
    for relative in sorted(actual):
        path = stage / relative
        if path.suffix in ('.html', '.css', '.js', '.svg', '.json', '.txt'):
            text = path.read_text()
            if FORBIDDEN.search(text):
                raise ValueError(f'Privacy check failed: {relative}')
        if path.suffix == '.html':
            parser = References()
            parser.feed(text)
            pages[relative] = parser
    checked = 0
    for relative, parser in pages.items():
        refs = list(parser.refs)
        for target in refs:
            parsed = urlsplit(target)
            if parsed.scheme or parsed.netloc:
                continue
            destination = (stage / relative).parent / unquote(parsed.path)
            if not parsed.path:
                destination = stage / relative
            destination = destination.resolve()
            if not destination.is_relative_to(stage.resolve()) or not destination.is_file():
                raise ValueError(f'Broken local reference in {relative}: {target}')
            key = destination.relative_to(stage.resolve()).as_posix()
            if parsed.fragment and key in pages and unquote(parsed.fragment) not in pages[key].ids:
                raise ValueError(f'Broken fragment in {relative}: {target}')
            checked += 1
    for asset in ('site.css', 'site-docs.css'):
        for target in re.findall(r'url\([\'"]?([^\)\'\"]+)', (stage / 'site' / asset).read_text()):
            if target not in ASSETS or not (stage / 'site' / target).is_file():
                raise ValueError('Unapproved CSS asset')
    return checked


def main():
    if markdown.__version__ != '3.8.2':
        raise SystemExit('Use the pinned requirements-docs.txt in a docs-only virtualenv')
    output = ROOT / '_site'
    if output.is_symlink() or (output.exists() and not output.is_dir()):
        raise ValueError('Refusing unsafe output path')
    sources = ['docs/index.html', *(f'docs/wiki/{name}.md' for name in GUIDES),
               *(f'docs/{asset}' for asset in ASSETS)]
    inputs = {source: read_source(source) for source in sources}
    with tempfile.TemporaryDirectory(prefix='omniforge-public-site-') as temporary:
        stage = Path(temporary)
        site = stage / 'site'
        (site / 'guides').mkdir(parents=True)
        (site / 'index.html').write_text(landing(inputs['docs/index.html'].decode()), encoding='utf-8')
        for name in GUIDES:
            (site / 'guides' / (name + '.html')).write_text(
                guide_page(name, inputs[f'docs/wiki/{name}.md'].decode()), encoding='utf-8')
        for asset in ASSETS:
            target = site / asset
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(inputs['docs/' + asset])
        (stage / '.nojekyll').write_text('')
        expected = {'.nojekyll', 'site/index.html', *(f'site/{asset}' for asset in ASSETS),
                    *(f'site/guides/{name}.html' for name in GUIDES)}
        checked = validate(stage, expected)
        manifest = {
            'target': BASE, 'scope': 'Public static documentation only; no application, history or audit files.',
            'sources': [{'source': source, 'sha256': hashlib.sha256(data).hexdigest()}
                        for source, data in sorted(inputs.items())],
            'outputs': [{'path': relative, 'sha256': hashlib.sha256((stage / relative).read_bytes()).hexdigest()}
                        for relative in sorted(expected)],
        }
        (site / 'build-manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
        expected.add('site/build-manifest.json')
        validate(stage, expected)
        if output.exists():
            shutil.rmtree(output)
        shutil.copytree(stage, output)
    print(f'Built {len(expected)} allowlisted files; {len(GUIDES)} guides; {checked} local references checked.')
    print('Output: _site/site/ — public-ready artifact only; this does not deploy or change repository visibility.')


if __name__ == '__main__':
    main()
