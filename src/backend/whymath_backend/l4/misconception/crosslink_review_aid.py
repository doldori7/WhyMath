"""오개념 crosswalk 검수 *보조 리포트* — 검수 큐 행에 근거를 붙여 한 화면에 모은다(read-only).

crosswalk(kebab-id ↔ M-id) 행은 **사람 검수 산출물**이고(`crosslink_review.py` 정본),
승인/반려·서명·적재는 전부 Kiki의 몫이다(AI 자기승인·자동 적재 절대 금지). 그 원칙을 *그대로*
지키면서, 이 모듈은 promote 모듈이 선언한 기계의 몫 — **"검수를 30분 작업으로 만든다"** — 를
한 걸음 더 밀어준다: 검수자가 행별 승인/반려를 판단하려면 매번 두 원천을 손으로 대조해야 한다.
  ① kebab측: 그 오개념이 *무엇인지*(정의·반례·정정형) — `catalog.py::CATALOG_BY_ID`(코드 상수)
  ② M-id측: 후보 M-id가 *무엇인지*(학생 오사고·distractor 규칙·오류유형·성취기준) — 839행 코퍼스
75행 × (코드 상수 + 839행 JSON) 대조는 실제 토일이다. 이 모듈은 그 조인을 대신 해 **kebab별로**
후보들을 근거와 함께 나란히 출력한다 — 검수자는 리포트만 보고 approve/reject를 눈으로 판단한다.

**판정하지 않는다(핵심 불변)**: 근거를 *모으기만* 한다. status를 바꾸지 않고, 큐 파일을 쓰지
않으며, 어떤 행도 승인/반려로 표시하지 않는다(harvest가 측정만 하고 canary는 사람이 정하는 것과
동형). 실제 승인(status=approved+reviewer+reviewed_on)과 적재는 여전히
`crosslink_review.py promote --load`(사람 서명 강제) 단계다. 조인 근거가 큐 rationale과 어긋나면
그 자체가 검수 신호가 된다(전사 왜곡·오매핑 후보 발견).

**오프라인·순수·비노출**: HTTP/런타임/DB 경로 0(코드 카탈로그 + 코퍼스 JSON 파싱·조인). 학생
식별자·풀이 원문 없음(카탈로그 식별자·자체 코퍼스 텍스트만). `crosslink_shadow_harvest`의 정본
패턴(load·pure build·format·CLI, 마지막 줄은 파싱 가능한 JSON 요약)을 미러한다.

파이프라인:
    python -m whymath_backend.l4.misconception.crosslink_review_aid \\
        [--queue docs/data/misconception_crosslink_review_queue.json] \\
        [--corpus data/corpus/misconceptions_v1/misconceptions.json] [--status pending|all]
    → kebab별 근거 리포트(stdout) 검토 → 검수 큐 JSON에 status/reviewer/reviewed_on 손기입(사람)
    → crosslink_review.py promote --queue … --load
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict

from whymath_backend.l4.misconception.catalog import CATALOG_BY_ID
from whymath_backend.l4.misconception.crosslink_review import (
    CrosslinkReviewError,
    CrosslinkReviewItem,
    ReviewStatus,
    parse_review_queue,
)
from whymath_backend.l4.misconception.models import Misconception

# M-id 코퍼스(misconceptions_v1) top key — 로더가 읽는 정본 리스트 키.
_CORPUS_KEY = "misconceptions"

# 리포트 기본 대상 — 미검수(pending) 행만 모은다(검수가 필요한 것). "all"은 전 상태 포함.
DEFAULT_STATUSES: tuple[ReviewStatus, ...] = ("pending",)

# CLI 기본 경로(레포 루트 기준 — promote CLI 규약 동형·ops가 루트에서 실행).
DEFAULT_QUEUE_PATH = "docs/data/misconception_crosslink_review_queue.json"
DEFAULT_CORPUS_PATH = "data/corpus/misconceptions_v1/misconceptions.json"


class MisconceptionCorpusEntry(BaseModel):
    """M-id 코퍼스 1행의 *검수 관련* 부분집합 — 검수자가 후보 M-id를 판단할 근거 필드만.

    코퍼스(misconceptions_v1)는 16필드지만 검수에 쓰는 것만 담는다(`extra="ignore"`로 나머지
    무시 — 스키마 결합 최소화). `canonical_statement`(개념명)·`student_wrong_thinking`(학생 오사고)
    ·`distractor_rule`(오답 규칙)·`error_type`(오류유형)이 kebab 오개념과의 일치를 눈으로 대조할
    핵심 근거다.
    """

    model_config = ConfigDict(extra="ignore")

    mis_id: str
    canonical_statement: str | None = None
    student_wrong_thinking: str | None = None
    distractor_rule: str | None = None
    error_type: str | None = None
    standard_code: str | None = None
    domain: str | None = None
    subunit: str | None = None
    school_level: str | None = None


class CandidateEvidence(BaseModel):
    """검수 큐 1행(후보 링크) + 조인된 M-id 코퍼스 근거 — 검수자 판단 입력(read-only).

    큐측 필드(`link_type`·`confidence`·`rationale`·`status`)는 *전사 그대로*(사람이 검수할 초안
    신뢰도·근거)이고, 코퍼스측(`corpus`)은 M-id의 실제 내용이다. `corpus is None`이면 M-id가
    코퍼스에 없다(dangling 후보 — 전사 오탈자/폐기 M-id 의심·검수 신호).
    """

    model_config = ConfigDict(extra="forbid")

    mis_id: str
    link_type: str
    confidence: float | None
    rationale: str
    status: ReviewStatus
    corpus: MisconceptionCorpusEntry | None
    """조인된 M-id 코퍼스 근거 — None이면 코퍼스 미존재(dangling)."""

    @property
    def corpus_found(self) -> bool:
        """M-id가 코퍼스에 실재하는지 — False면 dangling 후보(검수 신호)."""
        return self.corpus is not None


class KebabReviewGroup(BaseModel):
    """kebab-id 1개에 묶인 후보 M-id들 + kebab 자체 근거 — 리포트의 검수 단위(한 화면).

    검수자는 이 그룹을 보고 "이 kebab 오개념(정의·반례)에 어떤 M-id 후보가 맞는가"를 판단한다.
    `kebab is None`이면 kebab-id가 L4 탐지 카탈로그에 없다 — 전사 왜곡 의심(promote도 이
    행을 거부하므로 리포트가 먼저 드러낸다).
    """

    model_config = ConfigDict(extra="forbid")

    kebab_id: str
    kebab: Misconception | None
    """kebab측 근거(정의·반례·정정형) — None이면 카탈로그 미존재(전사 왜곡 의심)."""

    candidates: list[CandidateEvidence]

    @property
    def kebab_found(self) -> bool:
        """kebab-id가 L4 카탈로그(CATALOG_BY_ID)에 실재하는지 — False면 전사 왜곡 신호."""
        return self.kebab is not None


class ReviewAidSummary(BaseModel):
    """리포트 요약 1건 — 리포트 마지막 줄 JSON(스냅샷·회귀·검수 진척 대시보드용).

    `format_review_aid` 마지막 줄로 emit되며, 검수 규모(kebab/후보 수)와 *검수 신호*(카탈로그 밖
    kebab·dangling M-id 후보 수)를 정량화한다 — 판정이 아니라 검수 착수 전 규모·위생 파악용.
    """

    model_config = ConfigDict(extra="forbid")

    statuses: list[str]
    """리포트가 포함한 검수 상태(기본 ['pending'])."""

    kebab_groups: int
    """리포트에 오른 서로 다른 kebab-id 수."""

    candidates: int
    """리포트에 오른 후보 링크(행) 총수."""

    kebab_not_in_catalog: list[str]
    """L4 카탈로그에 없는 kebab-id(정렬) — 전사 왜곡 검수 신호."""

    dangling_mis_ids: list[str]
    """코퍼스에 없는 후보 M-id(정렬·중복 제거) — 폐기/오탈자 M-id 검수 신호."""


def load_corpus(text: str) -> dict[str, MisconceptionCorpusEntry]:
    """M-id 코퍼스 JSON 텍스트 → `mis_id → 엔트리` 인덱스(검수 조인용).

    top key `"misconceptions"`(정본 리스트)를 읽어 mis_id로 인덱싱한다. **중복 mis_id는
    ValueError**(조용한 덮어쓰기 금지 — 코퍼스 무결성은 단일 진실 원천). top key 부재도 ValueError.
    """
    data = json.loads(text)
    if not isinstance(data, dict) or _CORPUS_KEY not in data:
        found = sorted(data) if isinstance(data, dict) else type(data).__name__
        raise ValueError(f"코퍼스 top key '{_CORPUS_KEY}' 없음: {found}")
    rows = data[_CORPUS_KEY]
    if not isinstance(rows, list):
        raise ValueError(f"'{_CORPUS_KEY}'는 배열이어야 합니다: {type(rows).__name__}")
    index: dict[str, MisconceptionCorpusEntry] = {}
    for row in rows:
        entry = MisconceptionCorpusEntry.model_validate(row)
        if entry.mis_id in index:
            raise ValueError(f"코퍼스 중복 mis_id: {entry.mis_id}(단일 진실 원천 위반)")
        index[entry.mis_id] = entry
    return index


def build_review_aid(
    items: Iterable[CrosslinkReviewItem],
    *,
    corpus: dict[str, MisconceptionCorpusEntry],
    catalog: dict[str, Misconception] | None = None,
    statuses: Iterable[ReviewStatus] = DEFAULT_STATUSES,
) -> list[KebabReviewGroup]:
    """검수 큐 행 + 코퍼스 → kebab별 근거 그룹(순수·결정론·판정 없음).

    `statuses`에 해당하는 행만 대상으로(기본 pending — 검수 대기분), kebab-id로 묶고 각 후보에
    코퍼스 근거를 조인한다. kebab측은 `catalog`(기본 `CATALOG_BY_ID`)에서 조인한다. 카탈로그/코퍼스
    미존재는 조인 결과를 None으로 두고 *그대로 실어* 검수 신호로 드러낸다(조용한 누락 금지). 그룹은
    kebab-id 정렬, 그룹 내 후보는 큐 순서(초안 신뢰도 내림차순 전사)를 보존한다.
    """
    resolved_catalog = CATALOG_BY_ID if catalog is None else catalog
    wanted = set(statuses)
    groups: dict[str, list[CandidateEvidence]] = {}
    for item in items:
        if item.status not in wanted:
            continue
        groups.setdefault(item.kebab_id, []).append(
            CandidateEvidence(
                mis_id=item.mis_id,
                link_type=item.link_type,
                confidence=item.confidence,
                rationale=item.rationale,
                status=item.status,
                corpus=corpus.get(item.mis_id),
            )
        )
    return [
        KebabReviewGroup(
            kebab_id=kebab_id,
            kebab=resolved_catalog.get(kebab_id),
            candidates=candidates,
        )
        for kebab_id, candidates in sorted(groups.items())
    ]


def summarize_review_aid(
    groups: Iterable[KebabReviewGroup], *, statuses: Iterable[ReviewStatus]
) -> ReviewAidSummary:
    """kebab 그룹 → 검수 규모·위생 요약(순수) — 카탈로그 밖 kebab·dangling M-id 정량화."""
    group_list = list(groups)
    candidate_count = sum(len(g.candidates) for g in group_list)
    not_in_catalog = sorted(g.kebab_id for g in group_list if not g.kebab_found)
    dangling = sorted({c.mis_id for g in group_list for c in g.candidates if not c.corpus_found})
    return ReviewAidSummary(
        statuses=[str(s) for s in statuses],
        kebab_groups=len(group_list),
        candidates=candidate_count,
        kebab_not_in_catalog=not_in_catalog,
        dangling_mis_ids=dangling,
    )


def _format_kebab_header(group: KebabReviewGroup) -> list[str]:
    """kebab측 근거 블록 — 정의(틀린 믿음)·반례·정정형. 카탈로그 미존재면 경고."""
    if group.kebab is None:
        return [
            f"## {group.kebab_id}  ⚠ L4 카탈로그에 없음 — 전사 왜곡 의심(promote도 거부)",
        ]
    k = group.kebab
    lines = [
        f"## {group.kebab_id}  ({k.name_kr} · {k.domain})",
        f"   틀린 믿음: {k.canonical_statement}",
        f"   반례: {k.counterexample}",
    ]
    if k.correct_form is not None:
        lines.append(f"   정정형: {k.correct_form}")
    return lines


def _format_candidate(cand: CandidateEvidence) -> list[str]:
    """후보 M-id 1건 — 큐측(link_type·conf·rationale) + 코퍼스측 근거. dangling이면 경고."""
    conf = "null" if cand.confidence is None else f"{cand.confidence:g}"
    head = f"   → {cand.mis_id}  [{cand.link_type} conf={conf} status={cand.status}]"
    if cand.corpus is None:
        return [
            head + "  ⚠ 코퍼스에 없음 — dangling(폐기/오탈자 M-id 의심)",
            f"     초안근거: {cand.rationale}",
        ]
    c = cand.corpus
    parts: list[str] = [head]
    if c.canonical_statement:
        # standard_code는 코퍼스에서 이미 '[9수02-19]' 형태로 대괄호를 포함(이중 대괄호 방지).
        std = f"  · 성취기준 {c.standard_code}" if c.standard_code else ""
        parts.append(f"     개념: {c.canonical_statement}{std}")
    if c.student_wrong_thinking:
        parts.append(f"     학생 오사고: {c.student_wrong_thinking}")
    if c.distractor_rule:
        parts.append(f"     distractor 규칙: {c.distractor_rule}")
    if c.error_type:
        parts.append(f"     오류유형: {c.error_type}")
    parts.append(f"     초안근거: {cand.rationale}")
    return parts


def format_review_aid(
    groups: Iterable[KebabReviewGroup], *, statuses: Iterable[ReviewStatus]
) -> str:
    """kebab 그룹 → 사람이 읽는 검수 보조 리포트(마지막 줄은 파싱 가능한 JSON 요약).

    상단은 검수 안내(판정은 사람 몫·다음 단계=promote), 본문은 kebab별 근거 블록, 마지막 줄은
    `ReviewAidSummary` 한 줄(스냅샷·회귀·검수 진척). **어떤 행도 승인/반려로 표시하지 않는다**
    (근거 집합만 — AI 자기승인 금지·harvest 동형).
    """
    group_list = list(groups)
    status_label = ", ".join(str(s) for s in statuses)
    lines = [
        "# crosswalk 검수 보조 — 근거 조인(read-only·판정 없음)",
        f"대상 상태: {status_label} · kebab {len(group_list)}종 · "
        f"후보 {sum(len(g.candidates) for g in group_list)}건",
        "검수자는 kebab 오개념과 후보 M-id 근거를 대조해 approve/reject를 판단하고, 검수 큐 JSON에",
        "status/reviewer/reviewed_on을 손기입한 뒤 promote --load로 적재한다",
        "(이 도구는 status를 안 바꾼다·판정은 사람 몫).",
        "",
    ]
    for group in group_list:
        lines.extend(_format_kebab_header(group))
        for cand in group.candidates:
            lines.extend(_format_candidate(cand))
        lines.append("")
    lines.append(summarize_review_aid(group_list, statuses=statuses).model_dump_json())
    return "\n".join(lines)


def _run(queue_path: Path, corpus_path: Path, statuses: tuple[ReviewStatus, ...]) -> int:
    """큐·코퍼스 읽어 리포트 출력. 파일 부재는 exit 2(조용한 무동작 금지·promote 규약 미러)."""
    for path, label in ((queue_path, "검수 큐"), (corpus_path, "코퍼스")):
        if not path.exists():
            print(f"{label} 없음: {path}")
            return 2
    queue: dict[str, Any] = json.loads(queue_path.read_text(encoding="utf-8"))
    try:
        items = parse_review_queue(queue)
    except CrosslinkReviewError as exc:
        print(f"검수 큐 파싱 거부 — {exc}")
        return 1
    corpus = load_corpus(corpus_path.read_text(encoding="utf-8"))
    groups = build_review_aid(items, corpus=corpus, statuses=statuses)
    print(format_review_aid(groups, statuses=statuses))
    return 0


def main(argv: list[str] | None = None) -> int:
    """CLI 엔트리 — 검수 큐 + 코퍼스 → kebab별 근거 리포트(stdout·read-only).

    반환은 종료 코드: 0=성공 · 1=검수 큐 파싱 위반 · 2=입력 파일 부재. status를 바꾸지 않고 큐를
    쓰지 않는다(근거 집합만 — 판정·적재는 promote 단계).
    """
    parser = argparse.ArgumentParser(
        prog="python -m whymath_backend.l4.misconception.crosslink_review_aid",
        description=(
            "오개념 crosswalk 검수 큐에 kebab 정의·M-id 코퍼스 근거를 조인해 kebab별로 모은 "
            "read-only 검수 보조 리포트 — 판정·적재는 crosslink_review promote 단계(사람 서명)."
        ),
    )
    parser.add_argument(
        "--queue",
        type=Path,
        default=Path(DEFAULT_QUEUE_PATH),
        help=f"검수 큐 JSON 경로(기본 {DEFAULT_QUEUE_PATH})",
    )
    parser.add_argument(
        "--corpus",
        type=Path,
        default=Path(DEFAULT_CORPUS_PATH),
        help=f"M-id 코퍼스 JSON 경로(기본 {DEFAULT_CORPUS_PATH})",
    )
    parser.add_argument(
        "--status",
        choices=["pending", "approved", "rejected", "deferred", "all"],
        default="pending",
        help="리포트 대상 검수 상태(기본 pending — 검수 대기분). all은 전 상태.",
    )
    args = parser.parse_args(argv)
    status_arg: str = args.status
    statuses: tuple[ReviewStatus, ...] = (
        ("pending", "approved", "rejected", "deferred")
        if status_arg == "all"
        else (status_arg,)  # type: ignore[assignment]
    )
    return _run(args.queue, args.corpus, statuses)


if __name__ == "__main__":  # pragma: no cover — 엔트리포인트, _run/main이 테스트 대상
    sys.exit(main())


__all__ = [
    "CandidateEvidence",
    "DEFAULT_STATUSES",
    "KebabReviewGroup",
    "MisconceptionCorpusEntry",
    "ReviewAidSummary",
    "build_review_aid",
    "format_review_aid",
    "load_corpus",
    "main",
    "summarize_review_aid",
]
