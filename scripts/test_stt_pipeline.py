"""
STT 파이프라인 로컬 테스트 스크립트

테스트 범위:
  S1~S3: MediaPreprocessor (S3 다운로드 → 검증 → WAV 추출)
  S4:    WhisperSTTAdapter  (faster-whisper STT)
  S5:    ClaudeHaikuAdapter (LLM 교정)

시선처리(S6~S8)는 데이터 없으므로 제외.

사전 준비:
  pip install faster-whisper anthropic boto3 pyyaml

필수 환경변수 (.env 또는 터미널에서 export):
  AWS_ACCESS_KEY_ID
  AWS_SECRET_ACCESS_KEY
  AWS_DEFAULT_REGION   (또는 AWS_REGION)
  S3_BUCKET            S3 버킷 이름

실행 방법 (app/ 디렉토리에서):
  cd /path/to/gamyeon-AI/app
  python ../scripts/test_stt_pipeline.py

선택 인자 (기본값 있음):
  S3_KEY       테스트할 S3 키  (기본: answers/1/answer1.mp4)
  TECH_STACK   쉼표 구분 기술스택 (기본: "")
  WHISPER_DEVICE   cpu | cuda  (기본: cpu)
  WHISPER_COMPUTE  int8 | float16 (기본: int8)
"""

import asyncio
import os
import sys
from dotenv import load_dotenv 
from pathlib import Path

load_dotenv(Path(__file__).parent.parent / ".env")

# app/ 디렉토리를 sys.path에 추가 (scripts/ 에서 실행 시 대비)
APP_DIR = Path(__file__).parent.parent / "app"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

# ── 환경변수 읽기 ──────────────────────────────────────────────────
S3_KEY         = os.environ.get("S3_KEY",            "answers/1/answer1.mp4")
S3_BUCKET      = os.environ.get("S3_BUCKET",         "")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
TECH_STACK     = [t.strip() for t in os.environ.get("TECH_STACK", "").split(",") if t.strip()]
DEVICE         = os.environ.get("WHISPER_DEVICE",    "cpu")
COMPUTE_TYPE   = os.environ.get("WHISPER_COMPUTE",   "int8")
LLM_MODEL      = os.environ.get("LLM_MODEL",         "gpt-4o-mini")

def _check_env() -> None:
    missing = []
    if not S3_BUCKET:      missing.append("S3_BUCKET")
    if not OPENAI_API_KEY: missing.append("OPENAI_API_KEY")
    if missing:
        print(f"[ERROR] 필수 환경변수 누락: {', '.join(missing)}")
        sys.exit(1)


def _hr(title: str) -> None:
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")


async def main() -> None:
    _check_env()

    from media.application.service_helper.media_preprocessor import MediaPreprocessor
    from media.infrastructure.whisper_stt_adapter            import WhisperSTTAdapter
    from media.infrastructure.gpt_mini_adapter               import GptMiniAdapter

    # ── S1~S3: 전처리 ─────────────────────────────────────────────
    _hr("S1~S3  MediaPreprocessor  (S3 다운로드 → 검증 → WAV 추출)")
    print(f"  S3 key  : {S3_BUCKET}/{S3_KEY}")

    preprocessor = MediaPreprocessor(s3_bucket=S3_BUCKET)

    extracted = await asyncio.to_thread(
        preprocessor.preprocess,
        S3_KEY,
        1,   # interview_id
        1,   # question_id
    )
    print(f"  wav_path    : {extracted.wav_path}")
    print(f"  duration_ms : {extracted.duration_ms} ms  ({extracted.duration_ms/1000:.1f}s)")

    # ── S4: STT ───────────────────────────────────────────────────
    _hr("S4  WhisperSTTAdapter  (faster-whisper)")
    print(f"  device={DEVICE}  compute_type={COMPUTE_TYPE}")
    print(f"  tech_stack={TECH_STACK or '(없음)'}")
    print("  모델 로드 중... (처음 실행 시 수 분 소요)")

    stt_adapter = WhisperSTTAdapter(device=DEVICE, compute_type=COMPUTE_TYPE)
    stt_result  = await stt_adapter.transcribe(
        audio_path=extracted.wav_path,
        tech_stack=TECH_STACK,
    )

    print(f"\n  [STT 결과]")
    print(f"  model             : {stt_result.stt_model_used.value}")
    print(f"  language_prob     : {stt_result.language_probability:.3f}")
    print(f"  word_count        : {len(stt_result.word_timestamps)}")
    print(f"  raw_transcript    :\n    {stt_result.raw_transcript}")

    # ── S5: LLM 교정 ──────────────────────────────────────────────
    _hr("S5  ClaudeHaikuAdapter  (LLM CoT 교정)")

    gpt_adapter = GptMiniAdapter(api_key=OPENAI_API_KEY, model=LLM_MODEL)
    correction     = await gpt_adapter.correct(
        raw_transcript=stt_result.raw_transcript,
        tech_stack=TECH_STACK,
    )

    print(f"\n  [교정 결과]")
    print(f"  degraded              : {correction.degraded}")
    print(f"  phonetic_corrected    : {correction.phonetic_corrected}")
    print(f"  correction_count      : {len(correction.corrections)}")
    print(f"  corrected_transcript  :\n    {correction.corrected_transcript}")

    if correction.corrections:
        print(f"\n  [교정 항목]")
        for i, c in enumerate(correction.corrections, 1):
            print(f"  {i}. '{c.original}' → '{c.corrected}'  type={c.type.value}  pos={c.position}  conf={c.confidence:.2f}")

    # ── 정리 ──────────────────────────────────────────────────────
    _hr("완료")
    preprocessor.cleanup(interview_id=1, question_id=1)
    print("  임시 파일 제거 완료")


if __name__ == "__main__":
    asyncio.run(main())
