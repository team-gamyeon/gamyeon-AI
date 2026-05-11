import pytest
from unittest.mock import AsyncMock

from app.question.application.service import QuestionService
from app.question.domain.interview_input import InterviewInput
from app.question.schema.request import FileEntry, QuestionGenerateRequest


def make_request(file_types: list[str]) -> QuestionGenerateRequest:
    return QuestionGenerateRequest(
        intvId=1,
        files=[FileEntry(fileType=ft, fileKey=f"{ft.lower()}.pdf") for ft in file_types],
    )


@pytest.fixture
def mock_s3():
    port = AsyncMock()
    port.download.return_value = b"pdf_bytes"
    return port


@pytest.fixture
def mock_pdf():
    port = AsyncMock()
    port.extract.return_value = "추출된 이력서 텍스트 내용입니다."
    return port


@pytest.fixture
def mock_struct():
    port = AsyncMock()
    port.structure.return_value = InterviewInput(name="테스트")
    return port


@pytest.fixture
def mock_qgen():
    port = AsyncMock()
    port.generate.return_value = ["Q1", "Q2", "Q3", "Q4"]
    return port


@pytest.fixture
def mock_callback():
    return AsyncMock()


@pytest.fixture
def service(mock_s3, mock_pdf, mock_struct, mock_qgen, mock_callback):
    return QuestionService(
        s3_download_port=mock_s3,
        pdf_extract_port=mock_pdf,
        structuring_port=mock_struct,
        question_gen_port=mock_qgen,
        callback_port=mock_callback,
    )


# ── RESUME 필수 정책 ─────────────────────────────────────────────


class TestResumeMandatory:

    @pytest.mark.asyncio
    async def test_no_files_sends_failed_callback(self, service, mock_callback):
        await service.run(make_request([]))

        mock_callback.send.assert_called_once()
        payload = mock_callback.send.call_args.kwargs["payload"]
        assert payload.status == "FAILED"
        assert payload.questions == []
        assert payload.errorMessage is not None

    @pytest.mark.asyncio
    async def test_portfolio_only_sends_failed_callback(self, service, mock_callback):
        # RESUME 없이 선택 파일만 있는 경우
        await service.run(make_request(["PORTFOLIO"]))

        mock_callback.send.assert_called_once()
        payload = mock_callback.send.call_args.kwargs["payload"]
        assert payload.status == "FAILED"
        assert payload.questions == []

    @pytest.mark.asyncio
    async def test_self_introduction_only_sends_failed_callback(self, service, mock_callback):
        await service.run(make_request(["SELF_INTRODUCTION"]))

        payload = mock_callback.send.call_args.kwargs["payload"]
        assert payload.status == "FAILED"

    @pytest.mark.asyncio
    async def test_resume_present_sends_success_callback(self, service, mock_callback):
        await service.run(make_request(["RESUME"]))

        mock_callback.send.assert_called_once()
        payload = mock_callback.send.call_args.kwargs["payload"]
        assert payload.status == "SUCCESS"
        assert payload.questions == ["Q1", "Q2", "Q3", "Q4"]
        assert payload.errorMessage is None

    @pytest.mark.asyncio
    async def test_resume_with_optional_files_succeeds(self, service, mock_callback):
        await service.run(make_request(["RESUME", "PORTFOLIO", "SELF_INTRODUCTION"]))

        payload = mock_callback.send.call_args.kwargs["payload"]
        assert payload.status == "SUCCESS"


# ── finally 콜백 보장 정책 ───────────────────────────────────────


class TestCallbackAlwaysSent:

    @pytest.mark.asyncio
    async def test_s3_failure_still_sends_callback(self, service, mock_s3, mock_callback):
        mock_s3.download.side_effect = Exception("S3 다운로드 실패")

        await service.run(make_request(["RESUME"]))

        mock_callback.send.assert_called_once()
        payload = mock_callback.send.call_args.kwargs["payload"]
        assert payload.status == "FAILED"
        assert payload.questions == []

    @pytest.mark.asyncio
    async def test_pdf_failure_still_sends_callback(self, service, mock_pdf, mock_callback):
        mock_pdf.extract.side_effect = ValueError("스캔본 PDF이거나 텍스트가 없습니다.")

        await service.run(make_request(["RESUME"]))

        mock_callback.send.assert_called_once()
        payload = mock_callback.send.call_args.kwargs["payload"]
        assert payload.status == "FAILED"
        assert payload.questions == []

    @pytest.mark.asyncio
    async def test_structuring_failure_still_sends_callback(
        self, service, mock_struct, mock_callback
    ):
        mock_struct.structure.side_effect = Exception("LLM 구조화 실패")

        await service.run(make_request(["RESUME"]))

        mock_callback.send.assert_called_once()
        payload = mock_callback.send.call_args.kwargs["payload"]
        assert payload.status == "FAILED"

    @pytest.mark.asyncio
    async def test_callback_failure_does_not_propagate(self, service, mock_callback):
        # 콜백 전송 자체가 실패해도 예외가 상위로 전파되지 않아야 함
        mock_callback.send.side_effect = Exception("webhook 전송 실패")

        await service.run(make_request([]))  # should not raise
