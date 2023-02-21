from fastapi.encoders import jsonable_encoder
from fastapi.utils import is_body_allowed_for_status_code
from starlette.exceptions import HTTPException
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from supine.api_response import ApiError


async def supine_http_exception_handler(
    request: Request, exc: HTTPException
) -> Response:
    """
    Primarily copied from FastAPI's base implementation, but uses ApiError so that
    the response will include 'status': 'error' etc
    """
    headers = getattr(exc, "headers", None)
    if not is_body_allowed_for_status_code(exc.status_code):
        return Response(status_code=exc.status_code, headers=headers)
    api_error = ApiError.from_exc(exc)
    return JSONResponse(
        jsonable_encoder(api_error), status_code=exc.status_code, headers=headers
    )
