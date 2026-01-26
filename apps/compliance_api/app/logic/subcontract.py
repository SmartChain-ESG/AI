# app/logic/subcontract.py

SUBCONTRACT_RULES = [
    {
        "article": "제11조 (부당한 대금 결정 금지)",
        "check_points": [
            "정당한 사유 없이 일률적인 비율로 단가를 인하하는지 여부",
            "협력사와의 합의 없이 원청이 일방적으로 낮은 단가를 결정하는지 여부",
            "입찰 시 최저가보다 낮은 금액으로 대금을 결정하는지 여부"
        ]
    },
    {
        "article": "제12조의3 (기술자료 제공 요구 금지)",
        "check_points": [
            "정당한 사유(특허 등) 없이 기술자료 제공을 요구하는 조항",
            "제공받은 기술자료를 제3자에게 유출하거나 유용할 가능성이 있는 조항",
            "기술자료의 범위를 포괄적으로 규정하여 영업비밀을 침해하는지 여부"
        ]
    },
    {
        "article": "제13조 (하도급대금의 지급 등)",
        "check_points": [
            "목적물 수령일로부터 60일 이내에 대금을 지급하도록 명시되어 있는지 여부",
            "60일을 초과하는 지연 이자율(연 15.5%)에 대한 언급이 있는지 여부",
            "원청의 자금 사정에 따라 지급을 유예한다는 독소 조항 포함 여부"
        ]
    }
]

def get_detailed_rules_prompt():
    """AI에게 주입할 상세 가이드라인 텍스트 생성"""
    prompt = "당신은 다음의 대한민국 하도급법 세부 기준에 근거하여 계약서를 검토해야 합니다:\n\n"
    for rule in SUBCONTRACT_RULES:
        prompt += f"### {rule['article']}\n"
        for cp in rule['check_points']:
            prompt += f"- {cp}\n"
    prompt += "\n위 기준 중 하나라도 위반 소지가 있다면 반드시 지적하고, 근거 법령을 명시하세요."
    return prompt