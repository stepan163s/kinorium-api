# ============================================================
# ВНИМАНИЕ: этот файл сгенерирован автоматически.
# Источник: kinorium/client.py
# Команда:  python generate_async_version.py
# ============================================================

import hashlib
from typing import Dict, Any, Optional
from kinorium.utils.request_async import RequestAsync as Request
from kinorium.exceptions import KinoriumError, AuthenticationError

class KinoriumClientAsync:
    DEFAULT_BASE_URL = "https://api.kinorium.com/1.0.3/"
    DEFAULT_USER_AGENT = "Kinorium/1.56.0 (Android 16)"
    DEFAULT_API_SALT = "Sole8dya$ovbDi9I$adta"
    DEFAULT_WS_SALT = "SlozhnaYa$altDl9IBadiMa"

    _is_async: bool = True

    def __init__(
        self,
        auth: Optional[str] = None,
        phpsessid: Optional[str] = None,
        api_salt: str = DEFAULT_API_SALT,
        ws_salt: str = DEFAULT_WS_SALT,
        base_url: str = DEFAULT_BASE_URL,
        user_agent: str = DEFAULT_USER_AGENT,
        _request_instance: Optional[Request] = None
    ):
        self.api_salt = api_salt
        self.ws_salt = ws_salt
        self.base_url = base_url
        self._request = _request_instance or Request(
            client=self,
            api_salt=api_salt,
            base_url=base_url,
            user_agent=user_agent,
            auth=auth,
            phpsessid=phpsessid
        )

    @property
    def auth_cookie(self) -> Optional[str]:
        if hasattr(self._request, "auth") and self._request.auth:
            return self._request.auth
        if hasattr(self._request, "_session") and self._request._session:
            if hasattr(self._request._session, "cookies"):
                return self._request._session.cookies.get("auth")
        return None

    @property
    def phpsessid_cookie(self) -> Optional[str]:
        if hasattr(self._request, "phpsessid") and self._request.phpsessid:
            return self._request.phpsessid
        if hasattr(self._request, "_session") and self._request._session:
            if hasattr(self._request._session, "cookies"):
                return self._request._session.cookies.get("PHPSESSID")
        return None

    async def request(self, http_method: str, api_method: str, params: Optional[Dict[str, Any]] = None, data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Sends a signed request to the Kinorium API.
        """
        if http_method.upper() == "POST":
            return await self._request.post(api_method, params=params, data=data)
        elif http_method.upper() == "DELETE":
            return await self._request.delete(api_method, params=params)
        else:
            return await self._request.get(api_method, params=params)

    async def authenticate(self, email: str, password: str) -> Dict[str, Any]:
        """
        Authenticates a user with email and password using the userAuth method.
        """
        data = {
            "email": email,
            "password": password
        }
        try:
            res = await self._request.post("userAuth", data=data)
            return res
        except KinoriumError as e:
            raise AuthenticationError(f"Authentication failed: {e}") from e

    async def get_user_info(self, user_id: int = 0) -> Dict[str, Any]:
        """
        Fetches user profile data. Works for public profile data.
        """
        return await self._request.get("getUserInfo", params={"user_id": user_id})

    async def get_user_lists(self, user_id: int = 0) -> Dict[str, Any]:
        """
        Fetches user lists metadata (e.g. Watchlist, Favorite, custom lists).
        """
        params = {
            "user_id": user_id,
            "obj_ids": "",
            "page": 1,
            "perpage": 1000
        }
        return await self._request.get("getUList", params=params)

    async def get_user_list_objects(self, ulist_id: int, page: int = 1, perpage: int = 50) -> Dict[str, Any]:
        """
        Fetches data for a user list.
        """
        params = {
            "ulist_id": ulist_id,
            "page": page,
            "perpage": perpage
        }
        return await self._request.get("getUListObj", params=params)

    def sign_websocket(self, user_id: str) -> str:
        """
        Calculates the WebSocket signature for a given user_id.
        """
        sign_input = f"{user_id}{self.ws_salt}"
        return hashlib.md5(sign_input.encode("utf-8")).hexdigest()

    async def close(self):
        """Close the client session."""
        await self._request.close()
