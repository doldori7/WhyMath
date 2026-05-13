"""NCIC 테스트 공통 픽스처."""

from __future__ import annotations

import io
from pathlib import Path

import pytest

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def html_middle_school_unit() -> str:
    """중학교 수학 수와 연산 합성 픽스처."""
    return (FIXTURES_DIR / "sample_math_unit.html").read_text(encoding="utf-8")


@pytest.fixture
def html_high_school_unit() -> str:
    """고등학교 공통수학1 다항식 합성 픽스처."""
    return (FIXTURES_DIR / "sample_high_school_unit.html").read_text(encoding="utf-8")


@pytest.fixture
def synthetic_pdf_text() -> str:
    """pdfplumber가 반환할 *것으로 가정하는* 한국어 텍스트.

    한국어 폰트 임베딩 없이 ASCII-only PDF로는 한글 성취기준을 표현할 수 없으므로
    (Type1 Helvetica는 한글을 렌더하지 못함), pdfplumber 자체를 모킹하여
    이 문자열을 반환시킨다. 실 PDF 파싱은 *통합 테스트*에서 한국어 폰트가 임베드된
    실 NCIC PDF로 검증해야 한다.
    """
    return (
        "교육부 고시 제2022-33호\n"
        "수학과 교육과정 [별책 8]\n\n"
        "(1) 수와 연산\n"
        "[9수01-01] 소인수분해의 뜻을 알고 자연수를 소인수분해할 수 있다.\n"
        "[9수01-02] 최대공약수와 최소공배수의 성질을 이해한다.\n\n"
        "(2) 다항식\n"
        "[10공수1-01-01] 다항식의 덧셈과 뺄셈의 원리를 이해하고, 그 계산을 할 수 있다.\n"
    )


@pytest.fixture
def synthetic_pdf_bytes() -> bytes:
    """동작 검증용 최소 ASCII PDF (한글 X).

    pdfplumber가 *로드 가능*한 PDF인지만 확인하는 용도.
    한국어 텍스트 검증은 `synthetic_pdf_text` + 모킹 사용.
    """
    return _build_minimal_pdf(
        [
            "PDF parser smoke test.",
            "This PDF has no Korean text by design.",
        ]
    )


def _build_minimal_pdf(text_lines: list[str]) -> bytes:
    """최소 PDF 1.4 문서를 생성 — 외부 의존성 없음.

    구조:
        1: Catalog
        2: Pages
        3: Page
        4: Font (Helvetica)
        5: Contents (text stream)
    """
    # 텍스트 스트림 작성
    stream_lines = ["BT", "/F1 12 Tf", "50 750 Td"]
    for line in text_lines:
        # PDF 문자열 이스케이프
        escaped = line.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
        stream_lines.append(f"({escaped}) Tj")
        stream_lines.append("0 -20 Td")
    stream_lines.append("ET")
    stream = "\n".join(stream_lines)
    stream_bytes = stream.encode("ascii")

    objects: list[bytes] = []
    # 1: Catalog
    objects.append(b"<< /Type /Catalog /Pages 2 0 R >>")
    # 2: Pages
    objects.append(b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>")
    # 3: Page
    objects.append(
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        b"/Contents 5 0 R /Resources << /Font << /F1 4 0 R >> >> >>"
    )
    # 4: Font
    objects.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
    # 5: Contents
    content_dict = f"<< /Length {len(stream_bytes)} >>".encode("ascii")
    objects.append(content_dict + b"\nstream\n" + stream_bytes + b"\nendstream")

    buf = io.BytesIO()
    buf.write(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets: list[int] = []
    for i, obj in enumerate(objects, start=1):
        offsets.append(buf.tell())
        buf.write(f"{i} 0 obj\n".encode("ascii"))
        buf.write(obj)
        buf.write(b"\nendobj\n")
    xref_offset = buf.tell()
    buf.write(b"xref\n")
    buf.write(f"0 {len(objects) + 1}\n".encode("ascii"))
    buf.write(b"0000000000 65535 f \n")
    for off in offsets:
        buf.write(f"{off:010d} 00000 n \n".encode("ascii"))
    buf.write(b"trailer\n")
    buf.write(f"<< /Size {len(objects) + 1} /Root 1 0 R >>\n".encode("ascii"))
    buf.write(b"startxref\n")
    buf.write(f"{xref_offset}\n".encode("ascii"))
    buf.write(b"%%EOF\n")
    return buf.getvalue()
