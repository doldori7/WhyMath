"""실패정의 F-Ⅰ~F-Ⅴ 문서 동결 — G0 서명(2026-08-30 Kiki)의 기계 집행.

설계 정본: `docs/standards/eos_verification_design_v1.md` §5 (EOS-51).
서명 기록: `backlog/gates.yaml` `G-eos-g0-verification-design-freeze` clear evidence.

이 테스트가 막는 것
-------------------
실패정의는 12월 Go/No-Go 판정의 *사전* 계약이다 — 측정이 시작된 뒤 문구를 고치면
검증이 아니라 확증편향이 된다(전환 설계서 §2.4). 그런데 문서는 컴파일되지 않아서,
11월에 "12분"을 "20분"으로 바꿔도 어떤 도구도 소리내지 않는다. 그래서 서명 시점의
§5 전문을 해시로 동결하고, 판정 임계 토큰 6건을 개별 단언으로 이중 동결한다 —
"1차 집행은 규칙 산문이 아니라 코드다"(CLAUDE.md·PB-02 선례). 서명 기록(게이트
clear) 자체도 **evidence 전문 해시로** 동결한다: 게이트를 되돌려 '서명 전'으로
만드는 우회와, status는 cleared로 둔 채 evidence만 갈아끼우는 우회가 둘 다 같은
확증편향 경로다(후자는 "비어있지 않은가"만 보는 검사를 그대로 통과한다 — PR #910
리뷰 P2 지적·뮤테이션 재현).

트리거 배선(이 테스트가 *실제로 도는가*)
----------------------------------------
동결 대상 파일 자체가 CI backend 잡의 경로 필터 안에 있어야 한다 — 아니면 그 두
파일만 고치는 PR에서 잡이 SKIP되고 skip은 required check에서 충족으로 계상돼,
방어 대상인 "문서·서명의 조용한 수정"에서 정확히 실행되지 않는다(PR #910 리뷰 P1).
`FROZEN_INPUT_PATHS`가 그 단일 진실 원천이고, 항상 도는 infra-contracts 잡의
`test_ci_contract_fixture_trigger_wiring.py` 계약 ⑧이 이 상수를 AST로 읽어 강제한다.

동결의 소멸(명시)
-----------------
이 동결은 12/31 판정으로 임무가 끝난다. 판정 후 v2 개정 시 이 테스트도 *같은 PR에서*
함께 개정한다 — 해시를 바꾸는 diff가 곧 "동결 해제를 의식적으로 결정했다"는 증적이
된다(만료 없는 유예 금지 규칙의 역방향 적용: 동결에도 소멸 지점을 명기한다).

침묵 실패 방지 (이 테스트 자신에 대한 규율)
--------------------------------------------
§5 섹션 부재·게이트 부재·gates.yaml 파싱 실패를 "못 찾았으니 위반 없음"으로 통과시키지
않는다 — 전부 명시 실패다. 변별력은 `TestFreezeDiscrimination`이 뮤테이션으로 실측
동결한다(변별력 없는 검증 스텝 금지 — 2026-07-17 logconfig 선례).
"""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

import pytest
import yaml

from whymath_backend.schema.enums import GenerationFailureCode

# 레포 루트 — tests/backend/schema/<이 파일> 기준 3단계 위 (test_slo_contract.py 답습).
_REPO_ROOT = Path(__file__).resolve().parents[3]

# ── 동결 입력 경로의 단일 진실 원천 ──────────────────────────────────────────
# 이 테스트가 읽는 파일 전부. `tests/infra/test_ci_contract_fixture_trigger_wiring.py`가
# **이 상수를 AST로 파싱해** 전건이 CI backend 잡 필터 안에 있는지 동결한다(항상 도는
# infra-contracts 잡 소속). 즉 여기에 경로를 추가하면 트리거 배선 강제가 자동으로 따라온다 —
# 하드코딩 두 벌을 만들지 않는다(같은 파일 계약 ②의 "목록이 아니라 파생" 원칙).
# ⚠️ 리터럴 튜플 형태를 유지할 것 — AST 파서가 문자열 상수만 읽는다(f-string·연산 금지).
FROZEN_INPUT_PATHS: tuple[str, ...] = (
    "docs/standards/eos_verification_design_v1.md",
    "backlog/gates.yaml",
)

_DOC = _REPO_ROOT / FROZEN_INPUT_PATHS[0]
_GATES = _REPO_ROOT / FROZEN_INPUT_PATHS[1]
_GATE_ID = "G-eos-g0-verification-design-freeze"

# ── 서명 시점(2026-08-30) §5 전문의 정규화 해시 ──────────────────────────────
# 정규화 = CRLF→LF, 행별 우측 공백 제거, 전체 strip (플랫폼·에디터 노이즈만 흡수,
# 문안은 1글자도 흡수하지 않는다). 이 값을 바꾸는 diff = 동결 해제의 의식적 결정.
_SIGNED_SECTION5_SHA256 = "a9ad9f6ab7d4b065bf0c89d67e57e1d7cf827b6a4f4db4866a49c605d3553e3a"

# 서명 evidence 전문(gates.yaml 파싱값)의 해시 — 서명 *내용* 동결.
# 비어있지 않음만 보는 검사는 서명을 지키지 못한다: evidence를 "서명 철회"로 바꿔도
# `cleared`·비어있지 않음·(블록에 늘 있는 `requested: 2026-08-30`) 세 단언이 전부 통과한다
# (2026-08-30 실측 — PR #910 Codex 리뷰 P2 지적, 뮤테이션으로 재현 후 이 해시로 상환).
_SIGNED_EVIDENCE_SHA256 = "33e9f16c14da91d910378f3b53f5f61ae98b013fe89f5ddb489336a8073b051d"

# 판정 임계 토큰 — 해시와 독립인 의미 축 이중 동결(실패 메시지가 "무엇이 변했나"를 말하게).
_FROZEN_TOKENS = (
    "HIT 중앙값 > **12분/CU**",  # F-Ⅰ
    "수학적 오류율 > **2%**",  # F-Ⅱ
    "판단형(F3+F6+F7) 합 > **60%**",  # F-Ⅲ
    "앵커 **6개 중 3개 이상** 기준 미달",  # F-Ⅳ (6앵커 비례 환산 — 2026-08-30 확정)
    "(2개면 Conditional Go)",  # F-Ⅳ 완화 경로
    "표본 검수에서 ≥ **10%**",  # F-Ⅴ
)


def _read_doc() -> str:
    # 인코딩 명시 — 외부 파일 디코딩의 로케일 의존 금지(HARN-19 규칙).
    if not _DOC.exists():
        raise AssertionError(f"동결 대상 문서 부재: {_DOC} — 문서 삭제/이동도 동결 위반이다")
    return _DOC.read_text(encoding="utf-8").replace("\r\n", "\n")


def _section5(text: str) -> str:
    """§5 섹션 추출 — 부재 시 침묵 통과 대신 명시 실패."""
    m = re.search(r"^## §5\. .*?(?=^## |\Z)", text, re.MULTILINE | re.DOTALL)
    if m is None:
        raise AssertionError("§5 섹션(## §5. …)을 찾지 못함 — 제목 변경·삭제도 동결 위반이다")
    return m.group(0)


def _normalize(section: str) -> str:
    return "\n".join(line.rstrip() for line in section.splitlines()).strip()


def _signed_gate(text: str) -> dict[str, object]:
    """gates.yaml에서 G-eos-g0 게이트를 **YAML로 파싱해** 돌려준다.

    정규식 블록 절단이 아니라 파싱인 이유: 블록 문자열에는 게이트의 다른 필드(`requested:
    2026-08-30` 등)가 섞여 있어, 블록 대상 substring 검사는 evidence가 통째로 바뀌어도
    통과한다(P2 지적의 실제 원인). 판정은 evidence *값* 자체로 한다.
    """
    data = yaml.safe_load(text)
    gates = (data or {}).get("gates") if isinstance(data, dict) else None
    if not isinstance(gates, list):
        raise AssertionError("gates.yaml 파싱 실패 — gates 목록 부재(구조 변경도 동결 위반이다)")
    for gate in gates:
        if isinstance(gate, dict) and gate.get("id") == _GATE_ID:
            return gate
    raise AssertionError(f"gates.yaml에 {_GATE_ID} 부재 — 게이트 삭제도 서명 기록 위반이다")


class TestFailureDefinitionFrozen:
    """§5 실패정의 전문·임계 토큰 동결 — 서명본과 1바이트도 다르면 실패."""

    def test_section5_hash_matches_signed_version(self) -> None:
        norm = _normalize(_section5(_read_doc()))
        actual = hashlib.sha256(norm.encode("utf-8")).hexdigest()
        assert actual == _SIGNED_SECTION5_SHA256, (
            "§5 실패정의가 서명본(2026-08-30)과 다르다 — 12/31 판정 전 수정 금지. "
            "판정 후 v2 개정이라면 이 해시를 같은 PR에서 의식적으로 갱신하라."
        )

    def test_frozen_threshold_tokens_present(self) -> None:
        sec = _section5(_read_doc())
        missing = [t for t in _FROZEN_TOKENS if t not in sec]
        assert not missing, f"실패정의 판정 임계 토큰 소실/변형: {missing}"

    def test_five_definitions_enumerated(self) -> None:
        sec = _section5(_read_doc())
        for label in ("F-Ⅰ", "F-Ⅱ", "F-Ⅲ", "F-Ⅳ", "F-Ⅴ"):
            assert f"**{label}**" in sec, f"실패정의 {label} 항목 부재"

    def test_freeze_clause_in_heading(self) -> None:
        # 동결 규율이 §5 제목 자체에 명문 — 제목에서 지우는 것도 위반이다
        heading = _section5(_read_doc()).splitlines()[0]
        assert "12월 수정 금지" in heading

    def test_judgment_codes_exist_in_enum(self) -> None:
        # F-Ⅲ 산식의 판단형 3코드가 enum에 실재 — 문서↔코드 교차 결선
        # (부분집합 자체의 동결은 test_generation_failure_code.py 몫)
        for name in ("F3", "F6", "F7"):
            assert name in GenerationFailureCode.__members__


class TestSignatureRecordFrozen:
    """서명 기록(게이트 clear) 동결 — 게이트 되돌림·evidence 교체 양쪽을 차단.

    두 우회 경로가 있다: ①게이트를 pending으로 되돌려 '서명 전' 상태로 만들기 ②status는
    cleared로 두고 evidence만 다른 텍스트(철회·다른 근거)로 갈아끼우기. ②는 "비어있지
    않은가"만 보는 검사를 그대로 통과하므로 evidence *전문 해시*로 동결한다.
    """

    def test_gate_is_cleared(self) -> None:
        gate = _signed_gate(_GATES.read_text(encoding="utf-8"))
        assert (
            gate.get("status") == "cleared"
        ), f"{_GATE_ID}가 cleared가 아니다 — 서명(2026-08-30 Kiki) 후 되돌림은 동결 위반"

    def test_signed_evidence_content_frozen(self) -> None:
        gate = _signed_gate(_GATES.read_text(encoding="utf-8"))
        evidence = gate.get("evidence")
        assert (
            isinstance(evidence, str) and evidence.strip()
        ), "서명 evidence가 비어 있다 — clear가 곧 서명이므로 근거 없는 clear는 무효"
        actual = hashlib.sha256(evidence.encode("utf-8")).hexdigest()
        assert actual == _SIGNED_EVIDENCE_SHA256, (
            "서명 evidence가 서명본(2026-08-30)과 다르다 — 문안 교체·철회는 12/31 판정 전 금지. "
            "서명 철회가 Kiki의 결정이라면 이 해시도 같은 PR에서 의식적으로 갱신하라."
        )

    def test_signed_evidence_states_signing_date(self) -> None:
        # 블록이 아니라 evidence *값*에서 확인한다 — 게이트 블록에는 `requested: 2026-08-30`이
        # 항상 있어 블록 대상 검사는 evidence가 통째로 바뀌어도 통과한다(P2 지적의 원인).
        evidence = _signed_gate(_GATES.read_text(encoding="utf-8")).get("evidence")
        assert isinstance(evidence, str) and "2026-08-30" in evidence


class TestFreezeDiscrimination:
    """변별력 실측 — 이 동결 장치가 실패 상태에서 실제로 실패 신호를 내는가."""

    def test_mutated_threshold_is_actually_detected(self) -> None:
        # 가장 그럴듯한 위반(임계 완화)을 시뮬레이트 — 해시·토큰 두 축 모두 잡아야 한다
        norm = _normalize(_section5(_read_doc()))
        mutated = norm.replace("12분", "20분")
        assert mutated != norm, "뮤테이션 자체가 무효(원문에 12분 부재?) — 검증 스텝 무변별"
        assert hashlib.sha256(mutated.encode("utf-8")).hexdigest() != _SIGNED_SECTION5_SHA256
        assert any(t not in mutated for t in _FROZEN_TOKENS)

    def test_replaced_evidence_is_actually_detected(self) -> None:
        # P2 지적(2026-08-30 Codex)의 상시 봉인: status는 cleared로 둔 채 evidence만
        # 철회 문구로 갈아끼우는 우회가 해시 축에서 실제로 검출되는지 매 실행 확인한다.
        # 구 단언 3종(cleared·비어있지 않음·블록 내 날짜)은 이 뮤테이션을 전부 통과했다.
        evidence = _signed_gate(_GATES.read_text(encoding="utf-8")).get("evidence")
        assert isinstance(evidence, str)
        retracted = "서명 철회"
        assert retracted != evidence, "뮤테이션 자체가 무효 — 검증 스텝 무변별"
        assert hashlib.sha256(retracted.encode("utf-8")).hexdigest() != _SIGNED_EVIDENCE_SHA256

    def test_missing_section_fails_loudly(self) -> None:
        with pytest.raises(AssertionError, match="§5"):
            _section5("# 다른 문서\n\n## §4. 실패코드\n본문\n")

    def test_missing_gate_fails_loudly(self) -> None:
        with pytest.raises(AssertionError, match=_GATE_ID):
            _signed_gate("gates:\n  - id: G-other-gate\n    status: pending\n")

    def test_unparseable_gates_file_fails_loudly(self) -> None:
        # 파싱 실패를 "위반 0 통과"로 위장하지 않는다(침묵 실패 금지).
        with pytest.raises(AssertionError, match="파싱 실패"):
            _signed_gate("gates: 이건_목록이_아니다\n")
