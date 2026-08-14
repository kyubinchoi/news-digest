import json
import os
import re

from anthropic import Anthropic

MODEL = "claude-sonnet-5"

_client = None


def _get_client():
    global _client
    if _client is None:
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise RuntimeError(
                "ANTHROPIC_API_KEY가 설정되어 있지 않습니다. .env 파일이나 환경변수에 키를 넣어주세요."
            )
        _client = Anthropic(api_key=api_key)
    return _client


TOOL_SCHEMA = {
    "name": "record_summary",
    "description": "영어 학습자를 위해 뉴스 기사를 쉬운 영어 요약과 한국어 설명으로 정리한다.",
    "input_schema": {
        "type": "object",
        "properties": {
            "headline_kr": {
                "type": "string",
                "description": "뉴스레터 스타일의 짧고 눈에 띄는 한국어 헤드라인 (이모지 1개 정도 활용 가능)",
            },
            "easy_english": {
                "type": "string",
                "description": (
                    "3~5개의 짧은 문장으로 기사 내용을 요약. CEFR A2~B1 수준의 쉬운 단어와 "
                    "단순한 문장 구조만 사용하고, 관용구나 어려운 숙어는 피한다."
                ),
            },
            "korean_explanation": {
                "type": "string",
                "description": (
                    "한국 뉴스레터 '뉴닉' 같은 친근하고 편안한 말투로, 무슨 일이 있었는지와 "
                    "왜 중요한지를 2~4문장으로 설명."
                ),
            },
            "vocab": {
                "type": "array",
                "description": "위 easy_english 요약에 나온 핵심 단어/표현 3~5개",
                "items": {
                    "type": "object",
                    "properties": {
                        "word": {"type": "string", "description": "영어 단어 또는 표현"},
                        "meaning_kr": {"type": "string", "description": "한국어 뜻"},
                        "example": {
                            "type": "string",
                            "description": "이 단어를 사용한 쉬운 예문 (선택)",
                        },
                    },
                    "required": ["word", "meaning_kr"],
                },
                "maxItems": 5,
            },
        },
        "required": ["headline_kr", "easy_english", "korean_explanation", "vocab"],
    },
}


def summarize_article(source: str, title: str, original_summary: str) -> dict:
    """기사 제목+요약을 받아 쉬운 영어 요약 / 한국어 설명 / 단어 리스트를 생성."""
    client = _get_client()

    user_text = (
        f"Source: {source}\n"
        f"Title: {title}\n"
        f"Original summary/snippet: {original_summary}\n\n"
        "위 뉴스 기사 정보를 바탕으로 record_summary 도구를 호출해줘."
    )

    for attempt in range(2):
        response = client.messages.create(
            model=MODEL,
            max_tokens=1024,
            tools=[TOOL_SCHEMA],
            tool_choice={"type": "tool", "name": "record_summary"},
            messages=[{"role": "user", "content": user_text}],
        )

        result = None
        for block in response.content:
            if block.type == "tool_use":
                result = block.input
                break

        if result is not None:
            result = _repair_leaked_tags(result)
            if _looks_clean(result):
                return result

        if attempt == 0:
            continue  # 응답이 비어있거나 복구 후에도 형식이 깨진 경우 한 번 재시도

    raise RuntimeError("Claude 응답이 비어있거나 형식이 깨져서 재시도 후에도 실패했습니다.")


# 특정 주제(예: 전쟁/분쟁 관련 기사)에서 모델이 record_summary 호출 도중 다음 파라미터를
# 텍스트로 이어붙이는 경우가 있다 (예: "...설명끝.</korean_explanation>\n<parameter name=\"vocab\">[...]").
# 재시도해도 같은 입력에는 같은 방식으로 새는 경우가 많아, 새어나온 텍스트를 잘라내고
# 그 안에 섞인 값(주로 vocab)을 복구한다.
_LEAK_MARKERS = ("</korean_explanation>", "</easy_english>", "</headline_kr>", "<parameter", "<invoke")


def _repair_leaked_tags(result: dict) -> dict:
    repaired = dict(result)

    for key in ("headline_kr", "easy_english", "korean_explanation"):
        value = repaired.get(key) or ""
        cut_index = min(
            (idx for idx in (value.find(marker) for marker in _LEAK_MARKERS) if idx != -1),
            default=None,
        )
        if cut_index is None:
            continue

        leaked_tail = value[cut_index:]
        repaired[key] = value[:cut_index].strip()

        if not repaired.get("vocab"):
            match = re.search(r'"vocab">\s*(\[.*\])', leaked_tail, re.DOTALL)
            if match:
                try:
                    repaired["vocab"] = json.loads(match.group(1))
                except json.JSONDecodeError:
                    pass

    return repaired


def _looks_clean(result: dict) -> bool:
    for key in ("headline_kr", "easy_english", "korean_explanation"):
        value = result.get(key, "")
        if not value or any(marker in value for marker in _LEAK_MARKERS):
            return False
    return isinstance(result.get("vocab"), list) and len(result["vocab"]) > 0


def vocab_to_json(vocab: list) -> str:
    return json.dumps(vocab, ensure_ascii=False)
