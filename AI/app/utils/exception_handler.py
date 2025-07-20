from fastapi import Request
from fastapi.responses import JSONResponse
from app.models.response.base_response import error_response
from app.utils.app_exception import AppException
from app.utils.constants.error_codes import ErrorCode
from fastapi.exceptions import RequestValidationError

def app_exception_handler(request: Request, exc: AppException):
    status_code, body = error_response(exc.error)
    return JSONResponse(status_code=status_code, content=body)

def generic_exception_handler(request: Request, exc: Exception):
    status_code, body = error_response(ErrorCode.INTERNAL_SERVER_ERROR)
    return JSONResponse(status_code=status_code, content=body)

def validation_exception_handler(request: Request, exc: RequestValidationError):
    status_code, body = error_response(ErrorCode.VALIDATION_ERROR)
    return JSONResponse(status_code=status_code, content=body)