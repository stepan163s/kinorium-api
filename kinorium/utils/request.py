import requests
from typing import Any, Dict, Optional, Tuple
from kinorium.exceptions import (
    AuthenticationError,
    NetworkError,
    TimedOutError,
)
from .protocol import (
    canonicalize_and_sign, extract_error, form_data, normalize_keys, parse_response,
    post_params, raise_for_status,
)


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
        self._response_auth_issued = False
        self._session = requests.Session()
        self._session.headers.update({
            "User-Agent": user_agent
        })
        if auth:
            self._session.cookies.set("auth", auth)
        if phpsessid:
            self._session.cookies.set("PHPSESSID", phpsessid)

    def _normalize_keys(self, obj: dict) -> dict:
        return normalize_keys(obj)

    def _canonicalize_and_sign(self, method: str, params: Optional[Dict[str, Any]] = None) -> Tuple[str, str]:
        return canonicalize_and_sign(method, params, self.api_salt)

    def get(self, api_method: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        canonical_query, key = self._canonicalize_and_sign(api_method, params)
        url = f"{self.base_url}?{canonical_query}&key={key}"
        content = self._request_wrapper('GET', url)
        return self._parse(content)

    def post(self, api_method: str, params: Optional[Dict[str, Any]] = None, data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        query = post_params(api_method, params, data)
        canonical_query, key = self._canonicalize_and_sign(api_method, query)
        url = f"{self.base_url}?{canonical_query}&key={key}"
        self._response_auth_issued = False
        content = self._request_wrapper('POST', url, data=form_data(data))
        result = self._parse(content)
        if api_method == "userAuth" and not self._response_auth_issued:
            raise AuthenticationError("Server did not issue an auth cookie")
        return result

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

        raise_for_status(resp.status_code, resp.content)
        self._response_auth_issued = any(c.name == "auth" and bool(c.value) for c in resp.cookies)
        # Constructor cookies have no domain. Once the server issues a scoped
        # replacement, remove the old unscoped cookie to avoid sending both or
        # raising CookieConflictError when the client reads the new session.
        for issued in resp.cookies:
            if issued.name in ("auth", "PHPSESSID") and issued.domain:
                for old in list(self._session.cookies):
                    if old.name == issued.name and not old.domain:
                        self._session.cookies.clear(old.domain, old.path, old.name)
        return resp.content

    def _extract_error(self, content: bytes) -> str:
        return extract_error(content)

    def _parse(self, content: bytes) -> Dict[str, Any]:
        return parse_response(content)
