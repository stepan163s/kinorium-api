"""Regression checks discovered during the full API audit (no live requests)."""
from __future__ import annotations

import asyncio
import dataclasses
import unittest
from typing import Any, List, Optional
from unittest.mock import AsyncMock, MagicMock, patch

import requests
import aiohttp

from kinorium import KinoriumClient, KinoriumClientAsync
from kinorium.base import BaseModel
from kinorium.exceptions import (
    ApiError, AuthenticationError, BadRequestError, InvalidKeyError,
    InvalidOptionError, KinoriumAPIError, KinoriumError, NetworkError,
    NotFoundError, TimedOutError, UnauthorizedError,
)
from kinorium.models import Movie, User
from kinorium.utils import model


@model
class NestedMovies(BaseModel):
    movie: Optional[Movie] = None
    movies: List[Movie] = dataclasses.field(default_factory=list)
    client: Any = None


class TestExtendedContract(unittest.TestCase):
    def setUp(self):
        self.sync = KinoriumClient()
        self.addCleanup(self.sync._request._session.close)

    def response(self, status, body):
        response = requests.Response()
        response.status_code = status
        response._content = body
        return response

    def async_response(self, status, body):
        response = MagicMock()
        response.status = status
        response.text = AsyncMock(return_value=body)
        return response

    def test_user_accepts_real_profile_field_names(self):
        user = User.de_json({"user_id": "123", "name": "Test", "image": "avatar.png"})
        self.assertEqual(str(user.id_), "123")
        self.assertEqual(user.avatar, "avatar.png")

    def test_movie_preserves_real_api_title(self):
        movie = Movie.de_json({"id_": 123, "name": "Test film", "year": "2020",
                               "genre_list": [{"id_": "1", "name": "Drama"}]})
        self.assertEqual(movie.title, "Test film")
        self.assertEqual(movie.genres, ["Drama"])
        self.assertEqual(movie.year, 2020)

    def test_nested_models_with_postponed_annotations(self):
        nested = NestedMovies.de_json({"movie": {"id_": 1}, "movies": [{"id_": 2}]})
        self.assertIsInstance(nested.movie, Movie)
        self.assertIsInstance(nested.movies[0], Movie)
        self.assertEqual(NestedMovies.de_json({"movies": []}).movies, [])

    def test_models_accept_envelope_and_keep_canonical_fields(self):
        user = User.de_json({"result_code": 0, "data": {
            "user_id": "123", "image": "image.png", "avatar": "canonical.png",
        }})
        self.assertEqual(user.id_, 123)
        self.assertEqual(user.avatar, "canonical.png")
        movie = Movie.de_json({"resultCode": 0, "data": {
            "id": "456", "name": "Film", "year": None, "genre_list": [],
        }})
        self.assertEqual(movie.id_, 456)
        self.assertEqual(movie.title, "Film")
        self.assertEqual(movie.genres, [])
        self.assertEqual(movie.year, 0)

    def test_post_rejects_conflicting_parameters_without_sending(self):
        with patch.object(self.sync._request._session, "request") as send:
            with self.assertRaises(InvalidOptionError):
                self.sync.request("POST", "setMovieStatus", params={"movie_id": 1}, data={"movie_id": 2})
            send.assert_not_called()
        async def check():
            client = KinoriumClientAsync()
            with patch.object(client._request, "_get_session", new=AsyncMock()) as session:
                with self.assertRaises(InvalidOptionError):
                    await client.request("POST", "setMovieStatus", params={"movie_id": 1}, data={"movie_id": 2})
                session.assert_not_called()
        asyncio.run(check())

    def test_success_response_without_auth_cookie_is_not_a_login(self):
        with patch.object(self.sync._request, "post", return_value={"result_code": 0}):
            with self.assertRaises(AuthenticationError):
                self.sync.authenticate("test@example.com", "fake-password")
        async def check():
            client = KinoriumClientAsync()
            with patch.object(client._request, "post", new=AsyncMock(return_value={"result_code": 0})):
                with self.assertRaises(AuthenticationError):
                    await client.authenticate("test@example.com", "fake-password")
        asyncio.run(check())

    def test_sync_http_errors(self):
        for status, error in [(400, BadRequestError), (401, UnauthorizedError),
                              (403, UnauthorizedError), (404, NotFoundError),
                              (405, NetworkError), (429, NetworkError), (500, NetworkError)]:
            with self.subTest(status=status), patch.object(
                self.sync._request._session, "request",
                return_value=self.response(status, b'{"message":"failure"}')
            ), self.assertRaises(error):
                self.sync.get_user_info()

    def test_async_http_errors(self):
        async def check():
            client = KinoriumClientAsync()
            for status, error in [(400, BadRequestError), (401, UnauthorizedError),
                                  (403, UnauthorizedError), (404, NotFoundError),
                                  (405, NetworkError), (429, NetworkError), (500, NetworkError)]:
                with self.subTest(status=status), self.assertRaises(error):
                    await client._request._handle_response(
                        self.async_response(status, '{"message":"failure"}'))
        asyncio.run(check())

    def test_sync_network_errors(self):
        for cause, error in [(requests.Timeout(), TimedOutError),
                             (requests.ConnectionError(), NetworkError)]:
            with self.subTest(error=error.__name__), patch.object(
                self.sync._request._session, "request", side_effect=cause
            ), self.assertRaises(error):
                self.sync.get_user_info()

    def test_async_network_errors(self):
        async def check():
            for cause, error in [(asyncio.TimeoutError(), TimedOutError),
                                 (aiohttp.ClientConnectionError(), NetworkError)]:
                client = KinoriumClientAsync()
                session = MagicMock()
                session.closed = False
                session.get.side_effect = cause
                client._request.session = session
                with self.subTest(error=error.__name__), self.assertRaises(error):
                    await client.get_user_info()
        asyncio.run(check())

    def test_async_api_result_code(self):
        async def check():
            client = KinoriumClientAsync()
            with self.assertRaises(KinoriumAPIError) as caught:
                await client._request._handle_response(self.async_response(
                    200, '{"resultCode":106,"resultMessage":"Wrong credentials"}'))
            self.assertEqual(caught.exception.result_code, 106)
        asyncio.run(check())

    def test_websocket_signing_matches_between_clients(self):
        self.assertEqual(self.sync.sign_websocket("1437056"),
                         KinoriumClientAsync().sign_websocket("1437056"))

    def test_sync_authentication_wraps_api_error(self):
        with patch.object(self.sync._request, "post",
                          side_effect=KinoriumAPIError(106, "Wrong credentials")):
            with self.assertRaises(AuthenticationError):
                self.sync.authenticate("test@example.com", "fake-password")

    def test_async_authentication_wraps_api_error(self):
        async def check():
            client = KinoriumClientAsync()
            with patch.object(client._request, "post", new=AsyncMock(
                side_effect=KinoriumAPIError(106, "Wrong credentials")
            )), self.assertRaises(AuthenticationError):
                await client.authenticate("test@example.com", "fake-password")
        asyncio.run(check())

    def test_legacy_error_catches_library_errors(self):
        self.assertTrue(issubclass(UnauthorizedError, KinoriumError))

    def test_sync_delete_accepts_empty_204(self):
        with patch.object(self.sync._request._session, "request",
                          return_value=self.response(204, b"")):
            self.assertEqual(self.sync.request("DELETE", "testDelete"), {})

    def test_async_delete_accepts_empty_204(self):
        async def check():
            client = KinoriumClientAsync()
            session = MagicMock()
            session.closed = False
            session.delete.return_value.__aenter__ = AsyncMock(
                return_value=self.async_response(204, ""))
            client._request.session = session
            self.assertEqual(await client.request("DELETE", "testDelete"), {})
        asyncio.run(check())

    def test_sync_invalid_json_raises_library_error(self):
        with self.assertRaises(ApiError):
            self.sync._request._parse(b"<html>Service unavailable</html>")

    def test_async_invalid_json_raises_library_error(self):
        async def check():
            client = KinoriumClientAsync()
            with self.assertRaises(ApiError):
                await client._request._handle_response(
                    self.async_response(200, "<html>Service unavailable</html>"))
        asyncio.run(check())

    def test_sync_rejects_unknown_http_verb(self):
        with patch.object(self.sync._request, "get"), self.assertRaises(InvalidOptionError):
            self.sync.request("NOT_A_METHOD", "getUserInfo")

    def test_async_rejects_unknown_http_verb(self):
        async def check():
            client = KinoriumClientAsync()
            with patch.object(client._request, "get", new=AsyncMock()), self.assertRaises(InvalidOptionError):
                await client.request("NOT_A_METHOD", "getUserInfo")
        asyncio.run(check())

    def test_async_rejects_bad_signature(self):
        async def check():
            client = KinoriumClientAsync()
            with self.assertRaises(InvalidKeyError):
                await client._request._handle_response(
                    self.async_response(200, '{"key":false}'))
        asyncio.run(check())
