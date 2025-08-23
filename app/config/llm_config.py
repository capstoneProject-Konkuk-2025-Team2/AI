import os
from dotenv import load_dotenv
from openai import OpenAI
from langchain_openai import ChatOpenAI
from app.utils.constants.error_codes import ErrorCode
from app.utils.app_exception import AppException

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    raise AppException(ErrorCode.NOT_FOUND_OPENAI_API_KEY)

MODEL_NAME = os.getenv("LLM_MODEL", "gpt-3.5-turbo") # 모델 명시

client = OpenAI(api_key=OPENAI_API_KEY)
llm = ChatOpenAI(openai_api_key=OPENAI_API_KEY, temperature=0)