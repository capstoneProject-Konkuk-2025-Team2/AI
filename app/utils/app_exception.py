from app.utils.constants.error_codes import ErrorCode

class AppException(Exception):
    def __init__(self, error: ErrorCode):
        self.error = error
