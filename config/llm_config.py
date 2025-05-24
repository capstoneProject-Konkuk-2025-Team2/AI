from llmware.library import Library
from llmware.retrieval import Query
from llmware.models import ModelCatalog
from llmware.configs import LLMWareConfig, MilvusConfig
# 초기 설정
LLMWareConfig().set_active_db("sqlite")
MilvusConfig().set_config("lite", True)
LLMWareConfig().set_vector_db("chromadb")
USER_TABLE_PATH = "user.json"

# 라이브러리 및 모델 로딩
library_name = "my_library"
embedding_model = "mini-lm-sbert"
llm_model_name = "bling-answer-tool"

lib = Library().load_library(library_name)
query_engine = Query(lib)
model = ModelCatalog().load_model(llm_model_name)
