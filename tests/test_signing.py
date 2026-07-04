import hashlib
import unittest
from unittest.mock import MagicMock, patch
import requests
from kinorium import KinoriumClient, InvalidKeyError, KinoriumAPIError, AuthenticationError


class TestKinoriumSigning(unittest.TestCase):
    def setUp(self):
        self.client = KinoriumClient()

    def test_normal_signing_vector_1(self):
        # ?method=userAuth
        # => 77cb7d6ad06161f7923cc74c0fd88466
        canonical_query, key = self.client._request._canonicalize_and_sign("userAuth")
        self.assertEqual(canonical_query, "method=userAuth")
        self.assertEqual(key, "77cb7d6ad06161f7923cc74c0fd88466")

    def test_normal_signing_vector_2(self):
        # ?method=getUserInfo&user_id=1437056
        # => 1d632c88e2b4114aff633a9737741ae2
        canonical_query, key = self.client._request._canonicalize_and_sign("getUserInfo", {"user_id": 1437056})
        self.assertEqual(canonical_query, "method=getUserInfo&user_id=1437056")
        self.assertEqual(key, "1d632c88e2b4114aff633a9737741ae2")

    def test_normal_signing_vector_3(self):
        # ?method=getUList&user_id=0&obj_ids=&page=1&perpage=1000
        # => 478cc9984f5940e8ab9d64d08b4abe20
        canonical_query, key = self.client._request._canonicalize_and_sign(
            "getUList",
            {"user_id": 0, "obj_ids": "", "page": 1, "perpage": 1000}
        )
        self.assertEqual(canonical_query, "method=getUList&user_id=0&obj_ids=&page=1&perpage=1000")
        self.assertEqual(key, "478cc9984f5940e8ab9d64d08b4abe20")

    def test_websocket_signer_vector(self):
        # signWs("1437056") => aeee25a24d3d2ebb4128fcddda0dc956
        ws_key = self.client.sign_websocket("1437056")
        self.assertEqual(ws_key, "aeee25a24d3d2ebb4128fcddda0dc956")

    def test_canonicalization_replacements(self):
        params = {
            "title": "A B",
            "url": "http://example.com/test?param=1"
        }
        canonical_query, _ = self.client._request._canonicalize_and_sign("testMethod", params)
        self.assertIn("title=A%20B", canonical_query)
        self.assertIn("url=http%3A//example.com/test?param%3D1", canonical_query)

    def test_custom_salts_and_base_url(self):
        custom_client = KinoriumClient(
            api_salt="CustomApiSalt123",
            ws_salt="CustomWsSalt456",
            base_url="https://custom-api.example.com/",
            user_agent="CustomUserAgent/1.0"
        )
        # Test custom API signature calculation
        canonical, key = custom_client._request._canonicalize_and_sign("test")
        self.assertEqual(canonical, "method=test")
        expected_key = hashlib.md5(b"?method=testCustomApiSalt123").hexdigest()
        self.assertEqual(key, expected_key)

        # Test custom WebSocket signing
        expected_ws_key = hashlib.md5(b"999CustomWsSalt456").hexdigest()
        self.assertEqual(custom_client.sign_websocket("999"), expected_ws_key)
        
        # Test headers
        self.assertEqual(custom_client._request._session.headers.get("User-Agent"), "CustomUserAgent/1.0")


class TestKinoriumClientRequests(unittest.TestCase):
    @patch("requests.Session.request")
    def test_get_request_correct_url(self, mock_request):
        mock_response = MagicMock()
        mock_response.json.return_value = {"resultCode": 0, "data": {}}
        mock_response.content = b'{"resultCode": 0, "data": {}}'
        mock_response.status_code = 200
        mock_request.return_value = mock_response

        client = KinoriumClient()
        client.get_user_info(user_id=1437056)

        expected_url = (
            "https://api.kinorium.com/1.0.3/"
            "?method=getUserInfo&user_id=1437056"
            "&key=1d632c88e2b4114aff633a9737741ae2"
        )
        mock_request.assert_called_once_with('GET', expected_url, timeout=10)

    @patch("requests.Session.request")
    def test_custom_base_url_request(self, mock_request):
        mock_response = MagicMock()
        mock_response.json.return_value = {"resultCode": 0, "data": {}}
        mock_response.content = b'{"resultCode": 0, "data": {}}'
        mock_response.status_code = 200
        mock_request.return_value = mock_response

        client = KinoriumClient(
            api_salt="CustomSalt",
            base_url="https://alt-api.kinorium.com/v2/"
        )
        client.get_user_info(user_id=100)

        expected_key = hashlib.md5(b"?method=getUserInfo&user_id=100CustomSalt").hexdigest()
        expected_url = f"https://alt-api.kinorium.com/v2/?method=getUserInfo&user_id=100&key={expected_key}"
        mock_request.assert_called_once_with('GET', expected_url, timeout=10)

    @patch("requests.Session.request")
    def test_post_request_signing_and_body(self, mock_request):
        mock_response = MagicMock()
        mock_response.json.return_value = {"resultCode": 0, "data": {"user": "test"}}
        mock_response.content = b'{"resultCode": 0, "data": {"user": "test"}}'
        mock_response.status_code = 200
        mock_request.return_value = mock_response

        client = KinoriumClient()
        client.authenticate("test@example.com", "pass123")

        expected_url = (
            "https://api.kinorium.com/1.0.3/"
            "?method=userAuth"
            "&key=77cb7d6ad06161f7923cc74c0fd88466"
        )
        mock_request.assert_called_once_with(
            'POST',
            expected_url,
            json={"email": "test@example.com", "password": "pass123"},
            timeout=10
        )

    @patch("requests.Session.request")
    def test_invalid_key_error(self, mock_request):
        mock_response = MagicMock()
        mock_response.json.return_value = {"key": False}
        mock_response.content = b'{"key": false}'
        mock_response.status_code = 200
        mock_request.return_value = mock_response

        client = KinoriumClient()
        with self.assertRaises(InvalidKeyError):
            client.get_user_info(user_id=123)

    @patch("requests.Session.request")
    def test_api_result_code_error(self, mock_request):
        mock_response = MagicMock()
        mock_response.json.return_value = {"resultCode": 106, "resultMessage": "Wrong login details"}
        mock_response.content = b'{"resultCode": 106, "resultMessage": "Wrong login details"}'
        mock_response.status_code = 200
        mock_request.return_value = mock_response

        client = KinoriumClient()
        with self.assertRaises(KinoriumAPIError) as ctx:
            client.get_user_info(user_id=123)
        self.assertEqual(ctx.exception.result_code, 106)
        self.assertEqual(ctx.exception.result_message, "Wrong login details")

    def test_cookie_setup(self):
        client = KinoriumClient(auth="myauth", phpsessid="mysessid")
        self.assertEqual(client.auth_cookie, "myauth")
        self.assertEqual(client.phpsessid_cookie, "mysessid")
        self.assertEqual(client._request._session.cookies.get("auth"), "myauth")
        self.assertEqual(client._request._session.cookies.get("PHPSESSID"), "mysessid")

    @patch("requests.Session.request")
    def test_generic_request(self, mock_request):
        mock_response = MagicMock()
        mock_response.json.return_value = {"resultCode": 0, "data": {"movie": "Inception"}}
        mock_response.content = b'{"resultCode": 0, "data": {"movie": "Inception"}}'
        mock_response.status_code = 200
        mock_request.return_value = mock_response

        client = KinoriumClient()
        result = client.request("GET", "getMovie", params={"id": 12345})

        expected_key = hashlib.md5(b"?method=getMovie&id=12345Sole8dya$ovbDi9I$adta").hexdigest()
        expected_url = f"https://api.kinorium.com/1.0.3/?method=getMovie&id=12345&key={expected_key}"
        mock_request.assert_called_once_with('GET', expected_url, timeout=10)
        self.assertEqual(result["data"]["movie"], "Inception")
