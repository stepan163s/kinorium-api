import hashlib
from typing import Dict, Any, Optional
from kinorium.utils.request import Request
from kinorium.exceptions import KinoriumError, AuthenticationError, InvalidOptionError

class KinoriumClient:
    DEFAULT_BASE_URL = "https://api.kinorium.com/1.0.3/"
    DEFAULT_USER_AGENT = "Kinorium/1.56.0 (Android 16)"
    DEFAULT_API_SALT = "Sole8dya$ovbDi9I$adta"
    DEFAULT_WS_SALT = "SlozhnaYa$altDl9IBadiMa"

    _is_async: bool = False

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

    def request(self, http_method: str, api_method: str, params: Optional[Dict[str, Any]] = None, data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Sends a signed request to the Kinorium API.
        """
        verb = http_method.upper()
        if verb not in ("GET", "POST", "DELETE"):
            raise InvalidOptionError(f"Unsupported HTTP method: {http_method}")
        if verb == "DELETE" and api_method == "removeMovieStatus":
            # The server implements this deletion as a signed POST. Omitting
            # type=status returns success without clearing the current status.
            params = dict(params or {})
            if "type" not in params and "type" not in (data or {}):
                params["type"] = "status"
            return self._request.post(api_method, params=params, data=data)
        if verb == "POST":
            return self._request.post(api_method, params=params, data=data)
        if data:
            raise InvalidOptionError("Use params for GET/DELETE; data is supported for POST and DELETE removeMovieStatus")
        if verb == "DELETE":
            return self._request.delete(api_method, params=params)
        else:
            return self._request.get(api_method, params=params)

    def authenticate(self, email: str, password: str) -> Dict[str, Any]:
        """
        Authenticates a user with email and password using the userAuth method.
        """
        data = {
            "email": email,
            "password": password
        }
        try:
            res = self._request.post("userAuth", data=data)
            if not self.auth_cookie:
                raise AuthenticationError("Server did not issue an auth cookie")
            return res
        except KinoriumError as e:
            raise AuthenticationError(f"Authentication failed: {e}") from e

    def get_user_info(self, user_id: int = 0) -> Dict[str, Any]:
        """
        Fetches user profile data. Works for public profile data.
        """
        return self._request.get("getUserInfo", params={"user_id": user_id})

    def get_movie(self, movie_id: int) -> Dict[str, Any]:
        """Fetch movie details using the movie_id parameter expected by the API."""
        return self._request.get("getMovie", params={"movie_id": movie_id})

    def set_movie_status(self, movie_id: int, status: str) -> Dict[str, Any]:
        """Set a movie status (done, future or never)."""
        if status not in ("done", "future", "never"):
            raise InvalidOptionError("Supported movie statuses: done, future, never")
        return self.request("POST", "setMovieStatus", data={
            "movie_id": movie_id, "status": status,
        })

    def remove_movie_status(self, movie_id: int) -> Dict[str, Any]:
        """Remove the current movie status using the server's POST endpoint."""
        return self.request("POST", "removeMovieStatus", data={
            "movie_id": movie_id, "type": "status",
        })

    def get_user_lists(self, user_id: int = 0) -> Dict[str, Any]:
        """
        Fetches user lists metadata (e.g. Watchlist, Favorite, custom lists).
        """
        params = {
            "user_id": user_id,
            "obj_ids": "",
            "page": 1,
            "perpage": 1000
        }
        return self._request.get("getUList", params=params)

    def get_user_list_objects(self, ulist_id: int, page: int = 1, perpage: int = 50) -> Dict[str, Any]:
        """
        Fetches data for a user list.
        """
        params = {
            "ulist_id": ulist_id,
            "page": page,
            "perpage": perpage
        }
        return self._request.get("getUListObj", params=params)

    def sign_websocket(self, user_id: str) -> str:
        """
        Calculates the WebSocket signature for a given user_id.
        """
        sign_input = f"{user_id}{self.ws_salt}"
        return hashlib.md5(sign_input.encode("utf-8")).hexdigest()
