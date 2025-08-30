from typing import List, Any, Mapping
from app.config.llm_config import client
from app.utils.format.feedback_format import (
    FEEDBACK_PROMPT_TEMPLATE, SYSTEM_PROMPT,
    FALLBACK_NO_ACTIVITY, FALLBACK_TEMPLATE,
    ERROR_FALLBACK, LLM_CONFIG
)
from app.utils.app_exception import AppException
from app.utils.constants.error_codes import ErrorCode


def _get(obj: Any, key: str, default=None): # 객체 속성 또는 딕셔너리 키를 안전하게 가져옴
    if hasattr(obj, key):
        return getattr(obj, key)
    if isinstance(obj, Mapping):
        return obj.get(key, default)
    return default


def _to_int(val: Any, default: int = 0) -> int: # 임의의 값을 정수로 변환
    try:
        if val is None:
            return default
        return int(val)
    except Exception:
        return default


def _to_float(val: Any, default: float = 0.0) -> float: # 임의의 값을 부동소수점으로 변환
    try:
        if val is None:
            return default
        return float(val)
    except Exception:
        return default


def generate_feedback(stats: Any, insights: List[str], recommendations: List[str]) -> str:
    # stats가 dict이든 객체이든 모두 처리. LLM 실패/응답이상 시 안전한 fallback 반환하게 하기!
    # stats는 사용자 활동 통계, insights는 인사이트 목록, recommendations는 추천사항 목록
    try:
        prompt = _build_feedback_prompt(stats, insights, recommendations) # 입력 데이터를 LLM이 이해할 수 있는 프롬프트로 구섣

        # OpenAI 활용 - 여기서 max_tokens때문에 피드백 문장이 잘리는 듯 (토큰을 높이면 비용이 더 든다고 함)
        response = client.chat.completions.create(
            model=LLM_CONFIG["model"],
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt}
            ],
            max_tokens=LLM_CONFIG["max_tokens"],
            temperature=LLM_CONFIG["temperature"]
        )

        feedback = (response.choices[0].message.content or "").strip() # API 응답에서 실제 메세지 내용을 추출하고 정리함

        if not feedback or len(feedback) < 20: # 응답 품질을 검증하는데, 너무 짧거나 품질이 낮다고 판단되면 다시함
            return generate_fallback_feedback(stats, insights)

        return feedback # 정상적 피드백 반환

    except Exception as e:
        print(f"오류 발생: {e}")
        return generate_fallback_feedback(stats, insights)


def _build_feedback_prompt(stats: Any, insights: List[str], recommendations: List[str]) -> str:
    try:
        stats_summary = _format_stats_for_prompt(stats) # 통계데이터를 자연어로 변환
        insights_text = "\n".join(f"- {item}" for item in (insights or [])) # 위와 비슷
        recommendations_text = "\n".join(f"- {item}" for item in (recommendations or [])) # 위와 비슷

        # 미리 정의된 템플릿에 실제 데이터를 삽입
        return FEEDBACK_PROMPT_TEMPLATE.format(
            stats_summary=stats_summary,
            insights_text=insights_text,
            recommendations_text=recommendations_text
        )
    except Exception as e:
        print(f"오류 발생: {e}")
        raise AppException(ErrorCode.REPORT_GENERATION_FAILED)


def _format_stats_for_prompt(stats: Any) -> str:
    try:
        total_activities = _to_int(_get(stats, "total_activities", 0), 0)
        total_hours = _to_float(_get(stats, "total_hours", 0.0), 0.0)

        return (
            f"- 총 활동 수: {total_activities}개\n"
            f"- 총 활동 시간: {total_hours:.1f}시간\n"
        )
    except Exception as e:
        print(f"오류 발생: {e}")
        return "통계 정보를 처리하는 중 오류가 발생했습니다."


def generate_fallback_feedback(stats: Any) -> str: # LLM 호출 실패 시 사용할 피드백 생성함수
    try:
        total_activities = _to_int(_get(stats, "total_activities", 0), 0)
        total_hours = _to_float(_get(stats, "total_hours", 0.0), 0.0)

        if total_activities == 0:
            return FALLBACK_NO_ACTIVITY

        return FALLBACK_TEMPLATE.format(
            period="이번",
            total_activities=total_activities,
            total_hours=total_hours
        )

    except Exception as e:
        print(f"[오류 발생: {e}]")
        return ERROR_FALLBACK
