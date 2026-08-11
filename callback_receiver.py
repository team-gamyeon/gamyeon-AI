# callback_receiver.py

#PS C:\Users\user\Documents\GitHub\gamyeon-AI> uv run python callback_receiver.py   
import json
from datetime import datetime

import uvicorn
from fastapi import FastAPI, Request

app = FastAPI()
# 스프링 섭를 대신하여 웹훅을 받는 코드, 9000


@app.post("/internal/v1/questions/callback")
async def receive_question_callback(request: Request):
    now = datetime.now()
    body = await request.json()

    print("🟢 WEBHOOK 수신 성공!")
    print("  📋 Payload:", body)
    print("  🆔 intvId:", body.get("intvId"))
    print("  ✅ Status:", body.get("status"))
    print("  ❓ Questions:", body.get("questions", []))
    print("  ❌ Error:", body.get("errorMessage"))
    print("현재 시간:", now)
    print("-" * 50)
    return {"status": "received"}


# 리포트 생성요청 테스트
@app.post("/internal/v1/reports/callback")
async def receive_callback(request: Request):
    body = await request.json()
    api_key = request.headers.get("X-Internal-API-Key")
    print("🔑 수신된 API Key:", api_key) 
    now = datetime.now()
    print("\n" + "=" * 60)
    print("✅ 콜백 수신!")
    print("현재 시간:", now)
    print(json.dumps(body, ensure_ascii=False, indent=2))
    print("=" * 60)
    return {"ok": True}



@app.post("/internal/v1/feedbacks/callback")
async def receive_feedback_callback(request: Request):
    body = await request.json()
    now = datetime.now()
    print("\n" + "=" * 60)
    print("✅ 피드백 콜백 수신!")
    print(json.dumps(body, ensure_ascii=False, indent=2))

    print("=" * 60)
    print("현재 시간:", now)
    return {"ok": True}


@app.get("/received")  # ← 폴링용 엔드포인트 추가
async def get_received():
    return received_data


@app.post("/reset")  # ← 초기화용 엔드포인트 추가
async def reset_received():
    global received_data
    received_data = {"received": False, "payload": None}
    return {"status": "reset"}


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=9000)
