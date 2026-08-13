"""`/study`·`/outcome`이 `evidence_event.k_type`에 넘기는 값이 **PG enum 라벨**인지 동결한다.

**사고 경위**(SEC-24 회수 중 CI 실측 · 2026-08-11): `api/study.py`가 세 곳에서
`k_type=str(objective.k_type)`를 넘기고 있었다. `KnowledgeType`은 `class KnowledgeType(str, Enum)`
이라 얼핏 문자열처럼 보이지만 `str(멤버)`는 값이 아니라 **`"KnowledgeType.CONCEPT"`**
(`Enum.__str__`)를 낸다. `_pg_enum`이 `values_callable`로 PG 라벨을 enum *값*(`CONCEPT`)으로
잡아 두었으므로 그 문자열은 라벨 집합 밖이고, 실 PG INSERT가

    invalid input value for enum knowledge_type: "KnowledgeType.CONCEPT"

로 터진다.

**왜 이 파일이 필요한가 — 세 검출기가 전부 놓쳤다**:
  · 전체 백엔드 스위트 9,696건: green (fake 세션이 바인딩 값을 DB로 왕복시키지 않는다)
  · `mypy --strict`: green (`str(Enum)`의 타입은 `str`이라 타입 오류가 아니다)
  · `ruff`: green (문법·스타일 위반이 아니다)
잡은 것은 **CI 실 PG 통합 잡 하나뿐**이었다. PG 없는 개발 컨테이너에서도 같은 회귀가 즉시
드러나게 하는 것이 이 파일의 목적이다.

**한계(정직 표기)**: 여기서 동결하는 것은 *소스 표현식*과 *라벨 집합*이지 라우터의 런타임
동작이 아니다. 라우터를 실제로 태워 바인딩 값을 검사하는 축은 CI 실 PG 잡
(`api/test_study_integration.py::test_outcome_ownership_http_on_live_pg`)이 계속 담당한다 —
이 파일은 그 느린 검출기보다 **앞에서 싸게 잡는 것**이지 대체가 아니다.
"""

from __future__ import annotations

from pathlib import Path

from whymath_backend.schema.enums import KnowledgeType

#: PG enum `knowledge_type`의 실제 라벨 집합 — `_pg_enum(..., values_callable=...)`이 enum
#: *값*을 라벨로 쓰므로 값 집합이 곧 DB가 받아들이는 문자열 집합이다.
_PG_LABELS: frozenset[str] = frozenset(m.value for m in KnowledgeType)

_STUDY_SOURCE = Path(__file__).resolve().parents[3] / "src/backend/whymath_backend/api/study.py"


class TestKnowledgeTypeLabelContract:
    """enum → DB 라벨 변환 계약 — 어떤 표현이 라벨이고 어떤 것이 아닌가."""

    def test_str_of_member_is_not_a_pg_label(self) -> None:
        """`str(멤버)`는 라벨이 **아니다** — 이 사실이 결함의 뿌리였다.

        이 단언이 깨지면(예: enum이 `__str__`을 재정의) 이 파일의 전제가 사라지므로,
        아래 소스 동결도 함께 재검토해야 한다.
        """
        assert str(KnowledgeType.CONCEPT) == "KnowledgeType.CONCEPT"
        assert str(KnowledgeType.CONCEPT) not in _PG_LABELS

    def test_value_of_member_is_a_pg_label(self) -> None:
        """`.value`는 7종 전부 라벨이다 — 올바른 변환 경로."""
        for member in KnowledgeType:
            assert member.value in _PG_LABELS


class TestStudySourceFreeze:
    """`api/study.py`의 변환 표현식 동결.

    **왜 소스 텍스트를 검사하는가**: 이 결함은 타입 검사기를 통과한다(`str(Enum)`은 `str`).
    fake 세션 단위 테스트도 통과한다(DB 왕복이 없다). PG 없는 환경에서 기계가 볼 수 있는
    지점이 소스 표현식뿐이라 여기서 못 박는다. 변환 방식을 바꿔야 하면 이 테스트를 함께
    고치되, 위 라벨 집합 계약은 유지한다.
    """

    def test_does_not_use_str_of_enum(self) -> None:
        """`str(objective.k_type)` 패턴이 되살아나면 실패한다(회귀의 정확한 형태)."""
        text = _STUDY_SOURCE.read_text(encoding="utf-8")
        assert "str(objective.k_type)" not in text, (
            "`str(objective.k_type)`는 'KnowledgeType.CONCEPT'를 만들어 PG enum INSERT를 "
            "깨뜨린다(2026-08-11 실 PG 실측). `KnowledgeType(objective.k_type).value`를 쓸 것."
        )

    def test_all_three_call_sites_pass_value(self) -> None:
        """세 호출부(`supply`·`treatment`·`outcome`)가 전부 `.value`를 넘긴다.

        개수를 고정하는 이유: 하나만 고치고 나머지를 놓치는 것이 이 결함의 실제 형태였다
        (세 곳이 같은 표현식을 복사하고 있었다).
        """
        text = _STUDY_SOURCE.read_text(encoding="utf-8")
        assert text.count("k_type=KnowledgeType(objective.k_type).value") == 3
