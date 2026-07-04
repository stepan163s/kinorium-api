import json
import re
import requests
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


class Request:
    def __init__(
        self,
        client: Any,
        api_salt: str,
        base_url: str,
        user_agent: str,
        auth: Optional[str] = None,
        phpsessid: Optional[str] = None,
        timeout: int = 10
    ):
        self._client = client
        self.api_salt = api_salt
        self.base_url = base_url
        self.user_agent = user_agent
        self._timeout = timeout
        self._session = requests.Session()
        self._session.headers.update({
            "User-Agent": user_agent
        })
        if auth:
            self._session.cookies.set("auth", auth)
        if phpsessid:
            self._session.cookies.set("PHPSESSID", phpsessid)

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

    def get(self, api_method: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        canonical_query, key = self._canonicalize_and_sign(api_method, params)
        url = f"{self.base_url}?{canonical_query}&key={key}"
        content = self._request_wrapper('GET', url)
        return self._parse(content)

    def post(self, api_method: str, params: Optional[Dict[str, Any]] = None, data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        canonical_query, key = self._canonicalize_and_sign(api_method, params)
        url = f"{self.base_url}?{canonical_query}&key={key}"
        content = self._request_wrapper('POST', url, json=data)
        return self._parse(content)

    def delete(self, api_method: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        canonical_query, key = self._canonicalize_and_sign(api_method, params)
        url = f"{self.base_url}?{canonical_query}&key={key}"
        content = self._request_wrapper('DELETE', url)
        if not content:
            return {}
        return self._parse(content)

    def _request_wrapper(self, method: str, url: str, **kwargs) -> bytes:
        kwargs.setdefault('timeout', self._timeout)
        try:
            resp = self._session.request(method, url, **kwargs)
        except requests.Timeout as exc:
            raise TimedOutError(f"Request timed out ({self._timeout}s)") from exc
        except requests.ConnectionError as exc:
            raise NetworkError(f"Connection error: {exc}") from exc
        except requests.RequestException as exc:
            raise NetworkError(str(exc)) from exc

        if not (200 <= resp.status_code <= 299):
            message = self._extract_error(resp.content)
            if resp.status_code in (401, 403):
                raise UnauthorizedError(message)
            if resp.status_code == 400:
                raise BadRequestError(message)
            if resp.status_code == 404:
                raise NotFoundError(message)
            raise NetworkError(f"HTTP {resp.status_code}: {message}")

        return resp.content

    def _extract_error(self, content: bytes) -> str:
        try:
            data = json.loads(content)
            return data.get('message') or data.get('error') or 'Unknown error'
        except Exception:
            return content.decode('utf-8', errors='replace') or 'Unknown error'

    def _parse(self, content: bytes) -> Dict[str, Any]:
        if not content:
            return {}
        json_data = json.loads(content, object_hook=self._normalize_keys)
        
        if isinstance(json_data, dict) and json_data.get("key") is False:
            raise InvalidKeyError()
            
        if isinstance(json_data, dict) and "result_code" in json_data:
            rc = json_data.get("result_code")
            if rc != 0:
                rm = json_data.get("result_message", "Unknown API error")
                raise KinoriumAPIError(rc, rm)
                
        return json_data
