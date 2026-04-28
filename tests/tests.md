uv run uvicorn app.main:app --reload --port 8000

uv run python callback_receiver.py

들여쓰기 확인 !! 
# webhook 받는 애 
PS C:\Users\user\Documents\GitHub\gamyeon-AI> uv run python callback_receiver.py


### report 리포트 생성요청 test
(gamyeon-ai) PS C:\Users\user\Documents\GitHub\gamyeon-AI> 
curl.exe -X POST "http://localhost:8000/internal/v1/reports/generate" `
-H "Content-Type: application/json; charset=utf-8" `
-d "@request.json"   

# Event 
(gamyeon-ai) PS C:\Users\user\Documents\GitHub\gamyeon-AI> uv run python test_event_integration.py
(gamyeon-ai) PS C:\Users\user\Documents\GitHub\gamyeon-AI> uv run python callback_receiver.pyPS C:\Users\user\Documents\GitHub\gamyeon-AI> uv run uvicorn app.main:app --reload --port 8000
# question - test 
```
{
  "intvId": 123,
  "files": [
    {
      "fileType": "RESUME",
      "fileKey": "sample/resume.pdf"
    }
  ],
}

```

```
{
  "resume_url": "sample/resume.pdf",
  "portfolio_url": null,
  "self_introduction_url": null,
  "job_role": "백엔드 개발자"
}

{
  "resume_url": "https://gamyeon-s3-bucket.s3.ap-northeast-2.amazonaws.com/resume.pdf",
  "portfolio_url": null,
  "self_introduction_url": null,
  "job_role": "백엔드 개발자"
}
```
# feedback - test
```
{
  "intv_question_id": 101,
  "question_content": "본인의 강점에 대해 설명해주세요.",
  "corrected_transcript": "제 강점은 문제 해결 능력입니다. 프로젝트 진행 시 협업을 통해 효율적인 결과를 만들어냅니다.",
  "degraded": false,
  "reliability_score": 95,
  "gaze_score": 88,
  "time_score": 92,
  "answer_duration_ms": 45000,
  "keyword_candidates": [
    {
      "term": "문제 해결",
      "count": 1,
      "category": "역량"
    },
    {
      "term": "협업",
      "count": 1,
      "category": "태도"
    }
  ]
}
```

## report webhook 
## 리포트 생성 테스트 
```
# 터미널 1 — 수신 서버 실행
python tests/webhook_receiver.py

# 터미널 2 — AI 서버 실행
uvicorn app.main:app --reload --port 8000

# 터미널 3 — 리포트 생성 요청
curl -X POST http://localhost:8000/internal/v1/reports/generate \
  -H "Content-Type: application/json" \
  -d '{
    "intvId": 11,
    "userId": 3,
    "callback": "http://localhost:8080/internal/v1/reports/callback",
    "feedbacks": [...]
  }'

```