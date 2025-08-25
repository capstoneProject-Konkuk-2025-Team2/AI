from typing import List, Any, Mapping
from app.config.llm_config import client
from app.utils.format.feedback_format import (
    FEEDBACK_PROMPT_TEMPLATE, SYSTEM_PROMPT,
    FALLBACK_NO_ACTIVITY, FALLBACK_TEMPLATE,
    ERROR_FALLBACK, LLM_CONFIG
)
from app.utils.app_exception import AppException
from app.utils.constants.error_codes import ErrorCode


def _get(obj: Any, key: str, default=None):
    """객체 속성/딕셔너리 키를 동일 인터페이스로 안전하게 읽기"""
    if hasattr(obj, key):
        return getattr(obj, key)
    if isinstance(obj, Mapping):
        return obj.get(key, default)
    return default


def _to_int(val: Any, default: int = 0) -> int:
    try:
        if val is None:
            return default
        return int(val)
    except Exception:
        return default


def _to_float(val: Any, default: float = 0.0) -> float:
    try:
        if val is None:
            return default
        return float(val)
    except Exception:
        return default


def generate_feedback(stats: Any, insights: List[str], recommendations: List[str]) -> str:
    """
    stats가 dict이든 객체이든 모두 처리. LLM 실패/응답이상 시 안전한 fallback 반환.
    """
    try:
        prompt = _build_feedback_prompt(stats, insights, recommendations)

        response = client.chat.completions.create(
            model=LLM_CONFIG["model"],
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt}
            ],
            max_tokens=LLM_CONFIG["max_tokens"],
            temperature=LLM_CONFIG["temperature"]
        )

        # OpenAI 호환 형태 가정
        feedback = (response.choices[0].message.content or "").strip()

        if not feedback or len(feedback) < 20:
            return generate_fallback_feedback(stats, insights)

        return feedback

    except Exception as e:
        print(f"오류 발생: {e}")
        return generate_fallback_feedback(stats, insights)


def _build_feedback_prompt(stats: Any, insights: List[str], recommendations: List[str]) -> str:
    try:
        stats_summary = _format_stats_for_prompt(stats)
        insights_text = "\n".join(f"- {item}" for item in (insights or []))
        recommendations_text = "\n".join(f"- {item}" for item in (recommendations or []))

        return FEEDBACK_PROMPT_TEMPLATE.format(
            stats_summary=stats_summary,
            insights_text=insights_text,
            recommendations_text=recommendations_text
        )
    except Exception as e:
        print(f"오류 발생: {e}")
        # ErrorCode.REPORT_GENERATION_FAILED 가 없다면 기존 코드의 적절한 코드로 교체하세요.
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


def generate_fallback_feedback(stats: Any, insights: List[str]) -> str:
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
