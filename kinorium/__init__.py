__version__ = '0.1.0'
__author__ = 'stepan163s'

from kinorium.client import KinoriumClient

try:
    from kinorium.client_async import KinoriumClientAsync
except ImportError:
    KinoriumClientAsync = None  # type: ignore[assignment,misc]

from kinorium.exceptions import (
    ApiError,
    KinoriumError,
    NetworkError,
    TimedOutError,
    UnauthorizedError,
    BadRequestError,
    NotFoundError,
    InvalidOptionError,
    IdMissingError,
    InvalidKeyError,
    KinoriumAPIError,
    AuthenticationError
)
from kinorium.base import BaseModel
from kinorium.models import User, Movie, UserList

__all__ = [
    # Clients
    "KinoriumClient",
    "KinoriumClientAsync",

    # Exceptions
    "ApiError",
    "KinoriumError",
    "NetworkError",
    "TimedOutError",
    "UnauthorizedError",
    "BadRequestError",
    "NotFoundError",
    "InvalidOptionError",
    "IdMissingError",
    "InvalidKeyError",
    "KinoriumAPIError",
    "AuthenticationError",

    # Models
    "BaseModel",
    "User",
    "Movie",
    "UserList"
]
