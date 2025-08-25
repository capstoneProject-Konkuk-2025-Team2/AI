from enum import Enum

class ErrorCode(Enum):
    VALIDATION_ERROR = ("VALIDATION_ERROR", "요청 데이터가 유효하지 않습니다.", 422)
    INTERNAL_SERVER_ERROR = ("INTERNAL_SERVER_ERROR", "서버 내부 오류가 발생했습니다.", 500)
    USER_PROFILE_MISSING = ("USER_PROFILE_MISSING", "사용자 정보가 없습니다. 먼저 입력해 주세요.", 400)
    NO_RELEVANT_DOCUMENT = ("NO_RELEVANT_DOCUMENT", "관련 정보를 찾지 못했습니다.", 404)
    NOT_FOUND_OPENAI_API_KEY = ("NOT_FOUND_OPENAI_API_KEY", "OPEN_API_KEY를 찾을 수 없습니다. .env 파일을 확인해주세요.", 400)
    
    INVALID_ACTIVITY_DATA = ("INVALID_ACTIVITY_DATA", "활동 데이터가 올바르지 않습니다.", 400)
    ACTIVITY_LOAD_FAILED = ("ACTIVITY_LOAD_FAILED", "활동 데이터 로드에 실패했습니다.", 500)
    ACTIVITY_SAVE_FAILED = ("ACTIVITY_SAVE_FAILED", "활동 저장에 실패했습니다.", 500)
    ACTIVITY_NOT_FOUND = ("ACTIVITY_NOT_FOUND", "해당 활동을 찾을 수 없습니다.", 404)

    FILE_READ_ERROR = ("FILE_READ_ERROR", "파일 읽기에 실패했습니다.", 500)
    DATA_ACCESS_ERROR = ("DATA_ACCESS_ERROR", "데이터 접근 중 오류가 발생했습니다.", 500)
    REPORT_GENERATION_FAILED = ("REPORT_GENERATION_FAILED", "리포트 생성 중 오류가 발생했습니다.", 500)
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