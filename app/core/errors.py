from typing import Any

from fastapi import HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


def request_id(request: Request) -> str:
    return getattr(request.state, "request_id", "unknown")


def error_response(
    *,
    request: Request,
    status_code: int,
    code: str,
    message: str,
    details: Any = None,
) -> JSONResponse:
    request.state.error_category = code
    payload = {
        "error": {
            "code": code,
            "message": message,
            "details": details,
            "request_id": request_id(request),
        }
    }
    return JSONResponse(
        status_code=status_code,
        content=payload,
        headers={"X-Request-ID": request_id(request)},
    )


async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    detail = exc.detail
    message = detail if isinstance(detail, str) else "Request failed"
    return error_response(
        request=request,
        status_code=exc.status_code,
        code=_http_error_code(exc.status_code),
        message=message,
        details=None if isinstance(detail, str) else detail,
    )


async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    return error_response(
        request=request,
        status_code=422,
        code="validation_error",
        message="Request validation failed",
        details=_validation_details(exc),
    )


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    return error_response(
        request=request,
        status_code=500,
        code="internal_error",
        message="Internal server error",
        details=None,
    )


def _http_error_code(status_code: int) -> str:
    if status_code == 400:
        return "bad_request"
    if status_code == 401:
        return "unauthorized"
    if status_code == 403:
        return "forbidden"
    if status_code == 404:
        return "not_found"
    if status_code == 409:
        return "conflict"
    if status_code == 413:
        return "payload_too_large"
    if status_code == 415:
        return "unsupported_media_type"
    if status_code == 422:
        return "validation_error"
    if status_code == 429:
        return "rate_limited"
    return "http_error"


def _validation_details(exc: RequestValidationError) -> list[dict[str, Any]]:
    details = []
    for item in exc.errors():
        details.append(
            {
                "loc": list(item.get("loc", [])),
                "msg": item.get("msg", "Invalid value"),
                "type": item.get("type", "value_error"),
            }
        )
    return details
