"""K-12 개념 콘텐츠 코퍼스 빌드 CLI — xlsx → content.json + _provenance.json.

`concept_content_university/__main__.py` 미러. extract(개념+암기카드 조인) → validate → write
(자체작성 표지 + provenance sha256). 원본 xlsx 미커밋(휘발 → sha256 재현성). **K-12 성취기준
본문은 미수록**·연결 성취기준 코드만 보존. 콘텐츠 DB 투영은 Phase 3.

사용:
    python -m data_pipeline.concept_content \
        --input /path/master.xlsx \
        --output-dir data/corpus/concept_content_v1
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections.abc import Mapping
from datetime import datetime, timezone
from pathlib import Path

from data_pipeline.concept_content.extract import extract_k12_content
from data_pipeline.concept_content.models import (
    LICENSE_NOTICE,
    SOURCE_CITATION,
    ConceptContent,
)
from data_pipeline.concept_content.validate import validate_content

_CRAWLER_VERSION = "0.1.0"
_DEFAULT_OUTPUT_DIR = Path("data/corpus/concept_content_v1")
_SOURCE_NAME = "54c14913-260622__________________.xlsx"


def _now() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


def _collection(items: list[ConceptContent]) -> dict[str, object]:
    return {
        "source_citation": SOURCE_CITATION,
        "license_notice": LICENSE_NOTICE,
        "scope": "K-12",
        "collected_at": _now(),
        "crawler_version": _CRAWLER_VERSION,
        "content": [c.model_dump(mode="json") for c in items],
    }


def _write_json(path: Path, payload: Mapping[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="concept-content-build",
        description="통합마스터 xlsx → K-12 개념 콘텐츠 코퍼스(자체작성·검수필요·NCIC 본문 미수록)",
    )
    parser.add_argument("--input", type=Path, required=True, help="통합마스터 xlsx 경로")
    parser.add_argument("--output-dir", type=Path, default=_DEFAULT_OUTPUT_DIR)
    args = parser.parse_args(argv)

    if not args.input.exists():
        print(f"입력 xlsx 없음: {args.input}")
        return 2

    items = extract_k12_content(args.input)
    report = validate_content(items)
    print(report.summary())
    if not report.is_valid:
        print("검증 실패(error 존재) — 코퍼스를 쓰지 않습니다.")
        return 1

    out: Path = args.output_dir
    _write_json(out / "content.json", _collection(items))
    digest = hashlib.sha256(args.input.read_bytes()).hexdigest()
    _write_json(
        out / "_provenance.json",
        {
            "source_sha256": digest,
            "source_name": _SOURCE_NAME,
            "uploaded": datetime.now(tz=timezone.utc).date().isoformat(),
            "counts": {
                "content": len(items),
                "flashcards": report.flashcard_count,
                "subjects": report.subject_count,
            },
            "source_citation": SOURCE_CITATION,
            "license_notice": LICENSE_NOTICE,
            "post_extraction": [
                "개념(학교급!='대학교') 437 + 암기카드 조인 추출. 대학 비추출(U4 별도).",
                "성취기준 본문 미수록(NCIC)·연결 성취기준 코드만 보존. 정식정의=학생 비노출. "
                "DB 투영 Phase 3.",
            ],
        },
    )
    print(
        f"K-12 콘텐츠 코퍼스 작성: {out} (content={len(items)}·"
        f"flashcards={report.flashcard_count}·subjects={report.subject_count}·sha256={digest[:12]}…)"
    )
    return 0


if __name__ == "__main__":  # pragma: no cover — CLI 진입점
    raise SystemExit(main())
