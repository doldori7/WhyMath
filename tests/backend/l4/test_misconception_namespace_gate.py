"""오개념 kebab-id 과목 네임스페이스 게이트(S3) — 예약 접두 침범 금지 동결.

정본: `docs/architecture/subject_expansion_readiness.md` §5. 규약 — 비수학 오개념 kebab-id는
과목 접두(`phys-`·`chem-`·`bio-`·`earth-`) 필수, 수학 기존 카탈로그는 무접두 그대로(재명명
금지). 이 게이트는 그 규약의 *수학 측 절반*만 동결한다: 수학 카탈로그가 예약 접두를 선점하면
미래 물리 오개념과 id 충돌이 되므로 차단. (역방향 — 물리 오개념이 무접두로 들어오는 것은
물리 시드 슬라이스의 게이트 소관. 오개념 `subject` *필드*는 3중 표현 canonical 수렴 트랙
소관 — §8 보류 대장.)
"""

from __future__ import annotations

import re

import pytest
from whymath_backend.l4.misconception.catalog import CATALOG
from whymath_backend.l4.misconception.models import Misconception

# §5 예약 과목 접두 — 물리·화학·생명과학·지구과학.
_RESERVED_SUBJECT_PREFIXES: tuple[str, ...] = ("phys-", "chem-", "bio-", "earth-")

# kebab-id 형식 — 소문자·숫자 토큰을 하이픈으로 연결(선행/후행/연속 하이픈 불가).
_KEBAB_PATTERN = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")


class TestMisconceptionNamespaceGate:
    """수학 오개념 카탈로그의 과목 네임스페이스 규약 동결."""

    @pytest.mark.parametrize("misconception", CATALOG, ids=lambda m: m.id)
    def test_math_ids_do_not_use_reserved_subject_prefixes(
        self, misconception: Misconception
    ) -> None:
        """수학 항목이 예약 과목 접두를 선점하면 미래 과목 확장 시 id 충돌 — 차단."""
        assert not misconception.id.startswith(_RESERVED_SUBJECT_PREFIXES), (
            f"수학 오개념 {misconception.id!r}가 예약 과목 접두를 침범 — "
            "비수학 전용 네임스페이스다(readiness doc §5)."
        )

    @pytest.mark.parametrize("misconception", CATALOG, ids=lambda m: m.id)
    def test_ids_conform_kebab_format(self, misconception: Misconception) -> None:
        """kebab 형식(소문자·숫자·단일 하이픈) 준수 — URL 안전·접두 규약의 전제."""
        assert _KEBAB_PATTERN.match(misconception.id), f"kebab-id 형식 위반: {misconception.id!r}"
