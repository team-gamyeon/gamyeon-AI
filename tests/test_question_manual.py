"""
Question Feature 수동 확인 스크립트
Spring → Python 질문 생성 요청 → Webhook 콜백 전송 내용까지 확인

실행 전 준비:
    터미널 1: uv run python callback_receiver.py
    터미널 2: uv run python -m uvicorn app.main:app --reload
    터미널 3: uv run python test_question_manual.py
"""

import time

import httpx

# ── 서버 주소 ────────────────────────────────────────────────
MAIN_SERVER = "http://localhost:8000"
CALLBACK_SERVER = "http://localhost:9000"

GENERATE_URL = f"{MAIN_SERVER}/internal/v1/questions/generate"
RECEIVED_URL = f"{CALLBACK_SERVER}/received"
RESET_URL = f"{CALLBACK_SERVER}/reset"

# ── Spring이 파이썬에게 보내는 예시 요청 ─────────────────────
SPRING_REQUEST_EXAMPLE = {
    "intvId": 123,
    "files": [
        {
            "fileType": "RESUME",
            "fileKey": "resume.pdf",
        }
    ],
}

WAIT_TIMEOUT_SEC = 120  # LLM 처리 최대 대기 시간 (초)
POLL_INTERVAL_SEC = 3  # 콜백 수신 확인 폴링 간격 (초)


def step(num: int, msg: str):
    print(f"\n{'='*60}")
    print(f"  STEP {num}. {msg}")
    print(f"{'='*60}")


def check_servers() -> bool:
    """메인 서버 및 콜백 수신 서버 실행 여부 사전 확인"""
    print("\n🔍 서버 상태 확인 중...")

    try:
        httpx.get(f"{MAIN_SERVER}/docs", timeout=2.0)
        print(f"  ✅ 메인 서버 정상 ({MAIN_SERVER})")
    except Exception:
        print(
            "  ❌ 메인 서버 미실행 → 'uv run python -m uvicorn app.main:app --reload' 실행 필요"
        )
        return False

    try:
        httpx.get(RECEIVED_URL, timeout=2.0)
        print(f"  ✅ 콜백 수신 서버 정상 ({CALLBACK_SERVER})")
    except Exception:
        print(
            "  ❌ 콜백 수신 서버 미실행 → 'uv run python callback_receiver.py' 실행 필요"
        )
        return False

    return True


def reset_callback_receiver():
    """이전 수신 기록 초기화"""
    try:
        httpx.post(RESET_URL, timeout=2.0)
        print("  🔄 콜백 수신 기록 초기화 완료")
    except Exception:
        print("  ⚠️  콜백 수신 서버 reset 실패 (무시하고 진행)")


def send_spring_request() -> dict:
    """
    Spring 서버 역할:
    Python 서버에게 질문 생성 요청 POST
    """
    print(f"\n  📤 발송 주소: POST {GENERATE_URL}")
    print("  📦 발송 내용 (Spring → Python):")
    for k, v in SPRING_REQUEST_EXAMPLE.items():
        print(f"      {k}: {v}")

    with httpx.Client(timeout=5.0) as client:
        response = client.post(GENERATE_URL, json=SPRING_REQUEST_EXAMPLE)

    return {"status_code": response.status_code, "body": response.json()}


def wait_for_callback() -> dict | None:
    """
    파이프라인 완료 후 콜백 수신 대기 (폴링)
    """
    print(f"\n  ⏳ 콜백 수신 대기 중... (최대 {WAIT_TIMEOUT_SEC}초)")
    deadline = time.time() + WAIT_TIMEOUT_SEC
    elapsed = 0

    while time.time() < deadline:
        try:
            resp = httpx.get(RECEIVED_URL, timeout=2.0)
            data = resp.json()
            if data.get("received"):
                print(f"  ✅ 콜백 수신 완료! ({elapsed}초 경과)")
                return data.get("payload")
        except Exception:
            pass

        time.sleep(POLL_INTERVAL_SEC)
        elapsed += POLL_INTERVAL_SEC
        print(f"  ... {elapsed}초 경과 (대기 중)")

    return None


def print_callback_payload(payload: dict):
    """수신된 콜백 내용 상세 출력"""
    print("\n  📨 Python → Spring 전송 내용 (Webhook Payload):")
    print(f"  {'─'*50}")
    print(f"  {'intvId':<20}: {payload.get('intvId')}")
    print(f"  {'status':<20}: {payload.get('status')}")
    print(f"  {'errorMessage':<20}: {payload.get('errorMessage')}")
    print(f"\n  {'questions':<20}:")

    questions = payload.get("questions", [])
    if questions:
        for i, q in enumerate(questions, 1):
            print(f"    Q{i}. {q}")
    else:
        print("    (질문 없음)")

    print("\n  💡 camelCase 키 확인:")
    print(f"    {'intvId' in payload        and '✅ intvId' or '❌ intvId 없음'}")
    print(
        f"    {'errorMessage' in payload  and '✅ errorMessage' or '❌ errorMessage 없음'}"
    )
    print(
        f"    {'intv_id' not in payload   and '✅ snake_case 없음 (정상)' or '❌ snake_case 노출됨'}"
    )


def run():
    print("\n" + "🎭" * 30)
    print("  가면 (Gamyeon) — Question Feature 수동 검증")
    print("🎭" * 30)

    # STEP 0. 서버 상태 확인
    step(0, "서버 상태 사전 확인")
    if not check_servers():
        print("\n❌ 서버를 먼저 실행해주세요.")
        return

    # STEP 1. 콜백 수신 서버 초기화
    step(1, "콜백 수신 서버 초기화")
    reset_callback_receiver()

    # STEP 2. Spring → Python 질문 생성 요청
    step(2, "Spring → Python: 질문 생성 요청 발송")
    result = send_spring_request()

    print("\n  📬 Python 즉시 응답:")
    print(
        f"      HTTP Status : {result['status_code']} ({'✅ 202 Accepted' if result['status_code'] == 202 else '❌ 예상과 다름'})"
    )
    print(f"      Body        : {result['body']}")

    if result["status_code"] != 202:
        print("\n❌ 202 응답이 아닙니다. 서버 로그를 확인하세요.")
        return

    # STEP 3. 파이프라인 완료 대기 및 콜백 수신 확인
    step(3, "Python → Spring: Webhook 콜백 수신 대기")
    payload = wait_for_callback()

    # STEP 4. 결과 출력
    step(4, "최종 결과 확인")

    if payload is None:
        print(f"\n  ❌ {WAIT_TIMEOUT_SEC}초 내에 콜백이 수신되지 않았습니다.")
        print("  → 메인 서버 로그를 확인하세요. (DLQ 로그 또는 에러 메시지)")
        return

    print_callback_payload(payload)

    # STEP 5. 최종 검증 요약
    step(5, "검증 요약")
    status = payload.get("status")
    questions = payload.get("questions", [])

    checks = [
        ("202 Accepted 즉시 반환", result["status_code"] == 202),
        ("콜백 수신 완료", payload is not None),
        ("intvId 일치", payload.get("intvId") == SPRING_REQUEST_EXAMPLE["intvId"]),
        ("status SUCCESS", status == "SUCCESS"),
        ("질문 4개 생성", len(questions) == 4),
        ("camelCase 형식 준수", "intvId" in payload and "intv_id" not in payload),
    ]

    all_passed = True
    for name, passed in checks:
        icon = "✅" if passed else "❌"
        print(f"  {icon} {name}")
        if not passed:
            all_passed = False

    print()
    if all_passed:
        print("  🎉 모든 검증 통과! Question Feature 정상 동작 확인 완료.")
    else:
        print("  ⚠️  일부 검증 실패. 위 항목을 확인하세요.")


if __name__ == "__main__":
    run()
