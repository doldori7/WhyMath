"""LLM 동등문제 코퍼스 *축적* 배치 CLI — 회차 간 dedup·증분 append(라이브 ops).

새 Phaiakes9 라이브 스모크(2026-07-07 실측·MEMORY)에서 확인된 갭을 상환한다: 스모크 스크립트는
실행마다 ① dedup index를 새로 만들고(회차 *간* 판박이 미차단) ② 산출 JSONL을 전면 교체했다
(축적 불가). 이 CLI는 **기존 코퍼스들의 canonical signature를 로드해 `run_batch`에 주입**하고,
수용분을 산출 파일에 **증분 append**한다 — 회차를 거듭할수록 코퍼스가 중복 없이 자란다.

동작:
  1. `--seed`(복수 가능) + `--out`(존재 시)의 전 레코드에서 signature·slug 집합을 로드.
  2. 생성기(run 함수는 좌석 무관 — LLM·스켈레톤 동일 계약)를 `run_batch`에 태움. 공유
     signature_index 덕에 기존 코퍼스와 구조가 같은 후보는 `rejected_duplicate`로 차단.
  3. 수용분 중 slug가 기존과 겹치는 건 스킵·리포트(멱등 upsert 키 충돌 방어 — 정상 경로에선
     signature dedup이 먼저 잡으므로 드묾), 나머지를 `--out`에 append.

main()은 라이브 전용(LLM 필요): `LLMEquivalentProblemGenerator`(provider=None→표준
CompositeProvider·Ollama)를 조립한다 — 이 환경(CI·LLM 0)에서 호출하면 provider 예외를
생성기가 안전 폴백(None)해 전건 `generation_failed`·exit 1로 정직 실패한다. hermetic 테스트는
`run_corpus_accumulate`에 결정론 스켈레톤 생성기를 주입해 축적·dedup 로직만 검증한다.

조성 루트 소관(주입 원칙): L4 정본(`CATALOG_BY_ID`)을 읽어 생성기에 오개념 라벨을 주입한다 —
L3 코드에는 L4 import 0(계층 규칙). harness는 import-linter 계약 밖(`problem_corpus_batch` 선례).

산출물은 v0(사람 검수 전) — 게이트 통과 ≠ 학생 노출(§03 정본). exit 코드: 신규 수용 ≥1이면 0,
아니면 1(코퍼스 무진전 신호 — 사유는 리포트의 outcome 집계로 관측·조용한 실패 금지).

생성 로그(EOS-55 집행 별항): 이 경로는 **기본으로** LLM 호출별 `GenerationLog`(모델·재현
좌석·입력 스냅샷 해시+참조)를 `<out>.genlog.jsonl`에 즉시 flush로 적재한다 —
`--generation-log`로 경로만 바꿀 수 있다(끄는 옵션 없음 — 적재가 기본이어야 "경로가
적재한다"가 참·정본화≠집행). `ops/hit_cu_metrics --generation-log`가 이 JSONL을 소비한다.

검수 큐(EOS-58 앵커 관통 + codex 리뷰 상환 — 2층 구조·genlog 동형): 비수용 outcome
(needs_review·rejected_*·generation_failed)은 종전엔 사유 문자열 샘플만 남고 휘발했다 — 사람
검수 큐(§03 "needs_review는 사람 검수로")의 입력이 라이브 LLM 경로에서 끊겨 있던 공백이다.
  1. **내구 큐** `<out>.review.jsonl` — 비수용 outcome 1건당 1행을 **발생 즉시 append+flush**
     한다(P2 — 장기 라이브 배치가 도중에 죽어도 그때까지의 기록이 남는다·genlog와 같은 규약).
     행에는 **후보 payload 전문**(코퍼스 레코드와 동일 직렬화 — 검수 승격 가능 형태)이 실려
     검수자가 문항·정답·해설을 행만으로 본다(P1-1 — 종전 워크리스트는 slug·점수·사유뿐이라
     실검수 불가였다). 후보가 없는 실패(generation_failed)는 사유만 정직 기록(본문 날조 금지).
  2. **워크리스트 뷰** `<out>.worklist.md` — 회차 메모리가 아니라 **내구 큐 전체**를 렌더한다
     (P1-2 — 같은 --out 반복 실행에서 이전 미해결 needs_review가 덮어쓰기로 소실되지 않고,
     전건 수용 회차도 기존 큐를 비우지 않는다). 같은 후보 재출현은 payload sha로 묶어 출현
     횟수를 표기한다. `--worklist-out`으로 뷰 경로만 바꿀 수 있다(끄기 없음 — 기본 기록이라야
     검수 큐 공급이 참·비수용 0건이어도 "관측했고 0건"을 기록). 무진전(exit 1) 회차에도
     기록한다(실패 증거 보존·2026-08-22 규칙).
범위 밖 별항(정본화≠집행): 해결(체크 완료) 추적·review_status 각인·승격 집행은 OPS-24 백필·
승격 후속 태스크 소관 — 이 CLI의 계약은 "큐가 소실되지 않고 본문이 실린다"까지다.

사용법(Phaiakes9·라이브):
    python -m whymath_backend.harness.problem_corpus_accumulate \\
        --seed <기존.jsonl> [--seed <추가.jsonl> ...] --out <축적.jsonl> --n 20 \\
        [--topic-hint "..."] [--standard-code "[10공수1-02-02]"] [--difficulty 2.5] \\
        [--generation-log <경로.jsonl>] [--worklist-out <경로.md>]
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import uuid
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from whymath_backend.harness.needs_review_worklist import (
    ReviewQueueEntry,
    append_review_queue_jsonl,
    entry_from_outcome,
    load_review_queue_jsonl,
    render_review_queue_markdown,
)
from whymath_backend.harness.problem_corpus_batch import JsonlCorpusSink, _record_to_json
from whymath_backend.l1.problem_bank.populate import load_problem_bank_records
from whymath_backend.l3.equivalent.acceptance import EquivalenceSpec
from whymath_backend.l3.equivalent.canonicalize import canonical_signature
from whymath_backend.l3.equivalent.generator import EquivalentProblemGenerator
from whymath_backend.l3.equivalent.orchestrator import (
    GenerationOutcome,
    run_equivalent_generation,
)
from whymath_backend.l3.equivalent.orchestrator import (
    _to_record as _candidate_to_record,
)
from whymath_backend.l3.pregenerate.provenance_bridge import append_generation_log_jsonl
from whymath_backend.schema.provenance import GenerationLog

__all__ = [
    "AccumulateReport",
    "default_generation_log_path",
    "default_review_queue_path",
    "default_worklist_path",
    "load_corpus_index",
    "main",
    "run_corpus_accumulate",
]

_LOGGER = logging.getLogger(__name__)

# 기본 topic 힌트 — 라이브 스모크(2026-07-07) 검증 문구. --topic-hint로 교체 가능.
_DEFAULT_TOPIC_HINT = "이차방정식 — 두 근 중 큰 근을 구하는 형태(답 하나)"
_DEFAULT_STANDARD_CODE = "[10공수1-02-02]"
_DEFAULT_DIFFICULTY = 2.5


@dataclass(frozen=True, slots=True)
class AccumulateReport:
    """축적 배치 리포트 — 시도/수용/중복/검수/실패 + 파일 상태(조용한 실패 금지).

    `review_outcomes`(EOS-58)는 이 회차 비수용 GenerationOutcome 원본(후보+게이트 판정+사유)
    — 프로그램 소비용(batch `CorpusBatchReport.review_outcomes` 미러). 내구 영속은 리포트가
    아니라 `review_sink`(발생 즉시 append)가 소유한다 — 리포트는 회차 요약일 뿐이다.
    `run_id`는 이 회차 식별자 — 검수 큐 행(`ReviewQueueEntry.run_id`)과 조인하는 키.
    `to_json`엔 outcome 카운트만 싣는다(객체는 직렬화하지 않음).
    """

    attempted: int
    accepted: int
    appended: int
    slug_conflicts: int
    outcome_counts: dict[str, int]
    seed_records: int
    existing_out_records: int
    out_path: str
    run_id: str
    reason_sample: list[str] = field(default_factory=list)
    review_outcomes: list[GenerationOutcome] = field(default_factory=list)

    def to_json(self) -> dict[str, Any]:
        return {
            "attempted": self.attempted,
            "accepted": self.accepted,
            "appended": self.appended,
            "slug_conflicts": self.slug_conflicts,
            "outcome_counts": self.outcome_counts,
            "seed_records": self.seed_records,
            "existing_out_records": self.existing_out_records,
            "out_path": self.out_path,
            "run_id": self.run_id,
            "reason_sample": self.reason_sample,
            "review_outcomes_count": len(self.review_outcomes),
        }


def load_corpus_index(paths: Sequence[Path]) -> tuple[set[str], set[str], int]:
    """기존 코퍼스들에서 (signature 집합, slug 집합, 총 레코드 수)를 로드.

    signature는 verify 메타(conditions·answer_selection)의 canonical 정규형 — 생성 배치의
    dedup 축과 동일 키라 주입 즉시 회차 간 중복이 차단된다. 정규화 불가(비다항)면 None이라
    집합에 안 실린다(그 문제군은 slug·임베딩 dedup에 위임 — 오케스트레이터 규약 동일).
    부재 경로는 건너뛴다(첫 축적 회차의 빈 out 허용).
    """
    signatures: set[str] = set()
    slugs: set[str] = set()
    total = 0
    for path in paths:
        if not path.exists():
            continue
        for record in load_problem_bank_records(path):
            total += 1
            slugs.add(record.slug)
            signature = canonical_signature(
                record.verify.conditions, record.verify.answer_selection
            )
            if signature is not None:
                signatures.add(signature)
    return signatures, slugs, total


def _append_records(path: Path, lines: list[str]) -> None:
    """JSONL append — 기존 내용 보존·신규 행만 덧붙임(전면 교체 아님·축적의 핵심)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        for line in lines:
            handle.write(line + "\n")


def _queue_entry(outcome: GenerationOutcome, run_id: str) -> ReviewQueueEntry:
    """비수용 outcome → 내구 큐 행 조립(조성 루트) — payload = 코퍼스 레코드 동일 직렬화.

    후보가 있으면 저장 경로와 같은 변환(`_to_record`→`_record_to_json`)으로 전문을 싣는다 —
    검수 수용 시 그대로 코퍼스 행이 될 수 있는 승격 가능 형태(이중 직렬화 구현 금지). 후보
    없는 outcome(생성 실패)은 payload=None — `reasons`가 실패 사유를 말한다(본문 날조 금지).
    """
    payload: dict[str, Any] | None = None
    if outcome.candidate is not None:
        payload = _record_to_json(_candidate_to_record(outcome.candidate))
    return entry_from_outcome(outcome, run_id=run_id, candidate_payload=payload)


def run_corpus_accumulate(
    *,
    out_path: Path,
    seed_paths: Sequence[Path],
    generator: EquivalentProblemGenerator,
    spec: EquivalenceSpec,
    n: int,
    write: bool = True,
    review_sink: Callable[[ReviewQueueEntry], None] | None = None,
    run_id: str | None = None,
) -> AccumulateReport:
    """축적 1회차 — 기존 signature 주입 dedup + 수용분 증분 append(생성기 좌석 무관).

    `generator`는 좌석 계약만 요구한다(LLM·스켈레톤 동일) — 라이브 배선은 main() 소관이고,
    hermetic 테스트는 결정론 생성기를 주입해 축적 로직을 LLM 0으로 검증한다.

    `review_sink`(EOS-58 codex P2 상환 — EOS-55 `generation_log_sink` 심 동형): 비수용 outcome
    1건마다 내구 큐 행(`ReviewQueueEntry`·후보 payload 전문 동반)을 **발생 즉시** 흘린다 —
    회차 루프 안에서 호출되므로 배치가 도중에 죽어도 그때까지의 검수 큐는 싱크가 영속한 만큼
    남는다(종료 일괄 기록 금지). 싱크 예외는 배치를 깨지 않되 **타입명**을 로그에 남긴다
    (never-break·침묵 실패 금지). None(기본)이면 종전 동작 그대로(기존 호출부 무영향).
    `run_id`는 회차 식별자(미지정 시 uuid4 hex) — 리포트·큐 행 양쪽에 실려 조인 축이 된다.
    """
    seed_signatures, seed_slugs, seed_total = load_corpus_index(list(seed_paths))
    out_signatures, out_slugs, out_total = load_corpus_index([out_path])

    # 공유 index — 기존(시드+축적분) 구조가 전부 실려 회차 간 판박이가 생성 단계에서 차단된다.
    signature_index: set[str] = seed_signatures | out_signatures
    known_slugs: set[str] = seed_slugs | out_slugs

    resolved_run_id = run_id if run_id is not None else uuid.uuid4().hex
    sink = JsonlCorpusSink()
    # 종전 orchestrator.run_batch(n회 일괄) 대신 단건 조합을 회차 루프로 돈다 — 계약 동일
    # (같은 signature_index·store 공유)하되, 비수용 outcome을 **발생 즉시** 싱크로 흘릴 수
    # 있는 지점이 생긴다(P2 — outcome 리스트 완성 후 일괄 처리로는 중단 시 전부 잃는다).
    outcomes: list[GenerationOutcome] = []
    for _ in range(n):
        outcome = run_equivalent_generation(
            spec, generator, signature_index=signature_index, store=sink
        )
        outcomes.append(outcome)
        if review_sink is not None and outcome.status not in ("accepted_stored", "accepted"):
            try:
                review_sink(_queue_entry(outcome, resolved_run_id))
            except Exception as exc:  # noqa: BLE001 — 큐 적재 장애는 배치 비차단(타입명 로그)
                _LOGGER.warning("검수 큐 행 적재 실패(%s) — 배치 계속", type(exc).__name__)

    counts: dict[str, int] = {}
    reasons: list[str] = []
    # 비수용 outcome 원본 보존(EOS-58) — 이 회차 요약(리포트)용. 내구 영속은 위 review_sink가
    # 이미 발생 즉시 수행했다(batch의 review_outcomes 포착 필터와 동일 기준).
    review_outcomes: list[GenerationOutcome] = []
    for outcome in outcomes:
        counts[outcome.status] = counts.get(outcome.status, 0) + 1
        if outcome.status not in ("accepted_stored", "accepted"):
            review_outcomes.append(outcome)
        if outcome.status != "accepted_stored" and outcome.reasons and len(reasons) < 10:
            reasons.append(outcome.reasons[0][:80])

    fresh_lines: list[str] = []
    slug_conflicts = 0
    for record in sink.records:
        if record.slug in known_slugs:
            slug_conflicts += 1  # 멱등 키 충돌 — append하면 중복 행이라 스킵(정직 집계).
            continue
        known_slugs.add(record.slug)
        fresh_lines.append(json.dumps(_record_to_json(record), ensure_ascii=False))

    if write and fresh_lines:
        _append_records(out_path, fresh_lines)

    return AccumulateReport(
        attempted=n,
        accepted=counts.get("accepted_stored", 0),
        appended=len(fresh_lines) if write else 0,
        slug_conflicts=slug_conflicts,
        outcome_counts=counts,
        seed_records=seed_total,
        existing_out_records=out_total,
        out_path=str(out_path),
        run_id=resolved_run_id,
        reason_sample=reasons,
        review_outcomes=review_outcomes,
    )


def default_generation_log_path(out_path: Path) -> Path:
    """생성 로그 기본 경로 — 축적 산출물 곁 사이드카 `<out>.genlog.jsonl`(항상 적재)."""
    return out_path.with_suffix(".genlog.jsonl")


def default_review_queue_path(out_path: Path) -> Path:
    """내구 검수 큐 기본 경로 — 축적 산출물 곁 사이드카 `<out>.review.jsonl`(append-only).

    genlog와 같은 규약(EOS-58 codex 상환) — 비수용 outcome이 발생 즉시 여기 영속돼야 라이브
    회차의 needs_review 후보가 소실되지 않는다. 워크리스트 md는 이 파일의 렌더 뷰다(정본은
    JSONL 행 — 뷰 경로는 `--worklist-out`으로 바꿔도 큐 저장소는 항상 이 사이드카다).
    """
    return out_path.with_suffix(".review.jsonl")


def default_worklist_path(out_path: Path) -> Path:
    """검수 워크리스트 기본 경로 — 축적 산출물 곁 사이드카 `<out>.worklist.md`(항상 기록).

    genlog 사이드카와 같은 규약(EOS-58) — 기본 기록이라야 라이브 회차의 needs_review 후보가
    사람 검수 큐로 반드시 흐른다(플래그를 잊으면 큐가 조용히 유실되는 설계 금지).
    """
    return out_path.with_suffix(".worklist.md")


def _build_live_generator(
    topic_hint: str,
    *,
    generation_log_sink: Callable[[GenerationLog], None] | None = None,
) -> EquivalentProblemGenerator:
    """라이브 LLM 생성기 조립(조성 루트) — L4 카탈로그 라벨 주입·표준 CompositeProvider.

    이 함수만 LLM 경로를 안다 — 여기 격리해 run_corpus_accumulate는 좌석 무관을 유지한다.
    `generation_log_sink`(EOS-55): 호출별 GenerationLog(재현 좌석·입력 스냅샷)를 흘릴 싱크
    — main()이 JSONL appender를 배선한다(적재가 기본·정본화≠집행).
    """
    from whymath_backend.l3.equivalent.llm_generator import LLMEquivalentProblemGenerator
    from whymath_backend.l4.misconception.catalog import CATALOG_BY_ID
    from whymath_backend.schema.enums import Subject

    return LLMEquivalentProblemGenerator(
        None,  # 표준 CompositeProvider(Ollama+Anthropic) 지연 구성 — 라이브 환경 전제
        misconception_catalog={mid: m.name_kr for mid, m in CATALOG_BY_ID.items()},
        topic_hint=topic_hint,
        subject=Subject.공통,
        slug_prefix="wm-gen-quad",
        generation_log_sink=generation_log_sink,
    )


def main(argv: list[str] | None = None) -> int:
    """CLI 엔트리(라이브 전용) — 리포트 JSON을 stdout에 내고, 신규 수용 0이면 exit 1."""
    parser = argparse.ArgumentParser(
        prog="python -m whymath_backend.harness.problem_corpus_accumulate",
        description=(
            "LLM 동등문제 코퍼스 축적 배치 — 기존 코퍼스 signature를 주입해 회차 간 중복을 "
            "차단하고 수용분을 증분 append한다(라이브 LLM 필요)."
        ),
    )
    parser.add_argument(
        "--seed", dest="seeds", type=Path, action="append", default=[], help="기존 코퍼스 JSONL."
    )
    parser.add_argument("--out", type=Path, required=True, help="축적 산출 JSONL(append).")
    parser.add_argument("--n", type=int, default=20, help="생성 시도 횟수.")
    parser.add_argument("--topic-hint", default=_DEFAULT_TOPIC_HINT, help="저작 주제 힌트.")
    parser.add_argument(
        "--standard-code", default=_DEFAULT_STANDARD_CODE, help="스펙 성취기준 코드."
    )
    parser.add_argument(
        "--difficulty", type=float, default=_DEFAULT_DIFFICULTY, help="스펙 난이도(1~5)."
    )
    parser.add_argument(
        "--generation-log",
        type=Path,
        default=None,
        help=(
            "GenerationLog JSONL 경로(EOS-55). 미지정 시 <out>.genlog.jsonl 사이드카에 "
            "항상 적재한다(끄기 없음 — 적재가 기본·정본화≠집행)."
        ),
    )
    parser.add_argument(
        "--worklist-out",
        type=Path,
        default=None,
        help=(
            "검수 워크리스트(내구 큐 <out>.review.jsonl 전체의 누적 렌더 뷰) 마크다운 경로"
            "(EOS-58). 미지정 시 <out>.worklist.md 사이드카에 항상 기록한다(끄기 없음 — 사람 "
            "검수 큐 공급이 기본·뷰 경로를 바꿔도 큐 저장소는 <out>.review.jsonl 고정)."
        ),
    )
    args = parser.parse_args(argv)

    spec = EquivalenceSpec(
        achievement_standard_codes=frozenset({args.standard_code}),
        target_misconception_ids=frozenset(),
        difficulty_overall=args.difficulty,
        answer_format=None,
    )
    # 생성 Run 재현 로그(EOS-55) — 호출별 즉시 flush 사이드카(2026-08-22 규칙 ①: 배치가
    # 도중에 죽어도 그때까지의 호출 이력·비용은 파일에 남는다).
    genlog_path: Path = (
        args.generation_log
        if args.generation_log is not None
        else default_generation_log_path(args.out)
    )

    def _genlog_sink(log: GenerationLog) -> None:
        append_generation_log_jsonl(genlog_path, log)

    # 내구 검수 큐(EOS-58 codex P1-1/P2) — 비수용 outcome 발생 즉시 행 append+flush. 경로는
    # 항상 <out>.review.jsonl 사이드카(뷰와 달리 저장소는 옮기지 않는다 — 누적의 단일 원천).
    review_queue_path: Path = default_review_queue_path(args.out)

    def _review_sink(entry: ReviewQueueEntry) -> None:
        append_review_queue_jsonl(review_queue_path, entry)

    generator = _build_live_generator(args.topic_hint, generation_log_sink=_genlog_sink)
    report = run_corpus_accumulate(
        out_path=args.out,
        seed_paths=list(args.seeds),
        generator=generator,
        spec=spec,
        n=args.n,
        review_sink=_review_sink,
    )
    # 배치 종료 — 관측 전송 확정(2026-07-21 정합성 검토: 생성기 trace 배선). LangfuseSink는
    # 배치 버퍼 전송이라 짧은 CLI는 flush 없이 종료하면 이벤트가 유실된다(cost_probe 동형).
    # 좌석 계약(EquivalentProblemGenerator)엔 flush가 없으므로 duck-typing으로 있는 경우만.
    flush_trace = getattr(generator, "flush_trace", None)
    if callable(flush_trace):
        flush_trace()
    # 검수 워크리스트(EOS-58 codex P1-2) — 이 회차 메모리가 아니라 **내구 큐 전체**의 렌더
    # 뷰다: 회차 간 누적이 기본이라 이전 미해결 needs_review가 덮어쓰기로 소실되지 않고, 전건
    # 수용 회차도 기존 큐를 비우지 않는다. 무진전 회차(exit 1)에도 기록한다(실패 증거 보존·
    # 2026-08-22 규칙 ①) — 큐 파일 부재(비수용 기록 0)면 헤더가 "누적 행 0"을 말한다
    # (미기록과 구분·미측정≠0). 로드 실패 행은 뷰 헤더에 타입명+줄 번호로 노출된다.
    queue_entries: list[ReviewQueueEntry] = []
    queue_errors: list[str] = []
    if review_queue_path.exists():
        queue_entries, queue_errors = load_review_queue_jsonl(review_queue_path)
    worklist_path: Path = (
        args.worklist_out if args.worklist_out is not None else default_worklist_path(args.out)
    )
    worklist_md = render_review_queue_markdown(
        queue_entries,
        queue_display_path=str(review_queue_path),
        load_errors=queue_errors,
    )
    worklist_path.parent.mkdir(parents=True, exist_ok=True)
    worklist_path.write_text(worklist_md, encoding="utf-8")
    json.dump(report.to_json(), sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
    return 0 if report.appended > 0 else 1


if __name__ == "__main__":  # pragma: no cover — 모듈 실행 진입점
    raise SystemExit(main())
