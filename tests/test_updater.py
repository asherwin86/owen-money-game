"""Run with:  python -m unittest discover -s tests   (uses a fake local server, no internet needed)"""
import hashlib
import http.server
import json
import os
import shutil
import socketserver
import sys
import tempfile
import threading
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import updater as up


class UpdaterTests(unittest.TestCase):
    def test_versions_and_hosts(self):
        self.assertEqual(up.parse_version('v1.2.3'), (1, 2, 3))
        self.assertEqual(up.parse_version('abc'), ())
        self.assertTrue(up.is_newer('v1.10.0', '1.9.9'))
        self.assertFalse(up.is_newer('v1.0.0', '1.0.0'))
        self.assertFalse(up.is_newer('garbage', '1.0.0'))
        self.assertTrue(up._host_ok('https://release-assets.githubusercontent.com/x', up.ALLOWED_HOSTS))
        self.assertFalse(up._host_ok('https://github.com.evil.io/x', up.ALLOWED_HOSTS))
        self.assertFalse(up._host_ok('http://github.com/x', up.ALLOWED_HOSTS))

    def test_check_download_verify_install(self):
        good = b'MZ' + os.urandom(200_000)
        state = dict(payload=good, digest=None, serve=None)

        class H(http.server.BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def do_GET(self):
                if self.path == '/api':
                    digest = state['digest'] or 'sha256:' + hashlib.sha256(state['payload']).hexdigest()
                    body = json.dumps({'tag_name': 'v1.1.0', 'prerelease': False, 'draft': False, 'body': 'Notes',
                                       'assets': [{'name': up.ASSET_NAME, 'size': len(state['payload']), 'digest': digest,
                                                   'browser_download_url': f'http://127.0.0.1:{port}/file'}]}).encode()
                else:
                    body = state['payload'][:state['serve'] or len(state['payload'])]
                self.send_response(200)
                self.send_header('Content-Length', str(len(body)))
                self.end_headers()
                self.wfile.write(body)

        srv = socketserver.TCPServer(('127.0.0.1', 0), H)
        port = srv.server_address[1]
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        folder = tempfile.mkdtemp()
        exe = os.path.join(folder, 'MoneyTycoon3D.exe')
        with open(exe, 'wb') as f:
            f.write(b'MZOLD')

        def make(cur='1.0.0'):
            return up.Updater(cur, api_url=f'http://127.0.0.1:{port}/api', exe_path=exe, frozen=True, allow_http=True)

        try:
            u = make('1.1.0')
            u.check()
            self.assertEqual(u.state, 'none')
            u = make()
            u.check()
            self.assertEqual(u.state, 'available')
            state['digest'] = 'sha256:' + '0' * 64                       # wrong checksum is rejected
            u = make()
            u.check()
            u.download()
            self.assertEqual(u.state, 'failed')
            state['digest'] = None
            state['serve'] = 1000                                        # truncated download is rejected
            u = make()
            u.check()
            u.download()
            self.assertEqual(u.state, 'failed')
            state['serve'] = None
            state['payload'] = b'<html>' + os.urandom(100)               # not an exe is rejected
            u = make()
            u.check()
            u.download()
            self.assertEqual(u.state, 'failed')
            state['payload'] = good
            u = make()
            u.check()
            u.download()
            self.assertEqual(u.state, 'ready')
            u.install(launch=False)
            with open(exe, 'rb') as f:
                self.assertEqual(f.read(), good)
            u.cleanup()
            self.assertFalse(os.path.exists(os.path.join(folder, 'MoneyTycoon3D.old.exe')))
        finally:
            srv.shutdown()
            shutil.rmtree(folder, ignore_errors=True)


if __name__ == '__main__':
    unittest.main()
