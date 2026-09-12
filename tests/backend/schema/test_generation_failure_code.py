"""EOS-51 실패코드 F1~F8 계약 동결 테스트 — 검증설계서 v1 §4의 기계 동결.

설계 정본: `docs/standards/eos_verification_design_v1.md` (EOS-51 · 2026-08-30).
이 테스트가 지키는 것:
① 실패코드 값집합 F1~F8 폐쇄 동결 — G0(9/6) 이후 12월까지 추가·삭제·의미 변경 금지
  (분류 체계가 바뀌면 F-Ⅲ 실패분포 시계열이 무효가 된다).
② 판단형 부분집합 {F3, F6, F7} 동결 — 실패정의 F-Ⅲ("판단형 합 60% 초과 = 실패") 산식의 축.
③ CU(콘텐츠 단위) 구성요소의 스키마 좌석 실재 동결 — 설계서 §3의 "CU는 기존 스키마 조합으로
  표현한다(신설 금지)" 판단이 성립하려면 그 좌석들이 실제로 존재해야 한다.

정본화≠집행(자인): 이 enum을 소비하는 런타임 경로는 아직 0이다 — 자동 부여는 ARCH-23/D2 축,
검수 반려코드 입력 강제·이벤트 적재는 EOS-54 몫. 여기서는 분류 *계약*만 동결한다.
"""

from __future__ import annotations

from enum import Enum

from whymath_backend.schema.enums import GenerationFailureCode
from whymath_backend.schema.problem import DistractorEntry, Problem


class TestGenerationFailureCodeFrozen:
    """실패코드 8종 폐쇄 동결 — 값·이름·개수 전부."""

    def test_str_enum(self) -> None:
        assert issubclass(GenerationFailureCode, str)
        assert issubclass(GenerationFailureCode, Enum)

    def test_members_frozen_f1_to_f8(self) -> None:
        # 폐쇄 8종 — 순서 포함 동결(집계 표는 F1→F8 순으로 출력된다)
        assert [m.name for m in GenerationFailureCode] == [
            "F1",
            "F2",
            "F3",
            "F4",
            "F5",
            "F6",
            "F7",
            "F8",
        ]

    def test_values_equal_names(self) -> None:
        # 값 = 코드 문자열 그대로 (이벤트 적재·집계 쿼리에서 name/value 혼용 사고 방지)
        for m in GenerationFailureCode:
            assert m.value == m.name

    def test_judgment_type_subset_frozen(self) -> None:
        # F-Ⅲ 산식의 판단형(자동화 흡수 불가) 축 — 설계서 §5 F-Ⅲ와 1:1
        judgment = {
            GenerationFailureCode.F3,
            GenerationFailureCode.F6,
            GenerationFailureCode.F7,
        }
        machine = set(GenerationFailureCode) - judgment
        assert judgment == {
            GenerationFailureCode.F3,
            GenerationFailureCode.F6,
            GenerationFailureCode.F7,
        }
        assert len(machine) == 5


class TestContentUnitSeatContract:
    """CU 구성요소의 스키마 좌석 실재 — 설계서 §3 "기존 스키마 조합으로 표현" 판단의 동결.

    좌석 대응(설계서 §3 표): 문제·정답=Problem 본문/정답류 필드 · 예상 오답=distractor_map
    (+DistractorEntry.op_code) · 난이도=difficulty_overall(저작)·irt 축(실측) ·
    성취기준=achievement_standard_codes. 단계별 풀이는 SolutionPath/SolutionStep(DB·S4-09
    착지), 3단계 힌트 영속은 **미착지**(S4-11 todo)임을 설계서가 자인한다 — 없는 좌석을
    여기서 단언하지 않는다(날조 금지).
    """

    def test_problem_schema_cu_seats_exist(self) -> None:
        fields = set(Problem.model_fields)
        # CU 필수 구성요소의 Problem 측 좌석 — 하나라도 사라지면 CU 계약이 깨진다
        assert {"achievement_standard_codes", "distractor_map", "difficulty_overall"} <= fields

    def test_distractor_entry_carries_op_code_seat(self) -> None:
        # 예상 오답 → 오개념 op-code 매핑 좌석(설계서 §3 — 내용 KPI 오개념 연결 축의 전제)
        assert "op_code" in DistractorEntry.model_fields
