"""Exercise real HTTP serialization, cookies and method dispatch, without Kinorium."""
import asyncio
import hashlib
import json
import threading
import unittest
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit

from kinorium import AuthenticationError, InvalidOptionError, KinoriumClient, KinoriumClientAsync


class WireHandler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def handle_request(self):
        query = urlsplit(self.path).query
        canonical, _, key = query.rpartition('&key=')
        expected = hashlib.md5(('?' + canonical + KinoriumClient.DEFAULT_API_SALT).encode()).hexdigest()
        fields = parse_qs(query, keep_blank_values=True)
        method = fields['method'][0]
        body = parse_qs(self.rfile.read(int(self.headers.get('Content-Length', 0))).decode(), keep_blank_values=True)
        cookies = SimpleCookie(self.headers.get('Cookie', ''))
        headers = []
        if key != expected:
            result = {'key': False}
        elif method == 'userAuth':
            if body.get('password') == ['no-cookie']:
                result = {'resultCode': 0}
            elif body.get('password') == ['wrong']:
                result = {'resultCode': 106, 'resultMessage': 'Wrong credentials'}
            else:
                result = {'resultCode': 0}
                headers = [('auth', 'fresh'), ('PHPSESSID', 'session')]
        elif method == 'rotateSession':
            result = {'resultCode': 0}
            headers = [('auth', 'rotated'), ('PHPSESSID', 'rotated-session')]
        else:
            result = {'resultCode': 0, 'data': {
                'query': {k: v for k, v in fields.items() if k not in ('method', 'key')},
                'body': body, 'verb': self.command,
                'cookie_auth': cookies['auth'].value if 'auth' in cookies else None,
            }}
        encoded = json.dumps(result).encode()
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(encoded)))
        for name, value in headers:
            self.send_header('Set-Cookie', '%s=%s; Path=/' % (name, value))
        self.end_headers()
        self.wfile.write(encoded)

    do_GET = do_POST = do_DELETE = handle_request


VALUES = ('https://example.org/a?b=1&c=2', "a:b;c,d@e!$()*'", 'тест 🎬 + %2F',
          '', None, False, 0, [1, 2], {'a': 'b'})


class TestTransportContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(('localhost', 0), WireHandler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.url = 'http://localhost:%d/' % cls.server.server_port

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()

    def test_sync_wire_values_and_all_http_verbs(self):
        c = KinoriumClient(base_url=self.url)
        try:
            for verb in ('GET', 'POST', 'DELETE'):
                for value in VALUES:
                    with self.subTest(verb=verb, value=value):
                        args = {'data' if verb == 'POST' else 'params': {'value': value}}
                        data = c.request(verb, 'echo', **args)['data']
                        expected = {'value': ['' if value is None else str(value)]}
                        self.assertEqual(data['query'], expected)
                        self.assertEqual(data['body'], expected if verb == 'POST' else {})
                        self.assertEqual(data['verb'], verb)
        finally:
            c._request._session.close()

    def test_async_wire_values_and_all_http_verbs(self):
        async def check():
            c = KinoriumClientAsync(base_url=self.url)
            try:
                for verb in ('GET', 'POST', 'DELETE'):
                    for value in VALUES:
                        with self.subTest(verb=verb, value=value):
                            args = {'data' if verb == 'POST' else 'params': {'value': value}}
                            data = (await c.request(verb, 'echo', **args))['data']
                            expected = {'value': ['' if value is None else str(value)]}
                            self.assertEqual(data['query'], expected)
                            self.assertEqual(data['body'], expected if verb == 'POST' else {})
                            self.assertEqual(data['verb'], verb)
            finally:
                await c.close()
        asyncio.run(check())

    def test_sync_old_cookie_cannot_mask_missing_login_cookie(self):
        c = KinoriumClient(base_url=self.url, auth='old')
        try:
            for password in ('no-cookie', 'wrong'):
                with self.subTest(password=password), self.assertRaises(AuthenticationError):
                    c.authenticate('test@example.com', password)
        finally:
            c._request._session.close()

    def test_async_old_cookie_cannot_mask_missing_login_cookie(self):
        async def check():
            c = KinoriumClientAsync(base_url=self.url, auth='old')
            try:
                for password in ('no-cookie', 'wrong'):
                    with self.subTest(password=password), self.assertRaises(AuthenticationError):
                        await c.authenticate('test@example.com', password)
            finally:
                await c.close()
        asyncio.run(check())

    def test_sync_cookie_rotation(self):
        c = KinoriumClient(base_url=self.url)
        try:
            c.authenticate('test@example.com', 'ok')
            c.request('GET', 'rotateSession')
            self.assertEqual(c.auth_cookie, 'rotated')
            self.assertEqual(c.phpsessid_cookie, 'rotated-session')
            self.assertEqual(c.request('GET', 'echo')['data']['cookie_auth'], 'rotated')
        finally:
            c._request._session.close()

    def test_async_cookie_rotation_survives_session_reopening(self):
        async def check():
            c = KinoriumClientAsync(base_url=self.url)
            try:
                await c.authenticate('test@example.com', 'ok')
                await c.request('GET', 'rotateSession')
                self.assertEqual(c.auth_cookie, 'rotated')
                self.assertEqual(c.phpsessid_cookie, 'rotated-session')
                await c.close()
                await c.close()
                self.assertEqual((await c.request('GET', 'echo'))['data']['cookie_auth'], 'rotated')
            finally:
                await c.close()
        asyncio.run(check())

    def test_sync_rejects_ignored_data_and_unsupported_status(self):
        c = KinoriumClient(base_url=self.url)
        try:
            for verb in ('GET', 'DELETE'):
                with self.subTest(verb=verb), self.assertRaises(InvalidOptionError):
                    c.request(verb, 'echo', data={'movie_id': 123})
            with self.assertRaises(InvalidOptionError):
                c.set_movie_status(123, 'now')
        finally:
            c._request._session.close()

    def test_async_rejects_ignored_data_and_unsupported_status(self):
        async def check():
            c = KinoriumClientAsync(base_url=self.url)
            try:
                for verb in ('GET', 'DELETE'):
                    with self.subTest(verb=verb), self.assertRaises(InvalidOptionError):
                        await c.request(verb, 'echo', data={'movie_id': 123})
                with self.assertRaises(InvalidOptionError):
                    await c.set_movie_status(123, 'now')
            finally:
                await c.close()
        asyncio.run(check())
