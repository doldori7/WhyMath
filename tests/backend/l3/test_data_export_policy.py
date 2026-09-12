"""데이터 등급 → 국외(클라우드) 반출 게이트 계약 동결 (EOS-59).

이 파일이 지키는 것 (변별력을 **양방향**으로 잡는다)
--------------------------------------------------
한 방향만 보면 반대 결함을 못 잡는다 — "제한 자료를 막는다"만 검증하면 *전부* LOCAL로
보내는 구현도 통과하고, 그러면 게이트가 아니라 클라우드 차단기가 된다. 그래서:

  ① 제한 등급(AIHub) + 클라우드 희망 → LOCAL 강등          (차단이 작동한다)
  ② 비제한 등급(자체 저작) + 클라우드 희망 → 클라우드 유지   (**양성 대조** — 무차별 차단 아님)
  ③ 등급 미지정 → 보수 기본값(UNKNOWN)으로 차단             (fail-closed)
  ④ 게이트는 티어를 **올리지 못한다**                        (단방향성 — 전 격자 전수)

권리 판정의 정본은 `l1/rights/permission_map.py`다. 이 테스트는 그 정본이 라우팅에
*배선됐는지*를 본다 — 권리표 자체를 여기서 다시 정의하지 않는다(그러면 기준이 두 벌이 된다).
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from whymath_backend.l1.rights.permission_map import license_to_permission_set
from whymath_backend.l3.data_export_policy import (
    EXPORT_ALLOWED,
    EXPORT_PROHIBITED,
    EXPORT_UNVERIFIED,
    OFFSHORE_TIERS,
    export_judgment,
    export_judgment_for,
    guard_data_export,
    normalize_licenses,
)
from whymath_backend.l3.data_grade_defaults import (
    SELF_AUTHORED_CORPUS,
    STUDENT_SUBMITTED,
    STUDENT_SUBMITTED_WITH_CORPUS,
    SYNTHETIC_PROBE,
)
from whymath_backend.l3.models import (
    DEFAULT_DATA_LICENSES,
    CostTier,
    LocalModelTier,
    ModelFamily,
    RoutingDecision,
    RoutingRequest,
)
from whymath_backend.l3.router import Router, business_cost_tier, langfuse_fields
from whymath_backend.schema.enums import LicenseType, PermissionAction


def _cloud_wanting_request(**overrides: object) -> RoutingRequest:
    """비즈니스 축(구독·예산)만으로는 **반드시 CLOUD_MID로 가는** 요청.

    premium + requires_reasoning + 충분한 예산 → 축1 규칙4. killer/prove가 아니라 HIGH로
    승급하지 않고, sync=True라 async로도 새지 않는다. 이 전제가 깨지면 아래 테스트는
    "차단됐다"가 아니라 "애초에 클라우드를 원하지 않았다"를 재게 되므로, 각 테스트가
    `business_cost_tier`로 전제 자체를 먼저 확인한다.
    """
    payload: dict[str, object] = {
        "task_type": "diagnose",
        "difficulty": "hard",
        "requires_reasoning": True,
        "student_subscription": "premium",
        "budget_krw": 1000.0,
        "sync": True,
        "max_latency_ms": 30000,
    }
    payload.update(overrides)
    return RoutingRequest(**payload)  # type: ignore[arg-type]


# ══════════════════════════════════════════════════════════════════════
# 권리 모델 위임 — 등급 어휘가 두 벌이 되지 않았는가
# ══════════════════════════════════════════════════════════════════════
class TestRightsModelIsTheSingleSourceOfTruth:
    @pytest.mark.parametrize("license_type", list(LicenseType))
    def test_judgment_matches_permission_map_export_bit(self, license_type: LicenseType) -> None:
        """모든 라이선스의 판정이 `permission_map`의 `export` 값과 1:1로 일치한다.

        이 테스트가 깨진다면 게이트가 권리표를 *자기 방식으로 다시 정의*했다는 뜻이다
        (기준 이원화 — EOS-59가 명시적으로 금지한 실패 모드).
        """
        expected = license_to_permission_set(license_type).allows(PermissionAction.EXPORT)
        judgment = export_judgment((license_type,))
        assert judgment.permitted is expected
        if expected is True:
            assert judgment.reason == EXPORT_ALLOWED
            assert judgment.blocking_licenses == ()
        elif expected is False:
            assert judgment.reason == EXPORT_PROHIBITED
            assert judgment.blocking_licenses == (license_type,)
        else:
            assert judgment.reason == EXPORT_UNVERIFIED
            assert judgment.blocking_licenses == (license_type,)

    def test_aihub_is_prohibited_because_the_rights_map_says_so(self) -> None:
        """AIHub 4조건 ②(국외반출 별도합의)가 라우팅까지 도달했는가 — 이 태스크의 핵심 사실."""
        assert license_to_permission_set(LicenseType.AIHUB_OPEN).export is False
        assert export_judgment((LicenseType.AIHUB_OPEN,)).reason == EXPORT_PROHIBITED

    def test_conservative_merge_prohibited_beats_unverified_beats_allowed(self) -> None:
        """복수 자료는 *가장 제한적인* 판정을 따른다(policy_engine.DecisionPriority 동형)."""
        assert (
            export_judgment((LicenseType.INTERNAL_OWNED, LicenseType.AIHUB_OPEN)).reason
            == EXPORT_PROHIBITED
        )
        assert (
            export_judgment((LicenseType.INTERNAL_OWNED, LicenseType.UNKNOWN)).reason
            == EXPORT_UNVERIFIED
        )
        assert (
            export_judgment((LicenseType.INTERNAL_OWNED, LicenseType.KOGL_1)).reason
            == EXPORT_ALLOWED
        )
        # 금지가 미확인을 이긴다(순서 무관)
        mixed = export_judgment((LicenseType.UNKNOWN, LicenseType.AIHUB_OPEN))
        assert mixed.reason == EXPORT_PROHIBITED
        assert mixed.blocking_licenses == (LicenseType.AIHUB_OPEN,)

    def test_empty_license_list_is_unverified_not_allowed(self) -> None:
        """빈 목록은 '자료 없음'이 아니라 '무엇이 실렸는지 모름' → 차단(fail-closed)."""
        judgment = export_judgment(())
        assert judgment.permitted is None
        assert judgment.reason == EXPORT_UNVERIFIED
        assert judgment.blocks_offshore is True


class TestNormalizeLicenses:
    def test_accepts_enum_and_string_forms(self) -> None:
        """`use_enum_values=True`라 필드값이 문자열일 수 있다 — 양쪽 다 받는다."""
        assert normalize_licenses((LicenseType.KOGL_1, "AIHUB_OPEN")) == (
            LicenseType.KOGL_1,
            LicenseType.AIHUB_OPEN,
        )

    def test_unknown_string_raises_instead_of_rounding_to_unknown(self) -> None:
        """미지 문자열을 조용히 UNKNOWN으로 반올림하면 오타가 '우연한 안전'으로 위장된다."""
        with pytest.raises(ValueError):
            normalize_licenses(("NOT_A_LICENSE",))

    def test_non_string_non_enum_raises(self) -> None:
        with pytest.raises(TypeError):
            normalize_licenses((123,))


# ══════════════════════════════════════════════════════════════════════
# 게이트 — 양방향 변별력 + 단방향성
# ══════════════════════════════════════════════════════════════════════
class TestGuardDataExport:
    def test_prohibited_material_demotes_cloud_to_local(self) -> None:
        """① 제한 등급 + 클라우드 희망 → LOCAL."""
        assert guard_data_export(CostTier.CLOUD_MID, (LicenseType.AIHUB_OPEN,)) is CostTier.LOCAL
        assert guard_data_export(CostTier.CLOUD_HIGH, (LicenseType.AIHUB_OPEN,)) is CostTier.LOCAL

    def test_exportable_material_keeps_cloud(self) -> None:
        """② 양성 대조 — 비제한 등급은 클라우드에 그대로 간다(무차별 차단이 아니다)."""
        assert guard_data_export(CostTier.CLOUD_MID, SELF_AUTHORED_CORPUS) is CostTier.CLOUD_MID
        assert guard_data_export(CostTier.CLOUD_HIGH, SYNTHETIC_PROBE) is CostTier.CLOUD_HIGH

    def test_unspecified_material_is_blocked_by_the_conservative_default(self) -> None:
        """③ 미지정(=UNKNOWN 기본값) → 차단."""
        assert guard_data_export(CostTier.CLOUD_MID, DEFAULT_DATA_LICENSES) is CostTier.LOCAL

    def test_local_desire_is_untouched_even_for_prohibited_material(self) -> None:
        """이미 LOCAL이면 반출 자체가 없다 — 게이트는 아무것도 하지 않는다."""
        assert guard_data_export(CostTier.LOCAL, (LicenseType.AIHUB_OPEN,)) is CostTier.LOCAL

    @pytest.mark.parametrize("desired", list(CostTier))
    @pytest.mark.parametrize("license_type", list(LicenseType))
    def test_gate_never_raises_the_tier(self, desired: CostTier, license_type: LicenseType) -> None:
        """④ 단방향성 전수 — (전 티어 × 전 라이선스) 격자에서 결과는 항상 `desired` 또는 LOCAL.

        게이트가 티어를 *올리는* 구현(예: 반출 허용 시 승급)을 넣으면 이 격자가 즉시 깨진다.
        """
        result = guard_data_export(desired, (license_type,))
        assert result in (desired, CostTier.LOCAL)

    def test_string_tier_input_does_not_bypass_the_gate(self) -> None:
        """`use_enum_values=True` 경로에서 오는 *문자열* 티어도 게이트를 지난다.

        `CostTier(str, Enum)`이라 문자열이 멤버십에 걸리는 덕인데, 그 성질이 사라지면
        (예: 순수 Enum으로 바꾸면) 문자열 입력만 조용히 우회하게 된다 — 그 회귀를 봉인한다.
        """
        assert guard_data_export("cloud_mid", (LicenseType.AIHUB_OPEN,)) is CostTier.LOCAL
        assert guard_data_export("cloud_mid", SELF_AUTHORED_CORPUS) is CostTier.CLOUD_MID

    def test_unknown_tier_string_raises_instead_of_bypassing(self) -> None:
        """미지의 티어 문자열은 '국외 아님'으로 통과되지 않고 큰 소리로 실패한다."""
        with pytest.raises(ValueError):
            guard_data_export("cloud_ultra", (LicenseType.AIHUB_OPEN,))

    def test_offshore_tiers_cover_every_non_local_tier(self) -> None:
        """새 클라우드 티어가 생기면 게이트를 우회한다 — 그 사각을 상시 봉인한다."""
        assert OFFSHORE_TIERS == {tier for tier in CostTier if tier is not CostTier.LOCAL}


# ══════════════════════════════════════════════════════════════════════
# 라우터 배선 — 게이트가 실제 결정 경로에 붙었는가
# ══════════════════════════════════════════════════════════════════════
class TestRouterWiring:
    def test_aihub_request_that_wanted_cloud_lands_local_with_the_signal(self) -> None:
        req = _cloud_wanting_request(data_licenses=(LicenseType.AIHUB_OPEN,))
        # 전제: 비즈니스 축만 보면 이 요청은 클라우드로 간다(차단을 실제로 잰다는 증거).
        assert business_cost_tier(req) is CostTier.CLOUD_MID

        decision = Router().route(req)
        assert decision.cost_tier == CostTier.LOCAL
        assert decision.data_export_blocked is True
        assert decision.data_export_reason == EXPORT_PROHIBITED
        assert "data-export gate" in decision.reason

    def test_exportable_request_still_reaches_cloud(self) -> None:
        """양성 대조 — 라우터 경유에서도 비제한 자료는 클라우드로 간다."""
        req = _cloud_wanting_request(data_licenses=SELF_AUTHORED_CORPUS)
        decision = Router().route(req)
        assert decision.cost_tier == CostTier.CLOUD_MID
        assert decision.data_export_blocked is False
        assert decision.data_export_reason == EXPORT_ALLOWED

    def test_unspecified_grade_request_is_blocked(self) -> None:
        req = _cloud_wanting_request()  # data_licenses 미지정 → UNKNOWN
        assert business_cost_tier(req) is CostTier.CLOUD_MID
        decision = Router().route(req)
        assert decision.cost_tier == CostTier.LOCAL
        assert decision.data_export_blocked is True
        assert decision.data_export_reason == EXPORT_UNVERIFIED

    def test_already_local_request_reports_reason_but_not_blocked(self) -> None:
        """free 구독이라 이미 LOCAL — 게이트는 막을 것이 없으므로 blocked=False.

        "정상 응답 200"을 게이트 작동으로 오인하지 않기 위한 구분이다(EOS-59 ②). 사유는
        그대로 남겨 등급 분포는 계속 관측된다.
        """
        req = _cloud_wanting_request(
            student_subscription="free", data_licenses=(LicenseType.AIHUB_OPEN,)
        )
        decision = Router().route(req)
        assert decision.cost_tier == CostTier.LOCAL
        assert decision.data_export_blocked is False
        assert decision.data_export_reason == EXPORT_PROHIBITED

    def test_vision_shortcut_reports_the_grade_without_claiming_a_block(self) -> None:
        """비전 단축 경로도 등급 사유를 남긴다(LOCAL 직행이라 blocked=False)."""
        req = _cloud_wanting_request(requires_vision=True, data_licenses=STUDENT_SUBMITTED)
        decision = Router().route(req)
        assert decision.cost_tier == CostTier.LOCAL
        assert decision.local_family == ModelFamily.VISION
        assert decision.data_export_blocked is False
        assert decision.data_export_reason == EXPORT_PROHIBITED

    def test_business_axis_is_unchanged_by_the_legal_axis(self) -> None:
        """두 가드는 독립이다 — 등급이 무엇이든 비즈니스 축 결정 자체는 같다."""
        for licenses in (SELF_AUTHORED_CORPUS, (LicenseType.AIHUB_OPEN,), DEFAULT_DATA_LICENSES):
            req = _cloud_wanting_request(data_licenses=licenses)
            assert business_cost_tier(req) is CostTier.CLOUD_MID


class TestDecisionInvariant:
    def test_blocked_decision_cannot_be_a_cloud_tier(self) -> None:
        """불변식 5 — 막힌 결정이 클라우드로 나가 있으면 모순이므로 구성 자체를 거부한다."""
        with pytest.raises(ValidationError):
            RoutingDecision(
                cost_tier=CostTier.CLOUD_MID,
                est_latency_ms=3000,
                data_export_blocked=True,
            )

    def test_blocked_local_decision_is_valid(self) -> None:
        """양성 대조 — LOCAL이면 blocked=True가 정상이다(무차별 거부가 아님)."""
        decision = RoutingDecision(
            cost_tier=CostTier.LOCAL,
            local_family=ModelFamily.MATH,
            local_model=LocalModelTier.MID,
            est_latency_ms=3918,
            data_export_blocked=True,
            data_export_reason=EXPORT_PROHIBITED,
        )
        assert decision.data_export_blocked is True


class TestObservationSeat:
    def test_langfuse_fields_carry_the_gate_signal(self) -> None:
        """② "작동한 비율"의 원자료가 기존 관측 좌석으로 흘러나간다(호출부 수정 0)."""
        decision = Router().route(_cloud_wanting_request(data_licenses=(LicenseType.AIHUB_OPEN,)))
        fields = langfuse_fields(decision)
        assert fields["data_export_blocked"] is True
        assert fields["data_export_reason"] == EXPORT_PROHIBITED

    def test_directly_assembled_decision_reports_unjudged_not_allowed(self) -> None:
        """라우터를 안 탄 결정은 사유가 None — '미판정'이지 '허용'이 아니다."""
        decision = RoutingDecision(
            cost_tier=CostTier.LOCAL,
            local_family=ModelFamily.MATH,
            local_model=LocalModelTier.FAST,
            est_latency_ms=1010,
        )
        fields = langfuse_fields(decision)
        assert fields["data_export_reason"] is None
        assert fields["data_export_blocked"] is False


# ══════════════════════════════════════════════════════════════════════
# 스키마 — 보수 기본값과 빈 목록 거부
# ══════════════════════════════════════════════════════════════════════
class TestRoutingRequestGradeField:
    def test_default_is_the_most_conservative_grade(self) -> None:
        req = RoutingRequest(
            task_type="explain",
            difficulty="easy",
            requires_reasoning=False,
            student_subscription="free",
        )
        assert req.data_licenses == DEFAULT_DATA_LICENSES
        assert export_judgment_for(req).blocks_offshore is True

    def test_empty_grade_list_is_rejected(self) -> None:
        """'자료 없음'을 표현할 수 없게 막는다 — 미상은 UNKNOWN으로 *명시*한다."""
        with pytest.raises(ValidationError):
            RoutingRequest(
                task_type="explain",
                difficulty="easy",
                requires_reasoning=False,
                student_subscription="free",
                data_licenses=(),
            )


# ══════════════════════════════════════════════════════════════════════
# 호출부 판정 동결 — 프로파일이 조용히 바뀌면 실패한다
# ══════════════════════════════════════════════════════════════════════
class TestCallSiteGradeProfiles:
    def test_student_submitted_profiles_are_blocked_from_offshore(self) -> None:
        """학생 제출 자료는 국외로 나가지 않는다(권리 모델 USER_GENERATED.export=False)."""
        for profile in (STUDENT_SUBMITTED, STUDENT_SUBMITTED_WITH_CORPUS):
            assert guard_data_export(CostTier.CLOUD_MID, profile) is CostTier.LOCAL

    def test_authoring_and_probe_profiles_are_exportable_today(self) -> None:
        """자체 저작·합성 프로브는 오늘 반출 가능 — 클라우드 계측 경로가 이 등급에 의존한다.

        코퍼스에 AIHub 유래가 들어와 `SELF_AUTHORED_CORPUS`가 바뀌면 이 단언이 먼저 깨진다 —
        그 순간이 "저작 경로 전체가 로컬로 잠긴다"는 사실을 사람에게 알리는 지점이다.
        """
        assert export_judgment(SELF_AUTHORED_CORPUS).reason == EXPORT_ALLOWED
        assert export_judgment(SYNTHETIC_PROBE).reason == EXPORT_ALLOWED

    def test_ocr_recognizer_declares_student_material(self) -> None:
        """L5 OCR은 학생 손글씨를 다룬다 — 등급이 그 사실을 말해야 한다."""
        from whymath_backend.l5.ocr import recognize as ocr_recognize

        source = ocr_recognize.__file__
        assert source is not None
        with open(source, encoding="utf-8") as handle:
            body = handle.read()
        assert "data_licenses=STUDENT_SUBMITTED" in body

    def test_cloud_smoke_paths_declare_exportable_material(self) -> None:
        """클라우드 계측 경로가 게이트에 막히면 클라우드 비용을 영영 못 잰다 — 등급 동결."""
        from whymath_backend.ops.cost_probe import _cloud_mid_request
        from whymath_backend.ops.live_preflight import _cloud_mid_smoke_request

        for req in (_cloud_mid_request("diagnose", "hard"), _cloud_mid_smoke_request()):
            assert export_judgment_for(req).reason == EXPORT_ALLOWED
            assert Router().route(req).cost_tier == CostTier.CLOUD_MID

    def test_judge_seam_declares_student_statement(self) -> None:
        """judge 프롬프트는 `[학생 진술]`을 싣는다 — 등급이 그 사실을 반영해야 한다."""
        from whymath_backend.l4.misconception.judge_seam import _judge_routing_request

        assert export_judgment_for(_judge_routing_request()).reason == EXPORT_PROHIBITED
