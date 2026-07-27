"""[OPS-09] 무작위 순서 seed 노출 훅의 **배선 실재성** 동결.

왜 이 테스트가 있는가
--------------------
`pytest-randomly`를 상시 켠 이상, 무작위 순서로 실패했을 때 **어떤 순서였는지 재현**할 수
있어야 한다. 재현할 수 없는 빨강은 고칠 수 없는 빨강이고, 그러면 무작위화는 이득보다 손해가
된다(도입 전제 붕괴). pytest-randomly의 기본 헤더는 `-q`에서 출력되지 않는데 이 저장소 CI는
전 스위트를 `-q`로 돌리므로, conftest의 `pytest_configure` 훅이 seed를 직접 찍는다.

**중복이 존재하는 이유**(이 테스트가 지키는 것):
  - `conftest.py`(레포 루트) — `tests/infra`·`tests/harness`처럼 **레포 루트에서** 실행되는
    스위트를 덮는다.
  - `tests/backend/conftest.py` — backend 스위트는 CI에서 `cd src/backend && pytest -c
    pyproject.toml ../../tests/backend`로 돌아 **rootdir이 `src/backend`**가 된다. 이때 레포
    루트 conftest는 confcutdir 밖으로 밀려나 로드되지 않는다(2026-07-27 실측: 루트에만 뒀을 때
    `--collect-only`에서 seed 줄 0건). 하필 순서 의존 사고가 실제로 난 것이 이 스위트다.

한쪽만 남거나 두 사본이 어긋나면 *그 실행 맥락에서만* 조용히 재현 경로가 사라진다 — 평상시엔
아무 신호도 없다가 정작 빨강이 났을 때 발견된다. 그래서 기계가 대조한다.

검증 계약
--------
① 두 conftest 모두 훅을 갖는다 (한쪽 소실 차단)
② 두 사본이 **같은 seed 속성·같은 출력 마커**를 쓴다 (드리프트 차단)
③ 두 사본 모두 `trylast=True`를 단다 — 없으면 pytest-randomly가 seed를 확정하기 *전*에 돌아
   재현 불가능한 문자열 `"default"`를 찍는다(실측된 함정)
④ 파서가 위장하지 않는다 — 파일이 없거나 훅을 못 찾으면 "위반 0 통과"가 아니라 **실패**
"""

from __future__ import annotations

import re
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]

# seed 훅이 있어야 하는 conftest들 → 그 파일이 덮는 실행 맥락(실패 메시지용)
_CONFTESTS: dict[str, str] = {
    "conftest.py": "레포 루트에서 실행되는 스위트(tests/infra·tests/harness)",
    "tests/backend/conftest.py": (
        "backend 스위트(rootdir=src/backend라 루트 conftest가 confcutdir 밖)"
    ),
}

# 두 사본이 공유해야 하는 계약 조각
_SEED_ATTR = "randomly_seed"
_OUTPUT_MARKER = "[order] randomly-seed="
_TRYLAST = "@pytest.hookimpl(trylast=True)"


def _read(rel: str) -> str:
    path = _REPO_ROOT / rel
    if not path.is_file():
        raise AssertionError(
            f"{rel} 이(가) 없다 — seed 노출 훅의 배선을 확인할 수 없다. "
            f"이 파일은 {_CONFTESTS[rel]}을(를) 덮는다."
        )
    text = path.read_text(encoding="utf-8")
    if not text.strip():
        raise AssertionError(f"{rel} 이(가) 비어 있다.")
    return text


def _hook_block(rel: str) -> str:
    """`pytest_configure` 훅 본문을 잘라낸다. 못 찾으면 실패(위장 차단)."""
    text = _read(rel)
    match = re.search(r"def pytest_configure\(.*?\n(?:.*\n)*?", text)
    if match is None:
        raise AssertionError(
            f"{rel} 에 `pytest_configure` 훅이 없다 — {_CONFTESTS[rel]}에서 무작위 순서 "
            "seed가 찍히지 않아 실패 재현이 불가능해진다."
        )
    return text[match.start() :]


def test_both_conftests_declare_the_seed_hook() -> None:
    """계약 ① — 한쪽이 사라지면 그 실행 맥락에서 조용히 재현 경로가 없어진다."""
    missing = [rel for rel in _CONFTESTS if "def pytest_configure(" not in _read(rel)]
    assert not missing, "seed 노출 훅이 없는 conftest: " + ", ".join(
        f"{rel} ({_CONFTESTS[rel]})" for rel in missing
    )


def test_both_copies_share_the_same_contract() -> None:
    """계약 ② — 두 사본이 같은 속성·같은 마커를 써야 로그 형식이 갈리지 않는다."""
    for rel in _CONFTESTS:
        block = _hook_block(rel)
        assert _SEED_ATTR in block, f"{rel}: seed 속성 `{_SEED_ATTR}` 참조가 없다"
        assert _OUTPUT_MARKER in block, f"{rel}: 출력 마커 `{_OUTPUT_MARKER}` 가 없다"


def test_both_copies_pin_trylast() -> None:
    """계약 ③ — trylast가 없으면 확정 전 값 "default"를 찍어 재현에 쓸 수 없다.

    이건 가설이 아니라 실측된 함정이다(2026-07-27 첫 구현이 정확히 이 상태였다).
    """
    for rel in _CONFTESTS:
        text = _read(rel)
        idx = text.find("def pytest_configure(")
        assert idx != -1, f"{rel}: pytest_configure 훅 부재"
        # 훅 정의 바로 앞 200자 안에 데코레이터가 있어야 한다
        preceding = text[max(0, idx - 200) : idx]
        assert _TRYLAST in preceding, (
            f"{rel}: `pytest_configure`에 {_TRYLAST} 가 붙어 있지 않다 — "
            'pytest-randomly가 seed를 확정하기 전에 돌아 재현 불가능한 "default"를 찍는다.'
        )


def test_parser_fails_loudly_on_missing_file() -> None:
    """계약 ④ — 파일 부재가 조용한 통과가 되면 이 테스트 묶음 전체가 위장이 된다."""
    import pytest as _pytest

    _CONFTESTS["tests/__nonexistent_probe__/conftest.py"] = "존재하지 않는 경로(파서 검증용)"
    try:
        with _pytest.raises(AssertionError, match="없다"):
            _read("tests/__nonexistent_probe__/conftest.py")
    finally:
        del _CONFTESTS["tests/__nonexistent_probe__/conftest.py"]
