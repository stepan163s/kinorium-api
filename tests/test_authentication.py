import asyncio
import hashlib
import json
import threading
import unittest
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit

from kinorium import KinoriumClient, KinoriumClientAsync


EMAIL = "test+login@example.com"
PASSWORD = "test &+password=123"


class AuthHandler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def respond(self, payload, status=200, cookies=False):
        body = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        if cookies:
            self.send_header("Set-Cookie", "auth=test-auth; Path=/")
            self.send_header("Set-Cookie", "PHPSESSID=test-session; Path=/")
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        body = self.rfile.read(int(self.headers.get("Content-Length", 0)))
        content_type = self.headers.get("Content-Type")
        query_string = urlsplit(self.path).query
        query = parse_qs(query_string, keep_blank_values=True)
        method = query.get("method", [None])[0]
        signed, _, signature = query_string.rpartition("&key=")
        expected = hashlib.md5(
            ("?" + signed + KinoriumClient.DEFAULT_API_SALT).encode()
        ).hexdigest()
        if signature != expected:
            self.respond({"key": False})
            return
        if method == "userAuth":
            fields = parse_qs(body.decode())
            if content_type != "application/x-www-form-urlencoded" or fields != {
                "email": [EMAIL], "password": [PASSWORD]
            } or "email" in query or "password" in query:
                self.respond({"message": "Expected form credentials"}, status=400)
                return
            self.respond({"resultCode": 0, "data": {"user_id": 123}}, cookies=True)
        else:
            fields = parse_qs(body.decode(), keep_blank_values=True)
            if any(query.get(key) != value for key, value in fields.items()):
                self.respond({"message": "Unsigned body parameters"}, status=403)
                return
            query.pop("key")
            self.respond({"resultCode": 0, "data": {
                "content_type": content_type, "payload": fields, "query": query
            }})

    def do_DELETE(self):
        self.respond({"message": "Method not allowed"}, status=405)

    def do_GET(self):
        cookies = SimpleCookie(self.headers.get("Cookie", ""))
        auth = cookies.get("auth")
        if auth is None or auth.value != "test-auth":
            self.respond({"message": "Unauthorized"}, status=401)
            return
        self.respond({"resultCode": 0, "data": {"user_id": 123}})


class TestAuthentication(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(("localhost", 0), AuthHandler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base_url = "http://localhost:%d/" % cls.server.server_port

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()

    def test_sync_login_sends_form_and_exposes_usable_cookies(self):
        client = KinoriumClient(base_url=self.base_url)
        try:
            result = client.authenticate(EMAIL, PASSWORD)
            self.assertEqual(result["data"]["user_id"], 123)
            self.assertEqual(client.auth_cookie, "test-auth")
            self.assertEqual(client.phpsessid_cookie, "test-session")
            self.assertEqual(client.get_user_info()["data"]["user_id"], 123)
        finally:
            client._request._session.close()

    def test_sync_login_replaces_old_session_cookies(self):
        client = KinoriumClient(base_url=self.base_url, auth="old-auth", phpsessid="old-session")
        try:
            client.authenticate(EMAIL, PASSWORD)
            self.assertEqual(client.auth_cookie, "test-auth")
            self.assertEqual(client.phpsessid_cookie, "test-session")
            self.assertEqual(client.get_user_info()["data"]["user_id"], 123)
            self.assertEqual(sum(c.name == "auth" for c in client._request._session.cookies), 1)
        finally:
            client._request._session.close()

    def test_async_login_replaces_old_session_cookies(self):
        async def check():
            client = KinoriumClientAsync(base_url=self.base_url, auth="old-auth", phpsessid="old-session")
            try:
                await client.authenticate(EMAIL, PASSWORD)
                self.assertEqual(client.auth_cookie, "test-auth")
                self.assertEqual(client.phpsessid_cookie, "test-session")
                self.assertEqual((await client.get_user_info())["data"]["user_id"], 123)
            finally:
                await client.close()
        asyncio.run(check())

    def test_async_login_sends_form_and_exposes_usable_cookies(self):
        async def check():
            client = KinoriumClientAsync(base_url=self.base_url)
            try:
                result = await client.authenticate(EMAIL, PASSWORD)
                self.assertEqual(result["data"]["user_id"], 123)
                self.assertEqual(client.auth_cookie, "test-auth")
                self.assertEqual(client.phpsessid_cookie, "test-session")
                profile = await client.get_user_info()
                self.assertEqual(profile["data"]["user_id"], 123)
            finally:
                await client.close()
        asyncio.run(check())

    def test_sync_post_signs_data_and_preserves_params(self):
        client = KinoriumClient(base_url=self.base_url)
        try:
            result = client.request("POST", "otherMethod", params={"page": 2}, data={"value": "a &+b/?"})
            self.assertEqual(result["data"], {
                "content_type": "application/x-www-form-urlencoded",
                "payload": {"value": ["a &+b/?"]},
                "query": {"method": ["otherMethod"], "page": ["2"], "value": ["a &+b/?"]},
            })
        finally:
            client._request._session.close()

    def test_async_post_signs_data_and_preserves_params(self):
        async def check():
            client = KinoriumClientAsync(base_url=self.base_url)
            try:
                result = await client.request("POST", "otherMethod", params={"page": 2}, data={"value": "a &+b/?"})
                self.assertEqual(result["data"], {
                    "content_type": "application/x-www-form-urlencoded",
                    "payload": {"value": ["a &+b/?"]},
                    "query": {"method": ["otherMethod"], "page": ["2"], "value": ["a &+b/?"]},
                })
            finally:
                await client.close()
        asyncio.run(check())

    def test_sync_status_helpers_and_legacy_delete_use_post(self):
        client = KinoriumClient(base_url=self.base_url)
        try:
            result = client.set_movie_status(123, "future")
            self.assertEqual(result["data"]["query"]["status"], ["future"])
            for result in (client.remove_movie_status(123),
                           client.request("DELETE", "removeMovieStatus", params={"movie_id": 123}),
                           client.request("DELETE", "removeMovieStatus", data={"movie_id": 123})):
                self.assertEqual(result["data"]["query"], {
                    "method": ["removeMovieStatus"], "movie_id": ["123"], "type_": ["status"],
                })
        finally:
            client._request._session.close()

    def test_async_status_helpers_and_legacy_delete_use_post(self):
        async def check():
            client = KinoriumClientAsync(base_url=self.base_url)
            try:
                result = await client.set_movie_status(123, "future")
                self.assertEqual(result["data"]["query"]["status"], ["future"])
                for result in (await client.remove_movie_status(123),
                               await client.request("DELETE", "removeMovieStatus", params={"movie_id": 123}),
                               await client.request("DELETE", "removeMovieStatus", data={"movie_id": 123})):
                    self.assertEqual(result["data"]["query"], {
                        "method": ["removeMovieStatus"], "movie_id": ["123"], "type_": ["status"],
                    })
            finally:
                await client.close()
        asyncio.run(check())
