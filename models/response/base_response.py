from pydantic import BaseModel
from typing import Optional, Any
from utils.constants.error_codes import ErrorCode

class BaseResponse(BaseModel):
    success: bool
    message: Optional[str] = None
    data: Optional[Any] = None
    error_code: Optional[str] = None

def response(
    success: bool,
    message: Optional[str] = None,
    data: Any = None,
    error_code: Optional[str] = None
) -> BaseResponse:
    return BaseResponse(
        success=success,
        message=message,
        data=data,
        error_code=error_code
    )

def error_response(error: ErrorCode) -> tuple[int, dict]:
    response = response(
        success=False,
        message=error.message,
        error_code=error.code
    )
    return error.http_status, response.model_dump()
