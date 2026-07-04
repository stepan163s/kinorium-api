class ApiError(Exception):
    """Base exception for all library errors."""
    pass


class KinoriumError(ApiError):
    """Alias for ApiError for backwards compatibility."""
    pass


class NetworkError(ApiError):
    """Raised on connection failures or general network errors."""
    pass


class TimedOutError(NetworkError):
    """Raised when a request times out."""
    pass


class UnauthorizedError(ApiError):
    """Raised for HTTP 401 and 403 status codes."""
    pass


class BadRequestError(ApiError):
    """Raised for HTTP 400 status codes."""
    pass


class NotFoundError(ApiError):
    """Raised for HTTP 404 status codes."""
    pass


class InvalidOptionError(ApiError):
    """Raised for invalid parameter configuration."""
    pass


class IdMissingError(ApiError):
    """Raised when required ID attributes are missing."""
    pass


class InvalidKeyError(ApiError):
    """Raised when the API returns {"key": False}, indicating signature mismatch or missing key."""
    def __init__(self, message="Invalid or missing signature key"):
        super().__init__(message)


class KinoriumAPIError(ApiError):
    """Raised when the API returns a response containing a non-zero resultCode."""
    def __init__(self, result_code: int, result_message: str):
        self.result_code = result_code
        self.result_message = result_message
        super().__init__(f"API Error {result_code}: {result_message}")


class AuthenticationError(ApiError):
    """Raised when email/password authentication fails."""
    pass
