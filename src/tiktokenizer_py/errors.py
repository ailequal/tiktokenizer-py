"""One JSON error shape for every failure: ``{"error": {"code", "message", "details"}}``."""

from __future__ import annotations

from http import HTTPStatus

from fastapi import FastAPI, Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from tiktokenizer_py.schemas import ErrorBody, ErrorResponse


class ApiError(Exception):
    def __init__(
        self,
        status_code: int,
        code: str,
        message: str,
        details: object | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message
        self.details = details
        self.headers = headers


def error_response(
    status_code: int,
    code: str,
    message: str,
    details: object | None = None,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    body = ErrorResponse(error=ErrorBody(code=code, message=message, details=details))
    return JSONResponse(status_code=status_code, content=jsonable_encoder(body), headers=headers)


def _status_code_name(status_code: int) -> str:
    try:
        return HTTPStatus(status_code).phrase.lower().replace(" ", "_").replace("-", "_")
    except ValueError:
        return "error"


async def _api_error(_: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, ApiError)
    return error_response(exc.status_code, exc.code, exc.message, exc.details, exc.headers)


async def _http_error(_: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, StarletteHTTPException)
    response = error_response(exc.status_code, _status_code_name(exc.status_code), str(exc.detail))
    if exc.headers:
        response.headers.update(exc.headers)
    return response


async def _validation_error(_: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, RequestValidationError)
    # Keep only JSON-safe fields: "ctx" can hold exception objects and "input" can be huge.
    errors = [{k: e[k] for k in ("type", "loc", "msg") if k in e} for e in exc.errors()]
    first = errors[0] if errors else {}
    if first.get("type") == "json_invalid":
        # Its location is a character offset in the body, not a field name.
        message = "The request body is not valid JSON"
    else:
        where = ".".join(str(p) for p in first.get("loc", ()) if p != "body")
        # Pydantic prefixes errors raised by validators with "Value error, ".
        msg = str(first.get("msg", "")).removeprefix("Value error, ")
        message = f"{where}: {msg or 'invalid request'}" if where else msg
    return error_response(
        status.HTTP_422_UNPROCESSABLE_CONTENT,
        "validation_error",
        message or "Invalid request",
        details=errors,
    )


async def _unexpected_error(_: Request, exc: Exception) -> JSONResponse:
    # Starlette still logs the traceback; the client gets the usual error shape.
    return error_response(
        status.HTTP_500_INTERNAL_SERVER_ERROR,
        _status_code_name(status.HTTP_500_INTERNAL_SERVER_ERROR),
        "The server hit an unexpected error. Check the server log for details.",
    )


def install_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(ApiError, _api_error)
    app.add_exception_handler(StarletteHTTPException, _http_error)
    app.add_exception_handler(RequestValidationError, _validation_error)
    app.add_exception_handler(Exception, _unexpected_error)
