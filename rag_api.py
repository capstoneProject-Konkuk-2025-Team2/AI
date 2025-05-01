from fastapi import FastAPI, Request
from pydantic import BaseModel
from llmware.library import Library
from llmware.retrieval import Query
from llmware.models import ModelCatalog
from llmware.configs import LLMWareConfig, MilvusConfig
import os

# 초기 설정
LLMWareConfig().set_active_db("sqlite")
MilvusConfig().set_config("lite", True)
LLMWareConfig().set_vector_db("chromadb")

# 라이브러리 및 모델 로딩
library_name = "my_library"
embedding_model = "mini-lm-sbert"
llm_model_name = "bling-answer-tool"

lib = Library().load_library(library_name)
query_engine = Query(lib)
model = ModelCatalog().load_model(llm_model_name)

# FastAPI 초기화
app = FastAPI()

class ChatRequest(BaseModel):
    question: str

@app.post("/chat")
async def chat_with_bot(request: ChatRequest):
    user_question = request.question

    # semantic query
    search_results = query_engine.semantic_query(user_question, result_count=3)

    if not search_results:
        return {"answer": "관련 정보를 찾지 못했습니다."}

    # context 결합
    combined_context = " ".join([res["text"] for res in search_results])

    # 모델 추론
    answer = model.inference(user_question, add_context=combined_context)

    return {"answer": answer}