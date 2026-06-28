import asyncio
import fitz
from concurrent.futures import ThreadPoolExecutor
from app.question.application.port.pdf_extract_port import PdfExtractPort
from app.question.exception import PdfExtractError


MAX_CHARS_RESUME = 3000
MAX_CHARS_OTHER = 2000


_executor = ThreadPoolExecutor(max_workers=4)


class PyMuPDFAdapter(PdfExtractPort):

    async def extract(self, file_bytes: bytes, max_chars: int = MAX_CHARS_RESUME) -> str:
        try:
            loop = asyncio.get_event_loop()
            # 동기 블로킹 코드를 스레드풀로 격리
            text = await loop.run_in_executor(
                _executor,
                self._extract_sync,
                file_bytes,
                max_chars
            )
            return text
        except PdfExtractError:
            raise
        except Exception as e:
            raise PdfExtractError(f"PDF 처리 중 오류: {e}") from e

    def _extract_sync(self, file_bytes: bytes, max_chars: int) -> str:
        doc = fitz.open(stream=file_bytes, filetype="pdf")
        text = "\n".join([page.get_text() for page in doc])
        doc.close()

        if not text.strip():
            raise PdfExtractError("스캔본 PDF이거나 텍스트가 없습니다.")

        return text[:max_chars]