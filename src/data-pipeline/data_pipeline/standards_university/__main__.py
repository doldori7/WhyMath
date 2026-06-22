"""대학 성취기준 코퍼스 빌드 CLI — xlsx → standards.json·concept_standard_links.json·_provenance.

`atom_graph/__main__.py`·`ncic` 선례 미러. 파이프라인: extract(대학 행) → transform(모델) →
validate(집합 invariant) → write(Collection JSON·자체작성 표지 + provenance sha256). 원본 xlsx는
**커밋하지 않는다**(K-12 NCIC 본문 포함) — provenance의 sha256으로 재현성을 보장한다.

사용:
    python -m data_pipeline.standards_university \
        --input /path/standards_master.xlsx \
        --output-dir data/corpus/standards_university_v1
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections.abc import Mapping
from datetime import datetime, timezone
from pathlib import Path

from data_pipeline.standards_university.extract import extract_university_standard_rows
from data_pipeline.standards_university.models import (
    LICENSE_NOTICE,
    SOURCE_CITATION,
    UniversityConceptStandardLink,
    UniversityStandard,
)
from data_pipeline.standards_university.transform import transform_rows
from data_pipeline.standards_university.validate import validate_standards

_CRAWLER_VERSION = "0.1.0"
_DEFAULT_OUTPUT_DIR = Path("data/corpus/standards_university_v1")


def _now() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


def _standards_collection(standards: list[UniversityStandard]) -> dict[str, object]:
    """성취기준 Collection(자체작성 표지 + standards 배열). backend 로더가 `standards`만 읽는다."""
    return {
        "source_citation": SOURCE_CITATION,
        "license_notice": LICENSE_NOTICE,
        "curriculum_revision": "대학",
        "collected_at": _now(),
        "crawler_version": _CRAWLER_VERSION,
        "standards": [s.model_dump(mode="json") for s in standards],
    }


def _links_collection(links: list[UniversityConceptStandardLink]) -> dict[str, object]:
    """링크 Collection(자체작성 표지 + links 배열). backend 로더가 `links`만 읽는다."""
    return {
        "source_citation": SOURCE_CITATION,
        "license_notice": LICENSE_NOTICE,
        "curriculum_revision": "대학",
        "collected_at": _now(),
        "crawler_version": _CRAWLER_VERSION,
        "links": [link.model_dump(mode="json") for link in links],
    }


def _write_json(path: Path, payload: Mapping[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _write_provenance(
    path: Path, *, source: Path, standards: int, links: int, subjects: int
) -> str:
    """_provenance.json 작성(원본 미커밋 → sha256으로 재현성). 반환=sha256."""
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    payload = {
        "source_sha256": digest,
        "source_name": "수학과_성취기준_통합마스터(2026-06-16).xlsx",
        "uploaded": datetime.now(tz=timezone.utc).date().isoformat(),
        "counts": {"standards": standards, "links": links, "subjects": subjects},
        "source_citation": SOURCE_CITATION,
        "license_notice": LICENSE_NOTICE,
        "post_extraction": [
            "성취기준_목록 시트의 학교급=='대학교' 행만 추출(NCIC K-12 본문 비추출·라이선스 분리).",
            "소단원(개념ID)↔성취기준 1:1 — 각 성취기준이 한 링크(link_type='직접')를 생성.",
            "대학 성취기준 본문=자체작성(AI 추정·검수필요)·redaction 불요(NCIC 공공누리 아님).",
        ],
    }
    _write_json(path, payload)
    return digest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="standards-university-build",
        description="대학 성취기준 통합마스터 xlsx → 자체작성 standards 코퍼스(+링크·provenance)",
    )
    parser.add_argument("--input", type=Path, required=True, help="통합마스터 xlsx 경로")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=_DEFAULT_OUTPUT_DIR,
        help=f"코퍼스 출력 디렉터리(기본 {_DEFAULT_OUTPUT_DIR})",
    )
    args = parser.parse_args(argv)

    if not args.input.exists():
        print(f"입력 xlsx 없음: {args.input}")
        return 2

    rows = extract_university_standard_rows(args.input)
    standards, links = transform_rows(rows)
    report = validate_standards(standards, links)
    print(report.summary())
    if not report.is_valid:
        print("검증 실패(error 존재) — 코퍼스를 쓰지 않습니다.")
        return 1

    out: Path = args.output_dir
    _write_json(out / "standards.json", _standards_collection(standards))
    _write_json(out / "concept_standard_links.json", _links_collection(links))
    digest = _write_provenance(
        out / "_provenance.json",
        source=args.input,
        standards=len(standards),
        links=len(links),
        subjects=report.subject_count,
    )
    print(
        f"대학 성취기준 코퍼스 작성: {out} "
        f"(standards={len(standards)}·links={len(links)}·subjects={report.subject_count}·"
        f"sha256={digest[:12]}…)"
    )
    return 0


if __name__ == "__main__":  # pragma: no cover — CLI 진입점
    raise SystemExit(main())
