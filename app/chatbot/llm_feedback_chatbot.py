from typing import List
from app.config.llm_config import client
from app.utils.format.feedback_format import (
    CATEGORY_NAMES, FEEDBACK_PROMPT_TEMPLATE, SYSTEM_PROMPT,
    FALLBACK_NO_ACTIVITY, FALLBACK_TEMPLATE, DIVERSITY_MESSAGES,
    ERROR_FALLBACK, LLM_CONFIG
)
from app.models.activity import ActivityStats
from app.utils.app_exception import AppException
from app.utils.constants.error_codes import ErrorCode


def generate_feedback(stats: ActivityStats, insights: List[str], recommendations: List[str]) -> str:

    try:
        prompt = _build_feedback_prompt(stats, insights, recommendations)

        response = client.chat.completions.create(
            model=LLM_CONFIG["model"], # LLM_CONFIG가 feedback_format에 있는게 맞을까? 일단 빼놓음 (agent_rag_chatbot과 동일한 모델이면 config로 빼면 좋을 듯)
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt}
            ],
            max_tokens=LLM_CONFIG["max_tokens"],
            temperature=LLM_CONFIG["temperature"]
        )

        feedback = response.choices[0].message.content.strip()

        if not feedback or len(feedback) < 20:
            return generate_fallback_feedback(stats, insights)

        return feedback

    except Exception as e:
        print(f"오류 발생: {e}")
        return generate_fallback_feedback(stats, insights) # LLM 실패면 그냥 빈문자열 반환할까?


def _build_feedback_prompt(stats: ActivityStats, insights: List[str], recommendations: List[str]) -> str:
    try:
        stats_summary = _format_stats_for_prompt(stats)
        insights_text = "\n".join(f"- {item}" for item in insights)
        recommendations_text = "\n".join(f"- {item}" for item in recommendations)

        return FEEDBACK_PROMPT_TEMPLATE.format(
            stats_summary=stats_summary,
            insights_text=insights_text,
            recommendations_text=recommendations_text
        )
    except Exception as e:
        print(f"오류 발생: {e}")
        raise AppException(ErrorCode.REPORT_GENERATION_FAILED)


def _format_stats_for_prompt(stats: ActivityStats) -> str:
    try:
        korean_distribution = {
            CATEGORY_NAMES.get(cat, cat): count
            for cat, count in stats.category_distribution.items()
        }

        most_active_korean = CATEGORY_NAMES.get(stats.most_active_category, stats.most_active_category)

        return (
            f"- 총 활동 수: {stats.total_activities}개\n"
            f"- 총 활동 시간: {stats.total_hours:.1f}시간\n"
            f"- 가장 활발한 분야: {most_active_korean}\n"
            f"- 참여 분야 다양성: {stats.diversity_score:.1f}\n"
            f"- 분야별 활동 수: {korean_distribution}"
        )
    except Exception as e:
        print(f"오류 발생: {e}")
        return "통계 정보를 처리하는 중 오류가 발생했습니다."


def generate_fallback_feedback(stats: ActivityStats, insights: List[str]) -> str:
    try:
        if stats.total_activities == 0:
            return FALLBACK_NO_ACTIVITY

        main_category = CATEGORY_NAMES.get(stats.most_active_category, stats.most_active_category)
        diversity_msg = DIVERSITY_MESSAGES["high"] if stats.diversity_score >= 0.5 else DIVERSITY_MESSAGES["low"]

        return FALLBACK_TEMPLATE.format(
            period="이번",
            total_activities=stats.total_activities,
            total_hours=stats.total_hours,
            main_category=main_category,
            diversity_message=diversity_msg
        )

    except Exception as e:
        print(f"[오류 발생: {e}")
        return ERROR_FALLBACK
