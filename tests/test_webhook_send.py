# test_webhook_send.py
import asyncio
from datetime import datetime

import httpx

# 피드백용 웹훅 전송 테스트

# ── 전송할 페이로드 (camelCase, Spring 수신 형식) ──────────────────
PAYLOAD = {
    "intvId": 99,
    "questionId": 5,
    "status": "SUCCEED",
    "logicScore": 85,
    "answerCompositionScore": 72,
    "questionContent": "Redis를 활용한 캐싱 전략에 대해 설명해 주세요.",
    "characteristic": "Redis 활용 경험을 수치로 명확히 설명함.",
    "answerSummary": "Redis 캐싱으로 API 성능을 개선하고 Docker로 배포 자동화를 구현한 경험을 답변함.",
    "strength": "API 응답 속도 30% 개선이라는 구체적 수치를 근거로 제시했습니다.",
    "improvement": "PREP 구조를 활용하면 답변의 전달력이 향상될 것입니다.",
    "feedbackBadges": ["수치 근거 활용", "경험 기반 답변"],
    "gazeScore": 82,
    "timeScore": 91,
    "answerDurationMs": 54500,
    "keywordCount": 2,
    "reliability": 88,
}

# ── Webhook 전송 대상 (callback_receiver.py) ──────────────────────
WEBHOOK_URL = "http://127.0.0.1:9000/internal/v1/feedbacks/callback"


async def send():
    print(f"[{datetime.now()}] 🚀 Webhook 전송 시작 → {WEBHOOK_URL}")
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.post(
            WEBHOOK_URL,
            json=PAYLOAD,
            headers={"Content-Type": "application/json"},
        )
    print(f"[{datetime.now()}] ✅ 응답 코드  : {response.status_code}")
    print(f"[{datetime.now()}] 📋 응답 바디  : {response.text}")


if __name__ == "__main__":
    asyncio.run(send())
