"""거버넌스 동결 — 학년축은 오버레이 파라미터, 구조 분기 아님 (W0 — 학년축 최단경로 계획 §2.1).

CLAUDE.md 8대 구조 원칙 ⑤(Curriculum은 Overlay)와
`docs/strategy/grade_axis_mvp_shortest_path_v1.md` §2.1의 답을 코드로 동결한다: L2(학습자
모델)·L3(생성·검증)·L4(교수학 엔진)는 `school_level`/`grade_band`/`grade_band_hint` 값으로
*제어 흐름을 분기*하지 않는다 — 학년은 항상 프롬프트 인자·필터 값으로만 흘러야 한다(구조
자체가 갈라지면 안 됨). 4축(초·중·고·대학)으로 콘텐츠를 채울 때 L2~L4에 축별 `if` 분기가
스며드는 것을 이 테스트가 조기에 잡는다.

**L1은 스코프 밖**이다 — L1(데이터 기반)은 커리큘럼 Overlay 적재기가 본업이라
`school_level`/`grade_band`로 코퍼스를 필터·매핑하는 것이 정상 설계다(예:
`l1/curriculum/curriculum_loader.py`의 `atom.get("school_level") != "대학"` 필터). 여기서
막는 것은 *비교 연산자로 갈라지는 제어 흐름*(`==`/`!=`)이지, `.get(grade_band)` 같은 dict
기반 오버레이 매핑(파라미터 룩업 — 원칙이 권장하는 패턴)이 아니다 — 정규식이 비교 연산자만
잡아 dict lookup은 자연히 통과한다.

hermetic: DB 불요(소스 스캔만). `test_embedding_namespace_governance.py`(cosine_distance
allowlist)와 동일한 rglob + 문자열/정규식 스캔 패턴.
"""

from __future__ import annotations

import re
from pathlib import Path

# 구조 분기 금지 대상 값 3종 — 학년축 어휘(L1 커리큘럼 오버레이가 쓰는 필드명 그대로).
# `grade`(정수 힌트)는 대상이 아니다 — `if grade is not None:` 류는 오버레이 파라미터의
# 정상 사용(prompt_assembler.py 선례)이라 의도적으로 제외한다.
_BANNED_FIELDS = ("school_level", "grade_band_hint", "grade_band")

# 비교 연산자로 분기하는 패턴만 잡는다 — `X == "..."`·`X != "..."`(dict `.get(X)`/`X in {...}`
# 매핑 룩업은 오버레이 파라미터 패턴이라 통과시킨다).
_BRANCH_PATTERN = re.compile(r"\b(" + "|".join(_BANNED_FIELDS) + r")\s*(==|!=)")

# 스캔 대상 — L2(학습자 모델)·L3(생성·검증)·L4(교수학 엔진)만. L1(데이터 기반)은 커리큘럼
# Overlay 적재기 본업이라 스코프 밖(모듈 docstring). L5~L7은 이 저장소의 백엔드 패키지 밖
# (Flutter/별도 웹) 또는 아직 이 축 배선이 없어 후속 슬라이스 대상.
_SCANNED_LAYERS = ("l2", "l3", "l4")


def _iter_layer_files(package_root: Path) -> list[Path]:
    files: list[Path] = []
    for layer in _SCANNED_LAYERS:
        layer_root = package_root / layer
        if not layer_root.is_dir():
            continue
        files.extend(sorted(layer_root.rglob("*.py")))
    return files


def test_no_grade_axis_structural_branching_in_l2_l3_l4() -> None:
    """L2~L4 소스에 `school_level`/`grade_band`/`grade_band_hint` 비교 분기가 없어야 한다.

    위반이 발견되면 그 파일·라인을 보고한다 — 조용한 실패 금지(CLAUDE.md 침묵 실패 금지 원칙과
    동형: 위반 즉시 어디서 났는지 드러난다). 새 축(초·중·고·대학) 콘텐츠 확장(W2)이 L2~L4에
    학년별 `if` 분기를 심는 순간 이 테스트가 CI에서 즉시 red가 된다.
    """
    import whymath_backend

    package_root = Path(whymath_backend.__file__).parent
    violations: list[str] = []
    for path in _iter_layer_files(package_root):
        text = path.read_text(encoding="utf-8")
        for lineno, line in enumerate(text.splitlines(), start=1):
            if _BRANCH_PATTERN.search(line):
                rel = path.relative_to(package_root).as_posix()
                violations.append(f"{rel}:{lineno}: {line.strip()}")

    assert not violations, (
        "L2~L4에 학년축 구조 분기가 발견됐습니다(school_level/grade_band/grade_band_hint를 "
        "==/!=로 비교) — 학년축은 오버레이 파라미터여야지 제어 흐름을 갈라선 안 됩니다"
        "(CLAUDE.md 8대 구조 원칙 ⑤ Curriculum은 Overlay). 발견:\n"
        + "\n".join(violations)
        + "\n\ndict 기반 매핑(`_MAP.get(grade_band)`)으로 바꾸거나, 정말 구조 분기가 필요하다면 "
        "이 테스트와 grade_axis_mvp_shortest_path_v1.md §2.1을 함께 개정하라."
    )


def test_banned_field_scan_pattern_actually_detects_violations() -> None:
    """변별력 검증(CLAUDE.md "변별력 없는 검증 스텝 금지") — 패턴이 실제 위반을 잡는지 자가검증.

    `_BRANCH_PATTERN`이 아무것도 못 잡는 죽은 정규식이면 위 테스트는 상시 그린으로 위장한다.
    합성 위반 3종(값 3개 × == 1종 대표)을 실제로 매치하는지 여기서 못 박는다.
    """
    samples = [
        'if school_level == "대학":',
        "if grade_band != '고등':",
        'level = "심화" if grade_band_hint == "고등학교" else "기본"',
    ]
    for sample in samples:
        assert _BRANCH_PATTERN.search(sample), f"패턴이 위반을 못 잡음(변별력 없음): {sample!r}"

    # 정상 오버레이 룩업(dict.get — `==`/`!=` 자체가 없음)은 매치하지 않아야(오탐 없음).
    safe = "required_depth = _GRADE_BAND_TO_REQUIRED_DEPTH.get(grade_band)"
    assert not _BRANCH_PATTERN.search(safe)
