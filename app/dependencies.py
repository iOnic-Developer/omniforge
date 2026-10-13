"""Lazy dependency installs for trusted scripts; not a security sandbox."""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import time

LIB_ROOT = os.environ.get('OMNIFORGE_LIB_ROOT', '/opt/omniforge/lib')
INSTALL_TIMEOUT = 120
LOCK_TIMEOUT = 125
STDERR_LIMIT = 3000
PYTHON_REQUIREMENT = re.compile(r'[A-Za-z0-9](?:[A-Za-z0-9._-]*[A-Za-z0-9])?(?:==[0-9]+(?:\.[0-9]+)*(?:(?:a|b|rc|post|dev)[0-9]+)?)?')
NODE_REQUIREMENT = re.compile(r'(?:@[a-z0-9][a-z0-9._-]*/)?[a-z0-9][a-z0-9._-]*(?:@(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)(?:-[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?(?:\+[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?)?')


class DependencyError(ValueError):
    """Safe-to-display dependency validation, locking or installation error."""


def validate_requirements(requirements: list[str], language: str) -> list[str]:
    if not isinstance(requirements, list) or len(requirements) > 50:
        raise DependencyError('Requirements must be an array of at most 50 package names')
    pattern = PYTHON_REQUIREMENT if language in ('python', 'python3') else NODE_REQUIREMENT
    if language not in ('python', 'python3', 'node', 'js', 'javascript'):
        raise DependencyError('Unsupported dependency language')
    for item in requirements:
        if not isinstance(item, str) or len(item) > 200 or not pattern.fullmatch(item):
            raise DependencyError('Invalid requirement: use Python name or name==version; Node name or @scope/name with optional @1.2.3 pin. URLs, paths, flags, aliases and binaries are unsupported')
        if language in ('node', 'js', 'javascript') and item.lstrip('@').split('@')[0].split('/')[-1] in ('node_modules', 'favicon.ico'):
            raise DependencyError('Invalid Node package name')
        if language in ('node', 'js', 'javascript') and '@' in item.lstrip('@'):
            version = item.rsplit('@', 1)[1]
            prerelease = version.split('+', 1)[0].partition('-')[2]
            if any(part.isdigit() and len(part) > 1 and part.startswith('0') for part in prerelease.split('.')):
                raise DependencyError('Invalid exact Node semver pin')
    return sorted(set(requirements))


def _installer_environment(staging: Path) -> dict[str, str]:
    """No inherited API keys, Python paths, proxy credentials or pip/npm config."""
    home = staging / 'home'
    home.mkdir()
    tmp = staging / 'tmp'
    tmp.mkdir()
    return {
        'PATH': '/opt/venv/bin:/usr/local/bin:/usr/bin:/bin',
        'HOME': str(home), 'TMPDIR': str(tmp), 'LANG': 'C.UTF-8',
        'PYTHONNOUSERSITE': '1', 'PYTHONDONTWRITEBYTECODE': '1',
        'PIP_CONFIG_FILE': os.devnull,
        'NPM_CONFIG_USERCONFIG': os.devnull,
        'NPM_CONFIG_GLOBALCONFIG': str(home / 'empty-global-npmrc'),
    }


def _safe_stderr(stderr: str) -> str:
    # Installer children never receive app secrets; also redact inherited values
    # in mocked/unexpected diagnostics before displaying a bounded final excerpt.
    text = str(stderr or '')
    for key, value in os.environ.items():
        if value and re.search(r'KEY|TOKEN|SECRET|PASSWORD|CREDENTIAL|PROXY|PIP_|NPM_', key, re.I):
            text = text.replace(value, '[redacted]')
    text = re.sub(r'https?://[^\s<>]+', '[url]', text)
    text = re.sub(r'\x1b\[[0-?]*[ -/]*[@-~]', '', text)
    return text[-STDERR_LIMIT:]


def ensure_dependencies(tool, runtime: str) -> Path | None:
    """Return a complete immutable package directory, installing on cache miss."""
    try:
        requirements = validate_requirements(json.loads(tool.requirements_json or '[]'), tool.language)
    except (TypeError, json.JSONDecodeError) as exc:
        raise DependencyError('Invalid stored requirements') from exc
    if not requirements:
        return None
    language = 'python3' if tool.language in ('python', 'python3') else 'node'
    tool_key = hashlib.sha256(str(tool.id).encode()).hexdigest()
    digest = hashlib.sha256(json.dumps(requirements, separators=(',', ':')).encode()).hexdigest()
    parent = Path(LIB_ROOT).resolve() / tool_key / language
    parent.mkdir(parents=True, exist_ok=True)
    destination = parent / digest
    marker = destination / '.complete'
    with (parent / (digest + '.lock')).open('a') as lock:
        deadline = time.monotonic() + LOCK_TIMEOUT
        while True:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if time.monotonic() >= deadline:
                    raise DependencyError('Dependency installation lock wait timed out; retry later')
                time.sleep(0.1)
        if marker.is_file():
            return destination / ('site-packages' if language == 'python3' else 'node_modules')
        # Never delete a pre-existing directory: only our unique staging tree.
        if destination.exists():
            raise DependencyError('Incomplete dependency cache exists; administrator review required')
        staging = Path(tempfile.mkdtemp(prefix='.install-', dir=parent))
        try:
            env = _installer_environment(staging)
            if language == 'python3':
                command = [runtime, '-m', 'pip', 'install', '--target', str(staging / 'site-packages'),
                           '--only-binary=:all:', '--no-cache-dir', '--disable-pip-version-check',
                           '--index-url', 'https://pypi.org/simple', '--no-input', '--no-compile', *requirements]
            else:
                npm = shutil.which('npm', path=env['PATH'])
                if not npm:
                    raise DependencyError('npm runtime is unavailable')
                (staging / 'package.json').write_text('{"private":true,"name":"omniforge-tool-deps","version":"1.0.0"}')
                command = [npm, 'install', '--prefix', str(staging), '--ignore-scripts', '--no-audit',
                           '--no-fund', '--cache', str(staging / 'npm-cache'),
                           '--registry', 'https://registry.npmjs.org', *requirements]
            # File-backed output avoids unbounded pipe capture. Only bounded stderr is read.
            with (staging / 'install.stderr').open('w+b') as stderr:
                try:
                    result = subprocess.run(command, cwd=staging, env=env, stdin=subprocess.DEVNULL,
                                            stdout=subprocess.DEVNULL, stderr=stderr, text=True,
                                            timeout=INSTALL_TIMEOUT)
                except subprocess.TimeoutExpired as exc:
                    raise DependencyError(f'Dependency installation timed out after {INSTALL_TIMEOUT}s; script was not run') from exc
                if result.returncode:
                    stderr.seek(0, os.SEEK_END)
                    stderr.seek(max(0, stderr.tell() - STDERR_LIMIT))
                    detail = _safe_stderr(stderr.read().decode('utf-8', errors='replace'))
                    raise DependencyError('Dependency installation failed; script was not run' + (': ' + detail if detail else ''))
            (staging / 'install.stderr').unlink()
            (staging / '.complete').write_text(json.dumps(requirements))
            # Atomic publication: no reader can observe a partially installed env.
            staging.rename(destination)
            return destination / ('site-packages' if language == 'python3' else 'node_modules')
        except OSError as exc:
            raise DependencyError('Dependency storage or installer unavailable; verify writable OMNIFORGE_LIB_ROOT') from exc
        finally:
            if staging.exists():
                shutil.rmtree(staging)
