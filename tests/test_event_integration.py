# test_integration.py
import asyncio
import logging

from app.core.events import bus, signals
from app.feedback.infrastructure.di import get_feedback_service
from app.feedback.infrastructure.event_listener import register_feedback_listeners

# 피드백과 리포트 메시지 송수신 테스트
logging.basicConfig(level=logging.INFO)

# ── 테스트 페이로드 (media/ 가 실제로 emit 하는 구조) ──────────────
PAYLOAD = {
    "intvId": 99,
    "questionId": 5,
    "questionContent": "본인의 백엔드 프로젝트 경험 중 가장 기억에 남는 것을 말씀해 주세요.",
    "status": "DONE",
    "degraded": False,
    "transcript": {
        "rawTranscript": "레디스로 캐싱 처리를 하고 도커로 컨테이너 환경을 구성했습니다.",
        "phoneticTranscript": "레디스로 캐싱 처리를 하고 도커로 컨테이너 환경을 구성했습니다.",
        "correctedTranscript": "Redis로 캐싱 처리를 하고 Docker로 컨테이너 환경을 구성했습니다. API 응답 속도를 30% 개선하였으며, 서비스 안정성과 배포 자동화를 동시에 달성했습니다.",
    },
    "keywords": {
        "candidates": [
            {"term": "Redis", "count": 2, "category": "Backend"},
            {"term": "Docker", "count": 1, "category": "DevOps"},
        ]
    },
    "gaze": {"gazeScore": 82},
    "time": {"timeScore": 91, "answerDurationMs": 54500},
    "reliability": {"score": 88, "grade": "높음"},
}


async def main():
    # 1. 서비스 + 리스너 등록
    service = get_feedback_service()
    register_feedback_listeners(service)

    print("=" * 60)
    print("🚀 통합 테스트 시작")
    print("   media_completed 이벤트 emit →")
    print("   FeedbackService → LLM → Webhook(포트 9000)")
    print("=" * 60)

    # 2. 이벤트 emit (media/ 가 하는 동작 그대로 재현)
    bus.emit(
        signal=signals.media_completed,
        payload=PAYLOAD,
        sender="test",
    )

    # 3. 비동기 핸들러 완료 대기 (BackgroundTask 처리 시간)
    print("⏳ LLM 응답 대기 중 (최대 30초)...")
    await asyncio.sleep(30)
    print("✅ 테스트 완료 — 터미널 1(callback_receiver) 결과를 확인하세요.")


if __name__ == "__main__":
    asyncio.run(main())
