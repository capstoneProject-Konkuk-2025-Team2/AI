# 피드백 생성 관련 설정

# 카테고리 이름 매핑
CATEGORY_NAMES = {
    "career": "진로",
    "etc": "기타"
}

# 프롬프트 템플릿
FEEDBACK_PROMPT_TEMPLATE = """
당신은 대학생의 비교과 활동을 분석하고 격려하는 멘토입니다. 
다음 정보를 바탕으로 따뜻하고 격려적인 피드백 메시지를 한국어로 작성해주세요.

**활동 통계:**
{stats_summary}

**주요 인사이트:**
{insights_text}

**추천사항:**
{recommendations_text}

**요청사항:**
1. 친근하고 격려적인 톤으로 작성
2. 구체적인 수치와 성과를 언급
3. 앞으로의 발전 방향 제시
4. 2-3문단으로 구성 (100-150자 내외)
5. 이모지 사용 금지, 자연스러운 한국어 표현 사용

피드백 메시지:
"""

SYSTEM_PROMPT = "당신은 대학생 멘토링 전문가입니다. 비교과 활동 데이터를 분석하여 격려와 조언을 제공합니다."

# 폴백 메시지 템플릿
FALLBACK_NO_ACTIVITY = "아직 비교과 활동 기록이 없지만 괜찮습니다! 새로운 시작이 기대되네요. 관심 있는 분야부터 천천히 도전해보세요."

FALLBACK_TEMPLATE = "{period} 기간 동안 총 {total_activities}개의 활동에 참여하며 {total_hours:.1f}시간을 투자하셨네요. 특히 {main_category} 분야에서 두각을 나타내고 있어 인상적입니다. {diversity_message} 지금처럼 꾸준히 활동을 이어가시길 응원합니다."

DIVERSITY_MESSAGES = {
    "high": "진로와 기타 활동 모두에 균형있게 참여하고 있어 멋집니다!",
    "low": "앞으로 다른 분야도 도전해보시면 더욱 풍부한 경험을 쌓을 수 있을 것 같아요."
}

ERROR_FALLBACK = "피드백 생성 중 오류가 발생했지만, 여러분의 노력과 성장을 응원합니다!"

# LLM 설정
LLM_CONFIG = {
    "model": "gpt-3.5-turbo",
    "max_tokens": 200,
    "temperature": 0.7
} 