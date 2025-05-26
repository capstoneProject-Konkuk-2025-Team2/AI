from enum import Enum

class ErrorCode(Enum):
    VALIDATION_ERROR = ("VALIDATION_ERROR", "요청 데이터가 유효하지 않습니다.", 422)
    INTERNAL_SERVER_ERROR = ("INTERNAL_SERVER_ERROR", "서버 내부 오류가 발생했습니다.", 500)
    USER_PROFILE_MISSING = ("USER_PROFILE_MISSING", "사용자 정보가 없습니다. 먼저 입력해 주세요.", 400)
    NO_RELEVANT_DOCUMENT = ("NO_RELEVANT_DOCUMENT", "관련 정보를 찾지 못했습니다.", 404)

    def __init__(self, code: str, message: str, http_status: int):
        self._code = code
        self._message = message
        self._http_status = http_status

    @property
    def code(self) -> str:
        return self._code

    @property
    def message(self) -> str:
        return self._message

    @property
    def http_status(self) -> int:
        return self._http_status