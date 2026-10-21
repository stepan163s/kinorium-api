import aiohttp
import asyncio
from yarl import URL
from typing import Any, Dict, Optional, Tuple
from kinorium.exceptions import (
    AuthenticationError,
    NetworkError,
    TimedOutError,
)
from .protocol import (
    canonicalize_and_sign, form_data, normalize_keys, parse_response, post_params,
    raise_for_status,
)


class RequestAsync:
    def __init__(
        self,
        client: Any,
        api_salt: str,
        base_url: str,
        user_agent: str,
        auth: Optional[str] = None,
        phpsessid: Optional[str] = None,
        timeout: int = 10,
        session: Optional[aiohttp.ClientSession] = None
    ):
        self._client = client
        self.api_salt = api_salt
        self.base_url = base_url
        self.user_agent = user_agent
        self._timeout = timeout
        self.session = session
        self.auth = auth
        self.phpsessid = phpsessid

    def _normalize_keys(self, obj: dict) -> dict:
        return normalize_keys(obj)

    def _canonicalize_and_sign(self, method: str, params: Optional[Dict[str, Any]] = None) -> Tuple[str, str]:
        return canonicalize_and_sign(method, params, self.api_salt)

    async def _get_session(self) -> aiohttp.ClientSession:
        if self.session is None or self.session.closed:
            headers = {"User-Agent": self.user_agent}
            cookies = {}
            if self.auth:
                cookies["auth"] = self.auth
            if self.phpsessid:
                cookies["PHPSESSID"] = self.phpsessid
            self.session = aiohttp.ClientSession(headers=headers, cookies=cookies)
        return self.session

    async def _handle_response(self, response: aiohttp.ClientResponse) -> Dict[str, Any]:
        text = await response.text()
        if self.session is not None:
            # Remove constructor cookies superseded by scoped Set-Cookie values.
            # Refresh on every response, including cookie rotation outside login.
            for name in ("auth", "PHPSESSID"):
                if name in response.cookies:
                    self.session.cookie_jar.clear(
                        lambda cookie, name=name: cookie.key == name and not cookie["domain"]
                    )
            cookies = self.session.cookie_jar.filter_cookies(response.url)
            for name, attribute in (("auth", "auth"), ("PHPSESSID", "phpsessid")):
                cookie = cookies.get(name)
                if cookie is None:
                    setattr(self, attribute, None)
                elif isinstance(cookie.value, str):
                    setattr(self, attribute, cookie.value or None)
        raise_for_status(response.status, text)
        return parse_response(text)

    async def get(self, api_method: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        canonical_query, key = self._canonicalize_and_sign(api_method, params)
        url = URL(f"{self.base_url}?{canonical_query}&key={key}", encoded=True)
        session = await self._get_session()
        try:
            async with session.get(url, timeout=self._timeout) as response:
                return await self._handle_response(response)
        except asyncio.TimeoutError:
            raise TimedOutError("Request timed out")
        except aiohttp.ClientError as e:
            raise NetworkError(str(e))

    async def post(self, api_method: str, params: Optional[Dict[str, Any]] = None, data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        query = post_params(api_method, params, data)
        canonical_query, key = self._canonicalize_and_sign(api_method, query)
        url = URL(f"{self.base_url}?{canonical_query}&key={key}", encoded=True)
        session = await self._get_session()
        try:
            async with session.post(url, timeout=self._timeout, data=form_data(data)) as response:
                result = await self._handle_response(response)
                if api_method == "userAuth":
                    issued = response.cookies.get("auth")
                    if issued is None or not issued.value:
                        raise AuthenticationError("Server did not issue an auth cookie")
                return result
        except asyncio.TimeoutError:
            raise TimedOutError("Request timed out")
        except aiohttp.ClientError as e:
            raise NetworkError(str(e))

    async def delete(self, api_method: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        canonical_query, key = self._canonicalize_and_sign(api_method, params)
        url = URL(f"{self.base_url}?{canonical_query}&key={key}", encoded=True)
        session = await self._get_session()
        try:
            async with session.delete(url, timeout=self._timeout) as response:
                return await self._handle_response(response)
        except asyncio.TimeoutError:
            raise TimedOutError("Request timed out")
        except aiohttp.ClientError as e:
            raise NetworkError(str(e))

    async def close(self):
        if self.session and not self.session.closed:
            await self.session.close()
