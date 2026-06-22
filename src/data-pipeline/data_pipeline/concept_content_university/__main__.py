"""대학 소단원 콘텐츠 코퍼스 빌드 CLI — xlsx → content.json + _provenance.json.

`standards_university/__main__.py` 미러. extract(개념+암기카드 조인) → validate → write(자체작성
표지 + provenance sha256). 원본 xlsx 미커밋(휘발 → sha256 재현성). 콘텐츠 DB 투영은 Phase 3.

사용:
    python -m data_pipeline.concept_content_university \
        --input /path/standards_master.xlsx \
        --output-dir data/corpus/concept_content_university_v1
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections.abc import Mapping
from datetime import datetime, timezone
from pathlib import Path

from data_pipeline.concept_content_university.extract import extract_university_content
from data_pipeline.concept_content_university.models import (
    LICENSE_NOTICE,
    SOURCE_CITATION,
    UniversityConceptContent,
)
from data_pipeline.concept_content_university.validate import validate_content

_CRAWLER_VERSION = "0.1.0"
_DEFAULT_OUTPUT_DIR = Path("data/corpus/concept_content_university_v1")


def _now() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


def _collection(items: list[UniversityConceptContent]) -> dict[str, object]:
    return {
        "source_citation": SOURCE_CITATION,
        "license_notice": LICENSE_NOTICE,
        "scope": "대학",
        "collected_at": _now(),
        "crawler_version": _CRAWLER_VERSION,
        "content": [c.model_dump(mode="json") for c in items],
    }


def _write_json(path: Path, payload: Mapping[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="concept-content-university-build",
        description="대학 통합마스터 xlsx → 대학 소단원 콘텐츠 코퍼스(자체작성·검수필요)",
    )
    parser.add_argument("--input", type=Path, required=True, help="통합마스터 xlsx 경로")
    parser.add_argument("--output-dir", type=Path, default=_DEFAULT_OUTPUT_DIR)
    args = parser.parse_args(argv)

    if not args.input.exists():
        print(f"입력 xlsx 없음: {args.input}")
        return 2

    items = extract_university_content(args.input)
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
            "source_name": "수학과_성취기준_통합마스터(2026-06-16).xlsx",
            "uploaded": datetime.now(tz=timezone.utc).date().isoformat(),
            "counts": {
                "content": len(items),
                "flashcards": report.flashcard_count,
                "subjects": report.subject_count,
            },
            "source_citation": SOURCE_CITATION,
            "license_notice": LICENSE_NOTICE,
            "post_extraction": [
                "개념(학교급=='대학교') 콘텐츠 + 암기카드(소단원 코드) 조인 추출. 초중고 비추출.",
                "정식정의=학생 비노출(내부·검수용)·전 콘텐츠 AI 추정·검수필요. DB 투영은 Phase 3.",
            ],
        },
    )
    print(
        f"대학 콘텐츠 코퍼스 작성: {out} (content={len(items)}·"
        f"flashcards={report.flashcard_count}·subjects={report.subject_count}·sha256={digest[:12]}…)"
    )
    return 0


if __name__ == "__main__":  # pragma: no cover — CLI 진입점
    raise SystemExit(main())
