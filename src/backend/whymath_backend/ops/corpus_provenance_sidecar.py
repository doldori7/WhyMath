"""코퍼스 사이드카(`_provenance.json`) **생성·갱신** 저작 CLI — PB-11.

왜 이 모듈이 있는가 (실측 부재)
------------------------------
`schema/corpus_provenance.py`가 사이드카 최소 계약(`pool` + 서지 정보 ≥1건)을 정의하고
`ops/provenance_audit.py`가 그것을 CI에서 집행하는데, **그 계약을 만족하는 파일을 만들어 주는
도구가 저장소에 0개**였다(PB-11 acceptance ① 실측: `pool` 키를 쓰는 non-test 코드는 계약 정의
2곳 + 검증기 1곳뿐 — *생성 경로 0건*). 실 사이드카 26개의 `pool`은 ARCH-20이 **손으로** 백필한
것이고, 신규 코퍼스를 만드는 사람에게 남은 경로는 "JSON을 손으로 쓴다"뿐이었다. 즉 "계약과
게이트는 있는데 생산 수단이 없다" 상태였고, PB-06이 실측한 회수 차단 조건 1(신규 30종 사이드카
부재)의 해소 비용이 "30개 손 작성"인 이유가 바로 이 부재다. 이 CLI가 그 생산 수단이다.

data-pipeline `_write_provenance()`를 쓰면 안 되는 이유 (PB-11 acceptance ② 실측)
-------------------------------------------------------------------------------
`data_pipeline/{skill,strategy,formula,problem_type,atom}_graph`·`concept_atom_crosswalk`·
`standards_university`의 `_write_provenance()` 8종은 이 자리를 대신할 수 없다. 임시 트리에서
실측한 두 결함(리포 코퍼스 무수정):

  (a) 만들어 내는 payload에 `pool`이 **없다** → `provenance_audit`이 즉시 `SCHEMA_INVALID`
      (실측 키: `source_file`·`source_sha256`·`source_citation`·`counts`·`validation`·
      `skipped`·`determinism` — `pool` 부재).
  (b) `path.write_text(json.dumps(payload …))`로 **통째 덮어쓰기**다 → 손으로 넣은 `pool`이
      재실행 한 번에 소실된다(실측: 백필 직후 audit exit 0 → 재실행 후 `pool: None`·exit 1).

그래서 이 CLI의 핵심 계약은 **멱등 · 비파괴**다. 원본 xlsx 파이프라인 8종에 `pool`을 소급
추가하는 일은 별건이다(PB-11 acceptance ⑤ (b) — 그 CLI들은 원본 변환 전용이라 저작 문제은행에
적용되지 않는다).

병합 규칙 (기본값이 병합·덮어쓰기는 명시 플래그)
----------------------------------------------
`atom_graph/university_standard_fill.py::_append_provenance` 선례(기존 JSON을 읽어 필요한 키만
갱신하고 나머지는 그대로 되쓰기)를 따른다. 구체적으로:

  · 기존 파일이 있으면 **키 순서까지 보존**한 채 인자로 지정한 키만 덮어쓴다. 지정하지 않은
    키(`counts`·`validation`·`signatures` 등 코퍼스별 자유 서술)는 손대지 않는다 —
    `CorpusProvenanceSidecar`의 `extra="allow"` 정책(이질성은 결함이 아니다)과 같은 태도다.
  · `pool`은 **인자로 주지 않으면 기존 값을 보존**한다. 인자로 준 값이 기존 값과 다르면
    거부한다(`--allow-pool-change` 없이는 변경 불가) — 저작권 등급 분리 태그를 실수로 바꾸는
    것은 조용히 넘길 사고가 아니다(`docs/legal/copyright_gradient.md` §4.2).
  · `--overwrite`는 기존 payload를 통째로 버린다. **기본값이 아니다** — 위 (b) 결함을 재현하는
    동작이므로 명시적으로 요구해야만 한다.

쓰기 전 검증 (계약 재구현 금지)
------------------------------
병합 결과는 쓰기 **전에** `CorpusProvenanceSidecar.model_validate`로 검증하고, 실패하면 아무것도
쓰지 않고 비0으로 끝낸다(계약을 이 모듈에서 다시 구현하지 않는다 — 단일 진실 원천은
`schema/corpus_provenance.py`). 검증에 통과한 **원본 병합 payload**를 쓴다(모델이 돌려준 값이
아니라) — `str_strip_whitespace`·필드 정규화가 다른 코퍼스의 자유 서술을 조용히 바꾸는 것을
막기 위한 round-trip 무손실 규칙이다.

종료 코드
--------
- 0 : 전 대상 성공(created/updated/unchanged).
- 1 : 계약 위반으로 **쓰지 않음**(예: `pool` 없이 새 사이드카 생성 시도, 서지 정보 0건).
- 2 : 입력 오류(코퍼스 디렉터리 부재, 기존 사이드카 JSON 파싱 실패, `pool` 무단 변경 시도,
      `--set` 형식 오류, 잘못된 `--pool` 값 — argparse 거부 포함).

사용
----
    # 신규 코퍼스에 최소 유효 사이드카 생성
    python -m whymath_backend.ops.corpus_provenance_sidecar data/corpus/foo_v1 \\
        --pool whymath-original --source-citation "와이매스 자체작성(원문 미포함)."

    # 기존 사이드카에 서지 1줄만 추가(pool·기타 자유 필드 전부 보존)
    python -m whymath_backend.ops.corpus_provenance_sidecar data/corpus/foo_v1 \\
        --license-notice "CC BY 4.0"

    # 여러 코퍼스 일괄(셸 글롭) · 자유 필드 동시 기입 · 미리보기
    python -m whymath_backend.ops.corpus_provenance_sidecar data/corpus/*_v1 \\
        --pool whymath-original --set corpus_name=foo_v1 --set record_count=120 --dry-run
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path

from pydantic import ValidationError

from whymath_backend.schema.corpus_provenance import CorpusProvenanceSidecar
from whymath_backend.schema.enums import ContentPool

__all__ = [
    "ACTION_CREATED",
    "ACTION_UNCHANGED",
    "ACTION_UPDATED",
    "ApplyResult",
    "SIDECAR_FILENAME",
    "SidecarContractError",
    "SidecarInputError",
    "SidecarUpdate",
    "apply_to_corpus",
    "main",
    "merge_payload",
    "parse_set_option",
    "render_payload",
]

SIDECAR_FILENAME = "_provenance.json"

_EXIT_OK = 0
_EXIT_CONTRACT_VIOLATION = 1
_EXIT_INPUT_ERROR = 2

ACTION_CREATED = "created"
ACTION_UPDATED = "updated"
ACTION_UNCHANGED = "unchanged"


class SidecarInputError(Exception):
    """입력 오류(exit 2) — 디렉터리 부재·기존 파일 파싱 실패·pool 무단 변경·`--set` 형식 오류."""


class SidecarContractError(Exception):
    """계약 위반(exit 1) — 병합 결과가 `CorpusProvenanceSidecar`를 만족하지 못해 쓰지 않았다."""


@dataclass(frozen=True, slots=True)
class SidecarUpdate:
    """이번 실행이 *지정한* 키들. `None`은 "지정 안 함"이고 "빈 값으로 덮어씀"이 아니다.

    이 구분이 비파괴 계약의 뿌리다 — 지정하지 않은 키는 기존 값을 그대로 둔다(특히 `pool`).
    """

    pool: ContentPool | None = None
    source_citation: str | None = None
    license_notice: str | None = None
    extra: Mapping[str, object] = field(default_factory=dict)

    def specified_keys(self) -> tuple[str, ...]:
        """실제로 갱신할 키 목록(보고용 — 사람이 "무엇이 바뀌는지"를 눈으로 확인하게)."""
        keys: list[str] = []
        if self.pool is not None:
            keys.append("pool")
        if self.source_citation is not None:
            keys.append("source_citation")
        if self.license_notice is not None:
            keys.append("license_notice")
        keys.extend(sorted(self.extra))
        return tuple(keys)


@dataclass(frozen=True, slots=True)
class ApplyResult:
    """한 코퍼스에 대한 처리 결과."""

    corpus: str
    path: Path
    action: str  # ACTION_CREATED | ACTION_UPDATED | ACTION_UNCHANGED
    pool: str
    pool_preserved: bool  # 기존 파일의 pool을 인자 없이 그대로 살렸다
    payload: dict[str, object]


def parse_set_option(raw: str) -> tuple[str, object]:
    """`--set key=value` 한 항목을 `(key, 값)`으로 푼다.

    값은 먼저 JSON으로 해석하고(정수·불리언·리스트·객체를 그대로 넣을 수 있게), 실패하면 문자열
    그대로 쓴다 — `record_count=120`은 int로, `corpus_name=foo_v1`은 str로 들어간다. 계약 필드
    (`pool`·`source_citation`·`license_notice`)는 전용 옵션이 있으므로 `--set`으로는 막는다(같은
    필드를 두 경로로 쓸 수 있으면 어느 쪽이 이겼는지 사람이 추측하게 된다).
    """
    if "=" not in raw:
        raise SidecarInputError(f"--set 형식 오류(key=value 필요): {raw!r}")
    key, _, value = raw.partition("=")
    key = key.strip()
    if not key:
        raise SidecarInputError(f"--set 키가 비어 있다: {raw!r}")
    if key in {"pool", "source_citation", "license_notice"}:
        raise SidecarInputError(
            f"--set으로는 계약 필드를 쓸 수 없다(전용 옵션 사용): {key} → --{key.replace('_', '-')}"
        )
    try:
        parsed: object = json.loads(value)
    except json.JSONDecodeError:
        parsed = value  # JSON이 아니면 문자열 그대로(자유 서술 필드의 일반 케이스)
    return key, parsed


def _load_existing(path: Path) -> dict[str, object] | None:
    """기존 사이드카를 읽는다(없으면 `None`). 파싱 실패는 **삼키지 않는다**.

    CLAUDE.md "침묵 실패 금지" — 예외 타입명을 메시지에 포함해 무엇이 깨졌는지 남긴다.
    깨진 파일을 조용히 새 payload로 덮으면 그게 바로 (b) 결함의 재발이다.
    """
    if not path.is_file():
        return None
    text = path.read_text(encoding="utf-8")
    try:
        loaded: object = json.loads(text)
    except json.JSONDecodeError as exc:
        raise SidecarInputError(
            f"{path} 파싱 실패 [{type(exc).__name__}] — {exc}. 손상된 사이드카를 덮어쓰지 않았다"
            "(고치거나 --overwrite로 명시 요구할 것)."
        ) from exc
    if not isinstance(loaded, dict):
        raise SidecarInputError(
            f"{path} 최상위가 JSON 객체가 아니다(type={type(loaded).__name__})."
        )
    return loaded


def merge_payload(
    existing: Mapping[str, object] | None,
    update: SidecarUpdate,
    *,
    overwrite: bool = False,
    allow_pool_change: bool = False,
) -> tuple[dict[str, object], bool]:
    """`(병합 payload, pool을 인자 없이 보존했는가)`를 반환한다(파일 I/O 없음 — 순수 함수).

    기본은 병합이다: 기존 키 순서를 보존한 채 `update`가 지정한 키만 덮어쓰고, 나머지는 손대지
    않는다. `overwrite=True`면 기존 payload를 통째로 버린다(명시 요구 전용 — 모듈 docstring (b)).
    """
    base: dict[str, object] = {} if (overwrite or existing is None) else dict(existing)
    existing_pool = base.get("pool")

    pool_preserved = False
    if update.pool is not None:
        if (
            not overwrite
            and isinstance(existing_pool, str)
            and existing_pool != update.pool.value
            and not allow_pool_change
        ):
            raise SidecarInputError(
                f"기존 pool={existing_pool!r} 을(를) {update.pool.value!r} 로 바꾸려 한다 — "
                "콘텐츠 풀 분리 태그(copyright_gradient.md §4.2) 변경은 실수로 넘길 수 없다. "
                "의도한 변경이면 --allow-pool-change를 명시하라."
            )
        base["pool"] = update.pool.value
    elif isinstance(existing_pool, str):
        pool_preserved = True  # 인자 없이 기존 값을 그대로 살렸다(비파괴의 핵심 관측점)

    if update.source_citation is not None:
        base["source_citation"] = update.source_citation
    if update.license_notice is not None:
        base["license_notice"] = update.license_notice
    for key, value in update.extra.items():
        base[key] = value

    return base, pool_preserved


def _validate(payload: Mapping[str, object], corpus: str) -> None:
    """쓰기 전 계약 검증 — 실패하면 아무것도 쓰지 않는다(계약 재구현 0)."""
    try:
        CorpusProvenanceSidecar.model_validate(dict(payload))
    except ValidationError as exc:
        raise SidecarContractError(
            f"{corpus}: 병합 결과가 사이드카 계약을 위반해 쓰지 않았다 — {exc}"
        ) from exc


def render_payload(payload: Mapping[str, object]) -> str:
    """직렬화 정본 — `indent=2` + `ensure_ascii=False` + 개행 종료.

    기존 26개 실 사이드카 전부와 같은 형태다(전수 실측 2026-08-11: 모두 개행으로 끝난다).
    같은 입력이면 같은 바이트를 낸다 — 멱등 판정(`unchanged`)이 이 결정성에 의존한다.
    """
    return json.dumps(dict(payload), ensure_ascii=False, indent=2) + "\n"


def apply_to_corpus(
    corpus_dir: Path,
    update: SidecarUpdate,
    *,
    overwrite: bool = False,
    allow_pool_change: bool = False,
    dry_run: bool = False,
) -> ApplyResult:
    """코퍼스 디렉터리 1개의 사이드카를 생성 또는 갱신한다(멱등·비파괴).

    `dry_run=True`면 판정·검증까지 다 하고 파일만 쓰지 않는다(사람이 diff를 먼저 보게).
    """
    if not corpus_dir.is_dir():
        raise SidecarInputError(f"{corpus_dir} 이(가) 디렉터리가 아니다 — 경로를 확인하라.")

    path = corpus_dir / SIDECAR_FILENAME
    # `--overwrite`는 기존 payload를 어차피 버리므로 파싱하지 않는다 — 그래야 **손상된 JSON을
    # 고치는 유일한 CLI 경로**가 실제로 존재한다(`_load_existing`의 안내 문구가 빈말이 되지 않게).
    existing = None if overwrite else _load_existing(path)
    existed_before = path.is_file()
    merged, pool_preserved = merge_payload(
        existing, update, overwrite=overwrite, allow_pool_change=allow_pool_change
    )
    if "pool" not in merged:
        raise SidecarContractError(
            f"{corpus_dir.name}: pool이 없다 — 새 사이드카를 만들 때는 --pool이 필수다"
            f"(허용값: {', '.join(p.value for p in ContentPool)})."
        )
    _validate(merged, corpus_dir.name)

    rendered = render_payload(merged)
    if not existed_before:
        action = ACTION_CREATED
    elif rendered == path.read_text(encoding="utf-8"):
        action = ACTION_UNCHANGED  # 멱등 — 두 번째 실행은 바이트가 같다
    else:
        action = ACTION_UPDATED

    if not dry_run and action != ACTION_UNCHANGED:
        path.write_text(rendered, encoding="utf-8")

    pool_value = merged["pool"]
    return ApplyResult(
        corpus=corpus_dir.name,
        path=path,
        action=action,
        pool=str(pool_value),
        pool_preserved=pool_preserved,
        payload=merged,
    )


def _render_result(result: ApplyResult, *, dry_run: bool) -> str:
    suffix = " (dry-run — 쓰지 않음)" if dry_run else ""
    note = " · 기존 pool 보존" if result.pool_preserved else ""
    return f"[{result.action}] {result.corpus} pool={result.pool}{note} → {result.path}{suffix}"


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m whymath_backend.ops.corpus_provenance_sidecar",
        description=(
            "코퍼스 사이드카(_provenance.json) 생성·갱신 — 멱등·비파괴(기본 병합, "
            "덮어쓰기는 --overwrite 명시)."
        ),
    )
    parser.add_argument(
        "corpus_dirs",
        nargs="+",
        help="대상 코퍼스 디렉터리(여럿 가능 — 셸 글롭 사용).",
    )
    parser.add_argument(
        "--pool",
        choices=[p.value for p in ContentPool],
        default=None,
        help=(
            "콘텐츠 풀 분리 태그(폐쇄 3종). 생략하면 기존 사이드카의 값을 보존한다"
            "(새 사이드카 생성 시에는 필수)."
        ),
    )
    parser.add_argument("--source-citation", default=None, help="출처 서술(자유형).")
    parser.add_argument("--license-notice", default=None, help="라이선스 고지(자유형).")
    parser.add_argument(
        "--set",
        dest="set_items",
        action="append",
        default=[],
        metavar="KEY=VALUE",
        help="자유 필드 추가·갱신(값은 JSON 우선 해석, 실패 시 문자열). 반복 지정 가능.",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="기존 payload를 통째로 버리고 지정 키만 남긴다(기본값 아님 — 파괴적).",
    )
    parser.add_argument(
        "--allow-pool-change",
        action="store_true",
        help="기존 pool 값을 다른 값으로 바꾸는 것을 허용한다(기본은 거부).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="판정·검증만 하고 파일을 쓰지 않는다(결과 payload를 출력).",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)

    try:
        extra: dict[str, object] = dict(parse_set_option(item) for item in args.set_items)
    except SidecarInputError as exc:
        print(f"입력 오류: {exc}", file=sys.stderr)
        return _EXIT_INPUT_ERROR

    update = SidecarUpdate(
        pool=ContentPool(args.pool) if args.pool else None,
        source_citation=args.source_citation,
        license_notice=args.license_notice,
        extra=extra,
    )

    results: list[ApplyResult] = []
    for raw_dir in args.corpus_dirs:
        try:
            result = apply_to_corpus(
                Path(raw_dir),
                update,
                overwrite=args.overwrite,
                allow_pool_change=args.allow_pool_change,
                dry_run=args.dry_run,
            )
        except SidecarInputError as exc:
            print(f"입력 오류: {exc}", file=sys.stderr)
            return _EXIT_INPUT_ERROR
        except SidecarContractError as exc:
            print(f"계약 위반: {exc}", file=sys.stderr)
            return _EXIT_CONTRACT_VIOLATION
        results.append(result)
        print(_render_result(result, dry_run=args.dry_run))

    if update.specified_keys():
        print(f"지정 키: {', '.join(update.specified_keys())}")
    if args.dry_run:
        for result in results:
            print(f"--- {result.corpus} 최종 payload(미기록) ---")
            print(render_payload(result.payload), end="")

    return _EXIT_OK


if __name__ == "__main__":  # pragma: no cover — CLI 진입점
    sys.exit(main())
