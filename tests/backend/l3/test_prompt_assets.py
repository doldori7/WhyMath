"""L3 생성 프롬프트 정본 로더 + **정본↔코드 인용 드리프트** 회귀 (OPS-16).

왜 이 파일이 있는가
------------------
L4 교수학 프롬프트는 `docs/prompts/` 정본 + 코드 인용 + 감사가 있는데, L3 생성 프롬프트는
코드 인라인이 정본이고 감사가 0이었다(`ai_content_generation_gap_review.md` §3 D4). 정본을
문서로 옮긴 뒤 남는 위험은 **드리프트**다 — 문서와 코드가 서로 다른 것을 가리키는 상태.
코드에 사본을 두지 않으므로 "두 문자열이 다르다"는 형태의 드리프트는 원천적으로 없고, 대신
아래 네 형태가 남는다. 이 파일이 그 넷을 전부 닫는다.

검증 계약
--------
① **유령 인용 0** — `REQUIRED_ASSET_IDS`(코드가 부르는 id)가 전부 정본에 실재한다.
   실패 = 런타임 `PromptAssetError`(그 경로가 프로덕션에서 터진다).
② **고아 자산 0** — 정본에 있는데 아무도 안 부르는 문면이 없다. 고아는 감사만 통과하고
   실제로는 학생 경로에 영향이 없는 *유령 게이트*를 만든다.
③ **플레이스홀더 정합** — 정본 템플릿이 요구하는 `{{NAME}}`을 코드가 정확히 채운다.
   미치환 잔여는 그대로 LLM에 나가므로(조용한 품질 붕괴) `fill()`이 예외로 막는다.
④ **프로덕션 경로 동일성** — 4모듈이 LLM에 실제로 넘기는 문면이 정본 원문과 같다
   (`build_visualization_prompt`처럼 파생이 얹히는 자산은 *정본 문안이 포함*됨을 본다).

정직한 공백
----------
- **문면의 교수학적 품질은 판정하지 않는다** — 이 파일은 "정본과 코드가 같은 것을 가리키는가"만
  본다. 레일(저작권·봉인·독립성) 판정은 `harness/prompt_asset_audit`의 몫이다(축 분리).
"""

from __future__ import annotations

import logging
from pathlib import Path

import pytest

from whymath_backend.l3 import cross_verify, visualization
from whymath_backend.l3.equivalent import llm_generator, rephrase
from whymath_backend.l3.prompt_assets import (
    PROMPT_ASSET_DIR,
    PROMPT_ASSET_FILES,
    REQUIRED_ASSET_IDS,
    PromptAssetError,
    asset_registry,
    fill,
    parse_prompt_blocks,
    prompt_text,
    reset_prompt_asset_cache,
)


@pytest.fixture(autouse=True)
def _isolate_caches() -> None:
    """정본 캐시를 테스트마다 무효화 — 경로 monkeypatch가 이전 캐시에 가려지지 않게."""
    reset_prompt_asset_cache()
    visualization.reset_render_contract_cache()


# ── 계약 ①② : 유령 인용 0 · 고아 자산 0 ────────────────────────────────────────


class TestRegistryDrift:
    def test_every_required_asset_exists_in_canon(self) -> None:
        """계약 ① — 코드가 부르는 id가 정본에 전부 있다(없으면 런타임 차단)."""
        missing = [name for name in REQUIRED_ASSET_IDS if name not in asset_registry()]
        assert not missing, (
            f"코드가 인용하는데 정본에 없는 프롬프트 자산: {missing} — "
            f"docs/prompts/{PROMPT_ASSET_FILES}에 `prompt:<id>` 블록을 추가하라."
        )

    def test_no_orphan_assets_in_canon(self) -> None:
        """계약 ② — 정본에만 있고 아무도 안 쓰는 고아 문면이 없다."""
        orphans = sorted(set(asset_registry()) - set(REQUIRED_ASSET_IDS))
        assert not orphans, (
            f"정본에만 있고 코드가 인용하지 않는 자산: {orphans} — 쓰거나 지워라"
            "(고아 문면은 감사만 통과하고 실제 경로에 영향이 없다)."
        )

    def test_required_ids_are_sorted_and_unique(self) -> None:
        """목록 자체의 위생 — 중복·정렬 붕괴는 리뷰에서 드리프트를 숨긴다."""
        assert list(REQUIRED_ASSET_IDS) == sorted(set(REQUIRED_ASSET_IDS))

    def test_every_canon_file_contributes_assets(self) -> None:
        """정본 파일 하나가 통째로 파싱 실패해도 '자산 0건 통과'가 되지 않게 파일별 하한 확인."""
        for filename in PROMPT_ASSET_FILES:
            blocks = parse_prompt_blocks(
                (PROMPT_ASSET_DIR / filename).read_text(encoding="utf-8"), origin=filename
            )
            assert blocks, f"{filename}: 프롬프트 블록이 0건 — 파서·문서 형식이 어긋났다."


# ── 계약 ③ : 플레이스홀더 정합 ─────────────────────────────────────────────────


class TestPlaceholders:
    def test_fill_substitutes_and_detects_leftovers(self) -> None:
        assert fill("a{{X}}b", X="1") == "a1b"
        with pytest.raises(PromptAssetError, match="치환되지 않은"):
            fill("a{{X}}b{{Y}}", X="1")

    def test_fill_accepts_empty_value(self) -> None:
        """값이 비어야 정상인 자리(주제 힌트 없음)는 빈 문자열 치환으로 통과한다."""
        assert fill("{{TOPIC_LINE}}본문", TOPIC_LINE="") == "본문"

    def test_json_braces_in_prompt_are_not_placeholders(self) -> None:
        """프롬프트 본문의 JSON 중괄호(`{"type": ...}`)를 플레이스홀더로 오인하지 않는다."""
        text = prompt_text("l3.cross_verify.reconstruct_system")
        assert '{"total"' in text
        assert fill(text) == text


# ── 계약 ④ : 프로덕션 경로가 정본 문면을 그대로 쓴다 ─────────────────────────────


class TestProductionQuotesCanon:
    def test_equivalent_system_prompt_is_canon(self) -> None:
        assert llm_generator._system_prompt() == prompt_text("l3.equivalent.system")

    def test_rephrase_system_prompt_is_canon(self) -> None:
        assert rephrase._system_prompt() == prompt_text("l3.rephrase.system")

    def test_rephrase_user_prompt_is_canon_template(self) -> None:
        built = rephrase._build_prompt("x^2-6x+8=0의 큰 근은?", "x^2-6x+8 = 0")
        assert built == fill(
            prompt_text("l3.rephrase.user"),
            QUESTION_TEXT="x^2-6x+8=0의 큰 근은?",
            EQUATION="x^2-6x+8 = 0",
        )
        assert "{{" not in built

    def test_cross_verify_perspectives_use_canon(self) -> None:
        """K=3 관점의 시스템 프롬프트가 각각 정본 자산과 동일(원리별 문면 동결)."""
        expected = {
            "independent_reconstruction": "l3.cross_verify.reconstruct_system",
            "adversarial_falsification": "l3.cross_verify.falsify_system",
            "model_grounding": "l3.cross_verify.grounding_system",
        }
        actual = {p.principle: p.system_prompt for p in cross_verify.PROBABILITY_PERSPECTIVES}
        assert set(actual) == set(expected)
        for principle, asset_id in expected.items():
            assert actual[principle] == prompt_text(asset_id)

    def test_cross_verify_render_uses_canon_templates(self) -> None:
        subject = cross_verify.ResidueSubject(
            problem_id="p1",
            question_text="서로 다른 공 3개에서 2개를 뽑는 경우의 수는?",
            answer="3",
            answer_explanation="조합 3C2 = 3",
            machine_model_ko="3개에서 2개를 순서 없이 뽑는다",
            machine_total=3,
            machine_favorable=3,
            authored_by="deterministic_enumerator",
        )
        rendered = {p.principle: p.render(subject) for p in cross_verify.PROBABILITY_PERSPECTIVES}
        assert rendered["independent_reconstruction"] == fill(
            prompt_text("l3.cross_verify.reconstruct_user"), QUESTION_TEXT=subject.question_text
        )
        # 독립 재구성의 가시 필드에 정답·형식 모델이 새지 않는다(레일ⓒ의 런타임 확인).
        assert subject.answer not in rendered["independent_reconstruction"].replace(
            subject.question_text, ""
        )
        assert subject.machine_model_ko not in rendered["independent_reconstruction"]
        assert subject.machine_model_ko in rendered["model_grounding"]

    def test_visualization_prompt_embeds_canon_template(self) -> None:
        """파생 구조(VIZ-02) 보존 — 정본 문안이 들어가되 타입 목록은 계약에서 파생된다."""
        types = visualization.renderable_visualization_types()
        system_prompt, user_prompt = visualization.build_visualization_prompt("극한", "고2")
        assert (
            fill(
                prompt_text("l3.visualization.system"),
                TYPE_UNION="|".join(types),
                TYPE_COUNT=str(len(types)),
            )
            in system_prompt
        )
        assert user_prompt == "\n".join(
            [
                fill(prompt_text("l3.visualization.user_head"), CONCEPT="극한", LEVEL="고2"),
                prompt_text("l3.visualization.user_tail"),
            ]
        )

    def test_visualization_styles_line_only_when_given(self) -> None:
        with_styles = visualization._user_prompt("삼각함수", "고2", ["단위원"])
        assert prompt_text("l3.visualization.user_styles").split("{{")[0] in with_styles
        assert "단위원" in with_styles
        assert "권장 시각화 양식" not in visualization._user_prompt("삼각함수", "고2")


# ── fail-closed 강등 정책 (침묵 실패 금지) ──────────────────────────────────────


class TestFailClosedDegradation:
    """정본 부재·파손은 **폴백하지 않고 차단**한다.

    `l3/visualization.py`의 렌더 계약은 "읽기 실패 = 직전 동작 유지"로 강등할 수 있었다 —
    코드 측 폴백값이 계약과 동일함을 CI가 동결했기 때문이다. 프롬프트 *문면*에는 그런 동치
    폴백이 존재할 수 없다(사본을 두는 순간 정본이 둘이 된다). 그래서 방향이 반대다: 레일이
    빠진 문면으로 LLM을 부르느니 요청을 실패시킨다(의사결정 우선순위 ② 법적 준수 > ⑥⑦ 비용·속도).
    """

    def test_missing_canon_file_raises_with_typed_log(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        monkeypatch.setattr("whymath_backend.l3.prompt_assets.PROMPT_ASSET_DIR", tmp_path)
        reset_prompt_asset_cache()
        with caplog.at_level(logging.ERROR, logger="whymath.l3.prompt_assets"):
            with pytest.raises(PromptAssetError, match="읽을 수 없다"):
                prompt_text("l3.equivalent.system")
        assert "error_type=FileNotFoundError" in caplog.text

    def test_unknown_asset_id_raises_with_typed_log(self, caplog: pytest.LogCaptureFixture) -> None:
        with caplog.at_level(logging.ERROR, logger="whymath.l3.prompt_assets"):
            with pytest.raises(PromptAssetError, match="정본에 없는"):
                prompt_text("l3.does.not.exist")
        assert "error_type=KeyError" in caplog.text

    def test_unclosed_fence_fails_loudly(self) -> None:
        """파손된 문서를 '블록 0건'으로 조용히 넘기지 않는다(파손 위장 금지)."""
        with pytest.raises(PromptAssetError, match="닫히지 않은"):
            parse_prompt_blocks("```prompt:x\n본문\n", origin="fake.md")

    def test_duplicate_asset_id_fails_loudly(self) -> None:
        """같은 id가 두 번 나오면 어느 쪽이 정본인지 결정 불가 — 덮어쓰지 않고 실패한다."""
        with pytest.raises(PromptAssetError, match="id 중복"):
            parse_prompt_blocks("```prompt:x\nA\n```\n```prompt:x\nB\n```\n", origin="fake.md")

    def test_non_prompt_fences_are_ignored(self) -> None:
        """정본 파일의 설명용 코드 블록·산문은 자산이 아니다(문서로서도 읽히게)."""
        blocks = parse_prompt_blocks(
            "설명 산문\n```python\nprint(1)\n```\n```prompt:a.b\n본문\n```\n", origin="fake.md"
        )
        assert blocks == {"a.b": "본문"}


class TestCachingBehaviour:
    def test_registry_read_once(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """매 LLM 호출마다 파일을 읽지 않는다 — 프로세스당 1회(lru_cache)."""
        reset_prompt_asset_cache()
        reads: list[str] = []
        original = Path.read_text

        def counting_read_text(self: Path, *args: object, **kwargs: object) -> str:
            reads.append(self.name)
            return original(self, *args, **kwargs)  # type: ignore[arg-type]

        monkeypatch.setattr(Path, "read_text", counting_read_text)
        for _ in range(5):
            prompt_text("l3.equivalent.system")
            prompt_text("l3.rephrase.system")
        assert sorted(reads) == sorted(PROMPT_ASSET_FILES)
