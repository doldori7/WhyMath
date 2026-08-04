"""L3 생성 프롬프트 3레일 감사 — 순수 단위 + **배포 정본 봉인** + 결함 주입 변별력 (OPS-16).

세 축:
① 순수 단위 — `audit_generation_prompts`의 레일 판정(저작권·봉인·독립성)·미선언 자산·자산 결측.
② **배포 정본 봉인**(핵심 소비처) — 실제 `docs/prompts/l3_*.md` 정본이 전 레일을 통과함을 단언.
   레일 지시문이 정본에서 사라지면 여기서 red가 나고 CI 게이트도 exit 1이 된다.
③ **변별력 상시 봉인**(CLAUDE.md "변별력 없는 검증 스텝 금지") — 실제 정본 문면에 결함을
   주입해(저작권 1줄 제거·봉인 어구 제거·생성자 문맥 주입·정답 필드 노출) 각각이 *실제로*
   검출됨을 CI가 매번 재확인한다. 양성 대조(정상 정본은 위반 0)도 함께 둬 무차별 실패기가
   아님을 보인다. 실제 파일은 훼손하지 않는다 — 메모리 위 자산 맵에만 결함을 넣는다.

정직한 공백
----------
- 레일은 **지시문의 실재**를 본다. 그 지시문을 모델이 실제로 따르는지는 이 축이 아니다
  (그건 `rephrase_hygiene`·게이트·강등전의 몫 — 출력측 레일과 프롬프트측 레일의 이중 방어).
"""

from __future__ import annotations

from whymath_backend.harness.prompt_asset_audit import (
    L3_NO_RAIL_REASONS,
    L3_PROMPT_RAILS,
    RAIL_COPYRIGHT,
    RAIL_INDEPENDENCE,
    RAIL_SEAL,
    audit_generation_prompts,
    render_generation_audit_markdown,
    resolve_l3_prompt_assets,
)
from whymath_backend.l3.prompt_assets import REQUIRED_ASSET_IDS


def _violations(assets: dict[str, str]) -> list[str]:
    """자산 맵을 배포 선언표로 감사해 위반 사유를 평탄화(결함 주입 판정 공용)."""
    return [v for item in audit_generation_prompts(assets) for v in item.violations]


# ── 축 ① : 순수 단위 ───────────────────────────────────────────────────────────


class TestRailUnits:
    def test_copyright_rail_detects_missing_prohibition(self) -> None:
        items = audit_generation_prompts(
            {"a.system": "그냥 문제를 만드세요."}, rails={"a.system": (RAIL_COPYRIGHT,)}
        )
        assert not items[0].ok
        assert "저작권 금지 지시문 어구 결측" in items[0].violations[0]

    def test_copyright_rail_passes_with_full_prohibition(self) -> None:
        text = "평가원·EBS·검정 교과서 본문을 복제하지 말고 순수 자작 문제만 출제하세요."
        items = audit_generation_prompts({"a.system": text}, rails={"a.system": (RAIL_COPYRIGHT,)})
        assert items[0].ok

    def test_seal_rail_detects_missing_invariance(self) -> None:
        items = audit_generation_prompts(
            {"b.system": "발문을 자유롭게 다시 쓰세요."}, rails={"b.system": (RAIL_SEAL,)}
        )
        assert "봉인 지시문 어구 결측" in items[0].violations[0]

    def test_independence_rail_detects_generator_context(self) -> None:
        items = audit_generation_prompts(
            {"c.falsify_system": "너는 WhyMath의 동등문제 저작자다. 결함을 찾아라."},
            rails={"c.falsify_system": (RAIL_INDEPENDENCE,)},
        )
        assert "생성자 문맥 주입" in items[0].violations[0]

    def test_undeclared_asset_is_a_violation(self) -> None:
        """선언표에 없는 자산은 '레일 없음'이 아니라 **미선언 위반**이다(판단 누락 강제)."""
        items = audit_generation_prompts({"zz.new": "임의 문면"}, rails={})
        assert "레일 선언표에 없는 자산" in items[0].violations[0]

    def test_declared_but_missing_asset_is_a_violation(self) -> None:
        """선언된 자산이 정본에서 사라지면 '위반 0 통과'가 아니라 위반이다(측정 실패 ≠ 통과)."""
        items = audit_generation_prompts({}, rails={"a.system": (RAIL_COPYRIGHT,)})
        assert "정본에 없다" in items[0].violations[0]

    def test_render_reports_violation_count(self) -> None:
        report = render_generation_audit_markdown(
            audit_generation_prompts({"a.system": "빈 문면"}, rails={"a.system": (RAIL_COPYRIGHT,)})
        )
        assert "위반 1" in report
        assert "🔴" in report


# ── 축 ② : 배포 정본 봉인 ──────────────────────────────────────────────────────


class TestDeployedCanonSealed:
    def test_real_canon_passes_every_rail(self) -> None:
        """양성 대조 겸 봉인 — 실제 정본은 전 레일 통과(위반 0)."""
        assert _violations(resolve_l3_prompt_assets()) == []

    def test_rail_table_covers_every_quoted_asset(self) -> None:
        """코드가 인용하는 자산이 전부 레일 선언표에 있다(선언 누락 = 감사 사각)."""
        assert set(L3_PROMPT_RAILS) == set(REQUIRED_ASSET_IDS)

    def test_every_railless_asset_carries_a_reason(self) -> None:
        """레일 0 자산은 **사유와 함께**여야 한다(빈 사유로 조용히 빠져나가지 못하게)."""
        railless = {name for name, rails in L3_PROMPT_RAILS.items() if not rails}
        assert railless == set(L3_NO_RAIL_REASONS)
        blank = [name for name in railless if not L3_NO_RAIL_REASONS[name].strip()]
        assert not blank, f"레일 미적용 사유가 비어 있다(무효): {blank}"

    def test_three_rails_are_all_in_use(self) -> None:
        """준거 3종이 전부 실제 자산에 걸려 있다 — 한 축이 죽어도 초록이면 위장이다."""
        used = {rail for rails in L3_PROMPT_RAILS.values() for rail in rails}
        assert used == {RAIL_COPYRIGHT, RAIL_SEAL, RAIL_INDEPENDENCE}


# ── 축 ③ : 결함 주입 변별력 (실제 정본 문면에 결함을 넣어 검출 확인) ─────────────


class TestDefectInjectionDiscrimination:
    """실패 상태에서 *실제로* 실패 신호가 나는지 상시 재확인한다.

    성공/실패 양쪽에서 같은 값을 내는 검사는 검증이 아니라 위장이다(2026-07-17 logconfig
    `delay:true` 사고의 일반형). 여기서 깨뜨리는 것은 메모리 위 사본이며 저장소 파일은 그대로다.
    """

    def test_defect_copyright_line_removed_is_detected(self) -> None:
        """결함 ① — 저작권 금지 **한 줄**을 지우면 검출된다(acceptance ④의 상시 판).

        정본의 그 줄이 담은 금지 대상 열거(평가원·EBS·검정 교과서)가 통째로 사라지는 형태다.
        """
        assets = resolve_l3_prompt_assets()
        lines = assets["l3.equivalent.system"].splitlines()
        kept = [line for line in lines if "평가원·EBS·검정 교과서" not in line]
        assert (
            len(kept) == len(lines) - 1
        ), "저작권 금지 줄을 정본에서 찾지 못했다(문면이 바뀌었나?)"
        assets["l3.equivalent.system"] = "\n".join(kept)
        violations = _violations(assets)
        assert any("저작권 금지 지시문 어구 결측" in v for v in violations), violations

    def test_defect_seal_anchor_removed_is_detected(self) -> None:
        """결함 ② — rephrase 사용자 프롬프트의 보존 앵커를 지우면 검출된다."""
        assets = resolve_l3_prompt_assets()
        assets["l3.rephrase.user"] = assets["l3.rephrase.user"].replace(
            "한 글자도 바꾸지 말고", "적당히"
        )
        assert any("봉인 지시문 어구 결측" in v for v in _violations(assets))

    def test_defect_generator_context_injected_is_detected(self) -> None:
        """결함 ③ — 검증자 프롬프트에 저작자 역할 선언이 새면 검출된다(생성자≠검증자 붕괴)."""
        assets = resolve_l3_prompt_assets()
        assets["l3.cross_verify.falsify_system"] += "\n참고: 너는 WhyMath의 동등문제 저작자다."
        assert any("생성자 문맥 주입" in v for v in _violations(assets))

    def test_defect_answer_leaked_into_reconstruction_is_detected(self) -> None:
        """결함 ④ — 독립 재구성 관점에 정답 필드가 새면 검출된다(앵커링 공유)."""
        assets = resolve_l3_prompt_assets()
        assets["l3.cross_verify.reconstruct_user"] += "\n\n[제시된 정답]\n{{ANSWER}}"
        assert any("정답·형식모델 필드 노출" in v for v in _violations(assets))

    def test_defect_hidden_declaration_removed_is_detected(self) -> None:
        """결함 ⑤ — 정답 은닉 선언이 사라지면 검출된다(모델이 정답을 요구할 여지)."""
        assets = resolve_l3_prompt_assets()
        assets["l3.cross_verify.reconstruct_system"] = assets[
            "l3.cross_verify.reconstruct_system"
        ].replace("다른 사람의 풀이나 정답은 주어지지 않는다.", "")
        assert any("정답 은닉 선언" in v for v in _violations(assets))

    def test_defect_asset_deleted_is_detected(self) -> None:
        """결함 ⑥ — 자산을 통째로 지우면 '감사 대상 0건 통과'가 아니라 위반이다."""
        assets = resolve_l3_prompt_assets()
        del assets["l3.equivalent.system"]
        assert any("정본에 없다" in v for v in _violations(assets))
