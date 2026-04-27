"""
구조화 로그 설정.

dlq 로거:
- 기본 경로: LOG_DIR 환경변수 (기본값 /var/log/dlq)
- 권한 없을 경우 ./logs/dlq 로 폴백
"""

import logging
import logging.config
import os
from pathlib import Path


def setup_logging(log_dir: str | None = None) -> None:
    if log_dir is None:
        log_dir = os.getenv("LOG_DIR", "/var/log/dlq")

    try:
        Path(log_dir).mkdir(parents=True, exist_ok=True)
    except PermissionError:
        log_dir = "./logs/dlq"
        Path(log_dir).mkdir(parents=True, exist_ok=True)

    logging.config.dictConfig({
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "json": {
                # 메시지 자체가 이미 JSON이므로 포맷 최소화
                "format": "%(message)s",
            },
            "standard": {
                "format": "%(asctime)s %(levelname)s %(name)s %(message)s",
            },
        },
        "handlers": {
            "console": {
                "class":     "logging.StreamHandler",
                "formatter": "standard",
            },
            # DLQ 파일 핸들러(MVP1)
            "dlq_file": {
                "class":       "logging.handlers.RotatingFileHandler",
                "filename":    f"{log_dir}/dlq.log",
                "maxBytes":    10 * 1024 * 1024,  # 10MB
                "backupCount": 5,
                "formatter":   "json",
                "encoding":    "utf-8",
            },
        },
        "loggers": {
            # DLQ 전용 로거 — MVP2에서 Loki 핸들러 추가
            "dlq": {
                "handlers":  ["dlq_file"],
                "level":     "CRITICAL",
                "propagate": False,
            },
        },
        "root": {
            "handlers": ["console"],
            "level":    "INFO",
        },
    })