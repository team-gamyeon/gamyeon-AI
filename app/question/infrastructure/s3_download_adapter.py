import logging
import aioboto3
from botocore.exceptions import ClientError, NoCredentialsError
from app.core.config import settings
from app.question.application.port.s3_download_port import S3DownloadPort

logger = logging.getLogger(__name__)

# 앱 시작 시 1회만 생성 (싱글턴)
_session = aioboto3.Session(
    aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
    aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
    region_name=settings.AWS_REGION,
)

class S3DownloadAdapter(S3DownloadPort):
    def __init__(self, timeout: float = 30.0):
        self.timeout = timeout

    async def download(self, file_key: str) -> bytes:
        try:
            logger.info(f"S3 파일 다운로드 시작: {file_key}")

            async with _session.client("s3") as s3_client:  # type: ignore
                response = await s3_client.get_object(
                    Bucket=settings.S3_BUCKET, Key=file_key
                )
                file_data = await response["Body"].read()
                logger.info(f"S3 다운로드 완료: {len(file_data)} bytes")
                return file_data

        except ClientError as e:
            logger.error(f"S3 클라이언트 에러: {e}")
            error_code = e.response["Error"]["Code"]
            if error_code == "NoSuchKey":
                raise ValueError(f"S3 파일 없음: {file_key}") from e
            elif error_code == "AccessDenied":
                raise ValueError("S3 권한 없음") from e
            raise Exception(f"S3 에러: {error_code}") from e

        except NoCredentialsError:
            logger.error("AWS 자격증명 없음")
            raise ValueError("AWS 설정 확인") from None

        except Exception as e:
            logger.error(f"S3 다운로드 실패: {e}")
            raise Exception(f"S3 처리 실패: {e}") from e