from __future__ import annotations
from typing import Optional
from typing_extensions import Literal
import httpx

def is_dict(obj) -> bool:
    """Check if object is a dictionary."""
    return isinstance(obj, dict)

class TsGuardError(Exception):
    pass


class APIError(TsGuardError):
    message: str
    request: httpx.Request
    body: object | None
    code: Optional[str] = None


    def __init__(self, message: str, request: httpx.Request, *, body: object | None) -> None:
        super().__init__(message)
        self.request = request
        self.message = message
        self.body = body

        # Extract error details if body is a dictionary
        if is_dict(body):
            self.code = body.get("code")

        else:
            self.code = None    


class APIStatusError(APIError):
    """Raised when an API response has a status code of 4xx or 5xx."""
    
    response: httpx.Response
    status_code: int

    def __init__(self, message: str, *, response: httpx.Response, body: object | None) -> None:
        super().__init__(message, response.request, body=body)
        self.response = response
        self.status_code = response.status_code


class BadRequestError(APIStatusError):
    status_code: Literal[400] = 400  

class AuthenticationError(APIStatusError):
    status_code: Literal[401] = 401  


class PermissionDeniedError(APIStatusError):
    status_code: Literal[403] = 403  


class NotFoundError(APIStatusError):
    status_code: Literal[404] = 404  


class ConflictError(APIStatusError):
    status_code: Literal[409] = 409  

class UnprocessableEntityError(APIStatusError):
    status_code: Literal[422] = 422  


class RateLimitError(APIStatusError):
    status_code: Literal[429] = 429  

class InternalServerError(APIStatusError):
    pass    