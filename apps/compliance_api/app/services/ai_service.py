# app/services/ai_service.py (업데이트 버전)
from openai import AsyncOpenAI
import json
from app.core.config import settings
from app.logic.subcontract import get_detailed_rules_prompt # 로직 불러오기

client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

async def analyze_risk(full_text: str):
    # 우리가 정의한 법적 기준 가이드라인 가져오기
    legal_guideline = get_detailed_rules_prompt()
    
    system_prompt = f"""
    당신은 대한민국 하도급법 전문 변호사입니다.
    
    {legal_guideline}
    
    [응답 지침]
    1. 분석 결과는 반드시 JSON 형식으로 반환하세요.
    2. risk_score는 0~100 사이이며, 위반 조항이 명확할수록 높게 측정합니다.
    3. summary에는 어떤 법적 근거로 리스크가 있는지 요약합니다.
    4. risks 배열에는 구체적인 위반 의심 문구와 사유를 넣으세요.
    """

    response = await client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"다음 계약서 본문을 정밀 분석해줘:\n\n{full_text}"}
        ],
        response_format={"type": "json_object"}
    )
    
    return json.loads(response.choices[0].message.content)