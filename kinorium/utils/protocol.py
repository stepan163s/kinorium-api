"""Signing and response handling shared by both HTTP transports."""
import hashlib
import json
import re
import urllib.parse
from typing import Any, Dict, Optional, Tuple

from kinorium.base import PYTHON_RESERVED
from kinorium.exceptions import (
    BadRequestError, InvalidKeyError, InvalidOptionError, KinoriumAPIError,
    NetworkError, NotFoundError, UnauthorizedError,
)


_CAMEL_RE = re.compile(r'(?<=[a-z0-9])([A-Z])')


def normalize_keys(obj: dict) -> dict:
    result = {}
    for key, value in obj.items():
        key = _CAMEL_RE.sub(r'_\1', key.replace('-', '_')).lower()
        if key in PYTHON_RESERVED:
            key += '_'
        if key and key[0].isdigit():
            key = '_' + key
        result[key] = value
    return result


def canonicalize_and_sign(method: str, params: Optional[Dict[str, Any]],
                          salt: str) -> Tuple[str, str]:
    items = [("method", method)]
    for key, value in (params or {}).items():
        if key not in ("method", "key"):
            items.append((key, str(value) if value is not None else ""))
    encoded = urllib.parse.urlencode(items, quote_via=urllib.parse.quote)
    canonical = encoded.replace("%2F", "/").replace("%2f", "/")
    canonical = canonical.replace("%3F", "?").replace("%3f", "?")
    signature = hashlib.md5(f"?{canonical}{salt}".encode("utf-8")).hexdigest()
    return canonical, signature


def form_data(data: Optional[Dict[str, Any]]) -> Optional[Dict[str, str]]:
    """Use the same scalar representation in the form and the signature."""
    if data is None:
        return None
    return {key: str(value) if value is not None else "" for key, value in data.items()}


def post_params(method: str, params: Optional[Dict[str, Any]],
                data: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    query = dict(params or {})
    if method != "userAuth":
        # Mutation parameters must be part of the signed URL. Login credentials
        # are the exception: the API reads them from the form body only.
        for key, value in (data or {}).items():
            if key in query and query[key] != value:
                raise InvalidOptionError(f"Conflicting values for parameter {key!r}")
            query[key] = value
    return query


def parse_response(content: Any) -> Any:
    if not content or not content.strip():
        return {}
    try:
        data = json.loads(content, object_hook=normalize_keys)
    except (ValueError, UnicodeError) as exc:
        raise KinoriumAPIError(-1, "Failed to parse JSON response") from exc
    if isinstance(data, dict):
        if data.get("key") is False:
            raise InvalidKeyError()
        if "result_code" in data and data["result_code"] not in (0, "0"):
            raise KinoriumAPIError(data["result_code"],
                                   data.get("result_message", "Unknown API error"))
    return data


def extract_error(content: Any) -> str:
    try:
        data = json.loads(content)
        if isinstance(data, dict):
            for key in ("message", "error", "resultMessage", "result_message"):
                if data.get(key):
                    return str(data[key])
    except (ValueError, UnicodeError):
        pass
    if isinstance(content, bytes):
        content = content.decode("utf-8", errors="replace")
    return str(content).strip()[:500] or "Unknown error"


def raise_for_status(status: int, content: Any) -> None:
    if 200 <= status < 300:
        return
    message = f"HTTP {status}: {extract_error(content)}"
    error = {400: BadRequestError, 401: UnauthorizedError, 403: UnauthorizedError,
             404: NotFoundError}.get(status, NetworkError)
    raise error(message)
