"""Credentials stay in local configuration, not tracked Python source."""
import contextlib
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import MagicMock, patch

import get_session
from kinorium import AuthenticationError


class TestLocalCredentials(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.path = Path(temp.name) / 'get_session.local.json'
        self.environment = patch.dict(os.environ, {}, clear=True)
        self.environment.start()
        self.addCleanup(self.environment.stop)
        self.local = patch.object(get_session, 'LOCAL_CREDENTIALS', self.path)
        self.local.start()
        self.addCleanup(self.local.stop)

    def test_missing_local_file_allows_interactive_login(self):
        self.assertEqual(get_session.load_credentials(), ('', ''))

    def test_reads_local_json(self):
        self.path.write_text(json.dumps({'email': 'user@example.com', 'password': 'fixture-only'}))
        self.assertEqual(get_session.load_credentials(), ('user@example.com', 'fixture-only'))

    def test_environment_overrides_local_values(self):
        self.path.write_text(json.dumps({'email': 'local@example.com', 'password': 'local-fixture'}))
        with patch.dict(os.environ, {'KINORIUM_EMAIL': 'env@example.com', 'KINORIUM_PASSWORD': 'env-fixture'}):
            self.assertEqual(get_session.load_credentials(), ('env@example.com', 'env-fixture'))

    def test_rejects_non_object_json(self):
        self.path.write_text('[]')
        with self.assertRaises(ValueError):
            get_session.load_credentials()

    def test_rejects_non_string_credentials(self):
        self.path.write_text('{"email":123,"password":null}')
        with self.assertRaises(ValueError):
            get_session.load_credentials()

    def test_interactive_login_uses_hidden_password_prompt_and_closes_session(self):
        client = MagicMock()
        client.auth_cookie = 'fixture-auth'
        with patch.object(get_session, 'KinoriumClient', return_value=client), \
                patch('builtins.input', return_value='user@example.com'), \
                patch.object(get_session.getpass, 'getpass', return_value='fixture-only') as prompt, \
                contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(get_session.main(), 0)
        prompt.assert_called_once()
        client.authenticate.assert_called_once_with('user@example.com', 'fixture-only')
        client._request._session.close.assert_called_once()

    def test_failed_login_returns_nonzero_and_closes_session(self):
        self.path.write_text('{"email":"user@example.com","password":"fixture-only"}')
        client = MagicMock()
        client.authenticate.side_effect = AuthenticationError('Wrong credentials')
        with patch.object(get_session, 'KinoriumClient', return_value=client), \
                contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(get_session.main(), 1)
        client._request._session.close.assert_called_once()
