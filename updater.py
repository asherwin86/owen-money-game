"""Auto-updater: checks GitHub Releases for a newer version and swaps the exe in place.

Safety rules: HTTPS only, hosts limited to GitHub, the download must match the size and SHA-256 digest that
GitHub reports for the release asset, and it must look like a Windows executable before it replaces anything.
The running exe is renamed (not overwritten), so a failed swap rolls back cleanly.
"""
import hashlib
import json
import os
import subprocess
import sys
import threading
import urllib.parse
import urllib.request
import webbrowser

REPO = 'asherwin86/owen-money-game'
API_URL = f'https://api.github.com/repos/{REPO}/releases/latest'
ASSET_NAME = 'MoneyTycoon3D.exe'
RELEASES_PAGE = f'https://github.com/{REPO}/releases/latest'
ALLOWED_HOSTS = ('github.com', 'githubusercontent.com')          # and any subdomain of these
TIMEOUT = 8
CHUNK = 256 * 1024


def parse_version(text):
    """'v1.2.3' -> (1, 2, 3); anything unparseable -> ()."""
    parts = []
    for p in str(text).strip().lstrip('vV').split('.'):
        digits = ''.join(ch for ch in p if ch.isdigit())
        if not digits:
            return ()
        parts.append(int(digits))
    return tuple(parts)


def is_newer(latest, current):
    a, b = parse_version(latest), parse_version(current)
    return bool(a) and bool(b) and a > b


def _host_ok(url, allowed):
    parts = urllib.parse.urlparse(url)
    host = (parts.hostname or '').lower()
    return parts.scheme == 'https' and any(host == h or host.endswith('.' + h) for h in allowed)


class UpdateError(Exception):
    pass


class Updater:
    def __init__(self, current_version, api_url=API_URL, exe_path=None, frozen=None, allowed_hosts=ALLOWED_HOSTS,
                 allow_http=False):
        self.current = current_version
        self.api_url = api_url
        self.frozen = getattr(sys, 'frozen', False) if frozen is None else frozen
        self.exe_path = exe_path or (sys.executable if self.frozen else None)
        self.allowed_hosts = allowed_hosts
        self.allow_http = allow_http                  # tests only
        self.state = 'idle'       # idle | checking | none | available | downloading | ready | error | failed
        self.info = {}            # version, url, size, sha256, notes
        self.progress = 0.0
        self.error = ''
        self.manual = False       # the user asked for this check (so report "up to date" too)
        self.prompted = False
        self._lock = threading.Lock()

    # ---- capability -----------------------------------------------------------
    @property
    def can_self_update(self):
        return bool(self.frozen and self.exe_path and sys.platform == 'win32')

    def _paths(self):
        d, name = os.path.split(self.exe_path)
        stem, ext = os.path.splitext(name)
        return (os.path.join(d, f'{stem}.new{ext}'), os.path.join(d, f'{stem}.old{ext}'),
                os.path.join(d, f'{stem}.new{ext}.part'))

    def cleanup(self):
        """Delete leftovers from a previous update (call at start-up)."""
        if not self.exe_path:
            return
        for p in self._paths():
            try:
                os.remove(p)
            except OSError:
                pass

    # ---- network ---------------------------------------------------------------
    def _open(self, url):
        if not (self.allow_http or _host_ok(url, self.allowed_hosts)):
            raise UpdateError('Refusing to contact a non-GitHub address.')
        req = urllib.request.Request(url, headers={'User-Agent': 'MoneyTycoon3D-updater',
                                                   'Accept': 'application/vnd.github+json'})
        resp = urllib.request.urlopen(req, timeout=TIMEOUT)
        if not (self.allow_http or _host_ok(resp.geturl(), self.allowed_hosts)):
            resp.close()
            raise UpdateError('The download was redirected to an untrusted address.')
        return resp

    def check(self, manual=False):
        """Blocking check. Sets state to 'available', 'none' or 'error'."""
        with self._lock:
            if self.state in ('checking', 'downloading'):
                return
            self.state, self.manual, self.error = 'checking', manual, ''
        try:
            with self._open(self.api_url) as resp:
                data = json.loads(resp.read(2_000_000).decode('utf-8'))
            if data.get('draft') or data.get('prerelease'):
                self.state = 'none'
                return
            tag = data.get('tag_name', '')
            if not is_newer(tag, self.current):
                self.state = 'none'
                return
            asset = next((a for a in data.get('assets', []) if a.get('name') == ASSET_NAME), None)
            if asset is None:
                raise UpdateError('The new release has no downloadable game file yet.')
            digest = (asset.get('digest') or '')
            self.info = dict(version=tag.lstrip('vV'), url=asset.get('browser_download_url', ''),
                            size=int(asset.get('size') or 0),
                            sha256=digest.split(':', 1)[1].lower() if digest.startswith('sha256:') else '',
                            notes=(data.get('body') or '').strip())
            self.prompted = False
            self.state = 'available'
        except Exception as e:                        # network down, rate limit, bad JSON...
            self.error = str(e) or e.__class__.__name__
            self.state = 'error'

    def check_async(self, manual=False):
        threading.Thread(target=self.check, args=(manual,), daemon=True).start()

    def download(self):
        """Blocking download + verification into <exe>.new.exe. Sets state to 'ready' or 'failed'."""
        if not self.can_self_update and not self.allow_http:
            self.error, self.state = 'Self-update only works from the installed exe.', 'failed'
            return
        info = self.info
        new, _, part = self._paths()
        with self._lock:
            self.state, self.progress, self.error = 'downloading', 0.0, ''
        try:
            if not info.get('url'):
                raise UpdateError('No download address.')
            sha = hashlib.sha256()
            got = 0
            with self._open(info['url']) as resp, open(part, 'wb') as f:
                total = int(resp.headers.get('Content-Length') or info.get('size') or 0)
                while True:
                    block = resp.read(CHUNK)
                    if not block:
                        break
                    f.write(block)
                    sha.update(block)
                    got += len(block)
                    self.progress = got / total if total else 0.0
            if info.get('size') and got != info['size']:
                raise UpdateError(f'Download incomplete ({got} of {info["size"]} bytes).')
            if info.get('sha256') and sha.hexdigest() != info['sha256']:
                raise UpdateError('The downloaded file does not match its checksum, so it was discarded.')
            with open(part, 'rb') as f:
                if f.read(2) != b'MZ':
                    raise UpdateError('The downloaded file is not a Windows program.')
            os.replace(part, new)
            self.progress, self.state = 1.0, 'ready'
        except Exception as e:
            self.error = str(e) or e.__class__.__name__
            self.state = 'failed'
            try:
                os.remove(part)
            except OSError:
                pass

    def download_async(self):
        threading.Thread(target=self.download, daemon=True).start()

    # ---- install ---------------------------------------------------------------
    def install(self, launch=True):
        """Swap the downloaded exe into place and (optionally) start it. The caller then quits."""
        new, old, _ = self._paths()
        if not os.path.exists(new):
            raise UpdateError('The update file is missing.')
        try:
            if os.path.exists(old):
                os.remove(old)
        except OSError:
            pass
        os.replace(self.exe_path, old)               # a running exe can be renamed on Windows, not overwritten
        try:
            os.replace(new, self.exe_path)
        except OSError:
            os.replace(old, self.exe_path)           # roll back
            raise UpdateError('Could not replace the game file. Is the folder read-only?')
        if launch:
            env = dict(os.environ, PYINSTALLER_RESET_ENVIRONMENT='1')     # make the new exe unpack its own files
            flags = 0
            if sys.platform == 'win32':
                flags = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
            subprocess.Popen([self.exe_path], cwd=os.path.dirname(self.exe_path), env=env, close_fds=True,
                             creationflags=flags)

    @staticmethod
    def open_download_page():
        webbrowser.open(RELEASES_PAGE)
