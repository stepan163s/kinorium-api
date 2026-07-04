import json
import re
import aiohttp
import asyncio
from typing import Any, Dict, Optional, Tuple
import hashlib
import urllib.parse
from kinorium.exceptions import (
    BadRequestError,
    NetworkError,
    NotFoundError,
    TimedOutError,
    UnauthorizedError,
    KinoriumAPIError,
    InvalidKeyError
)

_RESERVED = frozenset({
    'type', 'from', 'import', 'class', 'return', 'pass',
    'in', 'is', 'format', 'filter', 'id', 'input', 'list',
    'dict', 'set', 'max', 'min', 'sum', 'map', 'zip',
})

_CAMEL_RE = re.compile(r'(?<=[a-z0-9])([A-Z])')

def _camel_to_snake(name: str) -> str:
    return _CAMEL_RE.sub(r'_\1', name).lower()


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
        result: dict = {}
        for key, value in obj.items():
            key = key.replace('-', '_')
            key = _camel_to_snake(key)
            key = key.lower()
            if key in _RESERVED:
                key += '_'
            if key and key[0].isdigit():
                key = '_' + key
            result[key] = value
        return result

    def _canonicalize_and_sign(self, method: str, params: Optional[Dict[str, Any]] = None) -> Tuple[str, str]:
        query_items = [("method", method)]
        if params:
            for k, v in params.items():
                if k not in ("method", "key"):
                    val_str = str(v) if v is not None else ""
                    query_items.append((k, val_str))
        encoded = urllib.parse.urlencode(query_items, quote_via=urllib.parse.quote)
        canonical = encoded.replace("+", "%20").replace("%2F", "/").replace("%2f", "/").replace("%3F", "?").replace("%3f", "?")
        sign_input = f"?{canonical}{self.api_salt}"
        key = hashlib.md5(sign_input.encode("utf-8")).hexdigest()
        return canonical, key

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
        if response.status in (401, 403):
            raise UnauthorizedError(f"HTTP {response.status}: Unauthorized")
        elif response.status == 400:
            raise BadRequestError("HTTP 400: Bad Request")
        elif response.status == 404:
            raise NotFoundError("HTTP 404: Not Found")
        elif response.status >= 500:
            raise NetworkError(f"Server error HTTP {response.status}")
            
        text = await response.text()
        try:
            json_data = json.loads(text, object_hook=self._normalize_keys)
        except json.JSONDecodeError:
            raise KinoriumAPIError(-1, f"Failed to parse JSON response: {text}")
            
        if isinstance(json_data, dict) and json_data.get("key") is False:
            raise InvalidKeyError()
            
        if isinstance(json_data, dict) and "result_code" in json_data:
            rc = json_data.get("result_code")
            if rc != 0:
                rm = json_data.get("result_message", "Unknown API error")
                raise KinoriumAPIError(rc, rm)
                
        return json_data

    async def get(self, api_method: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        canonical_query, key = self._canonicalize_and_sign(api_method, params)
        url = f"{self.base_url}?{canonical_query}&key={key}"
        session = await self._get_session()
        try:
            async with session.get(url, timeout=self._timeout) as response:
                return await self._handle_response(response)
        except asyncio.TimeoutError:
            raise TimedOutError("Request timed out")
        except aiohttp.ClientError as e:
            raise NetworkError(str(e))

    async def post(self, api_method: str, params: Optional[Dict[str, Any]] = None, data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        canonical_query, key = self._canonicalize_and_sign(api_method, params)
        url = f"{self.base_url}?{canonical_query}&key={key}"
        session = await self._get_session()
        try:
            async with session.post(url, json=data, timeout=self._timeout) as response:
                return await self._handle_response(response)
        except asyncio.TimeoutError:
            raise TimedOutError("Request timed out")
        except aiohttp.ClientError as e:
            raise NetworkError(str(e))

    async def delete(self, api_method: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        canonical_query, key = self._canonicalize_and_sign(api_method, params)
        url = f"{self.base_url}?{canonical_query}&key={key}"
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
