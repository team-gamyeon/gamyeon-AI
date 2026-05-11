
# 가면 (Gamyeon) — AI 모의 면접 시뮬레이터

AI와 함께하는 실전형 면접 연습 플랫폼입니다.
이력서 기반 맞춤형 질문 생성부터 답변 피드백까지, 면접의 전 과정을 시뮬레이션합니다.

---

## 서비스 소개

취업 준비생이 실제 면접과 유사한 환경에서 연습할 수 있도록
AI가 면접관 역할을 수행합니다.

- 업로드한 이력서와 직군을 분석하여 맞춤형 면접 질문을 생성합니다.
- 음성으로 답변하면 STT가 텍스트로 변환하고, LLM이 피드백을 제공합니다.
- 면접 이력을 대시보드로 관리하고 성장 과정을 확인할 수 있습니다.

---

## 주요 기능

  AI 면접 질문 생성
  - 이력서(필수) / 포트폴리오(선택) 기반 맞춤형 질문 생성
  - 공용 질문 + AI 생성 질문 혼합 출제 (최대 7문항)

  음성 답변 처리
  - 음성 답변을 Whisper STT△ 로 텍스트 변환
  - 한국어 / 영어 혼용 답변 지원

  답변 피드백
  - 면접 종료 후 전체 답변 일괄 평가
  - 특징 / 잘한 점 / 개선점 항목별 제공

  시선 처리 해석
  - 면접 중 시선 데이터 수집 및 집중도 분석

  면접 이력 관리
  - 대시보드에서 과거 면접 기록 조회
  - 회차별 피드백 열람

---

## 기술 스택

  Backend (Spring)
  - Java / Spring Boot
  - Spring Security + JWT
  - Spring Cloud Gateway
  - JPA / PostgreSQL
  - Gradle Multi Module
  - DDD + Half Hexagonal Architecture

  AI Server (Python)
  - Python / FastAPI
  - LangChain
  - OpenAI GPT-4o / Whisper
  - UV (패키지 관리)
  - Half Hexagonal Architecture

  Storage
  - PostgreSQL (사용자 / 세션 / 질문 데이터)
  - NoSQL (면접 피드백 보고서)
  - AWS S3 (파일 저장)

  Infra
  - GitHub Actions (CI/CD)
  - Docker

---

## 시스템 아키텍처
```

  [클라이언트]
       |
  [API Gateway]          인증 / 라우팅 / Rate Limit
       |
  ┌────┴────────────────────────┐
  |                             |
  [Spring 서버]             [Backoffice 서버]
  메인 서비스                   관리자 기능
  ├── user
  ├── interview
  ├── evaluation
  └── notification
       |
       | REST, Webhook
       |
  [Python AI 서버]         FastAPI + LangChain
  ├── question/            면접 질문 생성
  ├── evaluation/          답변 평가
  ├── feedback/            종합 피드백
  ├── stt/                 음성 → 텍스트
  ├── resume/              이력서 파싱
  └── agent/               2차 MVP 예정

```


## 개발 로드맵

  1차 MVP (진행 중)
  - 이력서 기반 AI 질문 생성
  - 음성 답변 STT 변환
  - 답변 피드백 생성
  - 면접 이력 대시보드
  - 시선 처리 해석


---



## 로컬 실행 방법 - Python AI 서버

uv 설치
```
Windows: powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
macOS/Linux: curl -LsSf https://astral.sh/uv/install.sh | sh
```

설치 후에는 VS Code를 완전히 껐다가 다시 켜야 터미널에서 uv 명령어를 인식합니다. 



**① 서버 실행**
```bash
uv run uvicorn app.main:app --reload
```

**② `http://localhost:8000/docs` 접속**


**③ `/internal/questions/generate` 클릭 → `Try it out` 클릭**

***

**④ Request Body 입력**

이력서만 있는 경우:
```json
{
  "resume_url": "sample/resume.pdf",
  "portfolio_url": null,
  "self_introduction_url": null,
  "job_role": "백엔드 개발자"
}
```

이력서 + 포트폴리오 있는 경우:
```json
{
  "resume_url": "sample/resume.pdf",
  "portfolio_url": "sample/portfolio.pdf",
  "self_introduction_url": null,
  "job_role": "백엔드 개발자"
}
```

이력서 + 포트폴리오 + 자기소개서 모두 있는 경우:
```json
{
  "resume_url": "sample/resume.pdf",
  "portfolio_url": "sample/portfolio.pdf",
  "self_introduction_url": "sample/self_introduction.pdf",
  "job_role": "백엔드 개발자"
}
```

**⑤ `Execute` 클릭**

###  예상 정상 응답

```json
{
  "questions": [
    "백엔드 개발자로서 RESTful API 설계 시 어떤 원칙을 중요하게 생각하시나요?",
    "PostgreSQL과 MySQL을 모두 사용해보셨는데, 두 DB의 차이점과 각각 어떤 상황에서 선택하셨나요?",
    "FastAPI와 Express.js를 함께 사용한 경험이 있으신데, 두 프레임워크의 장단점을 비교해주세요.",
    "클린 아키텍처를 지향하신다고 하셨는데, 실제 프로젝트에서 어떻게 적용하셨나요?"
  ]
}
```

**⑥ 파일 경로 주의사항**

`sample/resume.pdf` 경로는 **서버 실행 위치 기준**입니다. 
프로젝트 루트에서 서버를 실행했다면 아래 구조여야 합니다.

```
gamyeon-AI/
└── sample/
    ├── resume.pdf        ← 실제 파일 존재 확인
    ├── portfolio.pdf
    └── self_introduction.pdf

  환경변수 (.env)
    OPENAI_API_KEY=your-openai-api-key
    ENVIRONMENT=development
````