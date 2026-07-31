"""SEC-11 — 시크릿 하드코딩 저장소 스캔.

`dev_constitution.md:193`가 "시크릿 형식 자가검증(§8) — CLAUDE.md 런북 규칙으로 존재.
**코드 테스트화는 남은 선택지**"라고 자백한 항목을 이 테스트가 상환한다. CLAUDE.md 절대
금기 "API 키·시크릿을 코드에 하드코딩 금지"를 사람 기억이 아니라 기계 검사로 강제한다.

무엇을 스캔하나
--------------
`src/backend/whymath_backend/`(프로덕션 코드만) 안의 모든 `.py` 파일을
`ops/log_scrubber.SECRET_LITERAL_PATTERNS`(sk-/pk- API 키·`Bearer <token>`·JWT
3-세그먼트)로 검사한다. 이 패턴은 로그 스크러버가 마스킹하는 자격증명-형태 패턴과 **동일
정의**를 재사용한다(단일 진실 원천 — "시크릿의 모양"을 두 곳에서 따로 정의하면 표류한다).
PII 형태(이메일·전화)는 스캔에서 **의도적으로 제외**한다 — 이메일은 시크릿이 아니라 코드
주석·docstring에 정당하게 등장할 수 있어(예: 라이선스 헤더 연락처) 하드코딩 스캔에 넣으면
오탐이 통제 불가능해진다. `log_scrubber.py`가 `CREDENTIAL_SHAPE_PATTERNS`/`_PII_SHAPE_PATTERNS`로
이미 분리해 둔 경계를 그대로 따른다.

오탐 방지 (false-positive) — 스캔 범위 설계로 해결, 문자열 예외처리 최소화
----------------------------------------------------------------------
- **`tests/`는 스캔 대상 밖** — 이 태스크 자신의 판별력 테스트(`test_log_scrubber.py`)가
  의도적으로 가짜 시크릿 모양 문자열(`sk-testkey…`·`sk-ant-api03-leakedkey0001` 등)을
  픽스처로 담고 있다. `src/backend/whymath_backend/`(배포되는 프로덕션 코드)만 스캔해 그
  문제를 *구조적으로* 피한다 — 테스트 픽스처는 배포 산출물이 아니므로 대상이 아니다.
- **docstring의 설명용 표기**(`sk-...`·`sk-ant-...` — 말줄임표 `...`)는 패턴이 요구하는
  최소 6문자 연속 `[A-Za-z0-9_-]`를 만족하지 않아 애초에 매치되지 않는다(정규식 설계
  자체가 오탐을 피한다 — 실측: 이 태스크 착수 시점 `config.py`·`log_scrubber.py`의 `sk-...`
  표기 3곳 모두 매치 0건, 아래 baseline 테스트가 그 상태를 동결한다).
- 그래도 향후 진짜 예외(정당한 이유로 시크릿 모양 리터럴을 남겨야 하는 경우)가 생기면
  `_ALLOWLIST`(상대경로 → 사유)에 등재한다. **빈 사유는 무효**(OPS-06·OPS-08 선례 —
  CLAUDE.md "의도적 미배선은 사유 필수").

변별력
------
`test_scan_detects_planted_violation`이 임시 디렉터리에 진짜 시크릿 모양 문자열을 심어
스캐너가 *실제로* 검출하는지 확인한다 — "오탐 회피를 위해 스캔 범위를 좁혔더니 아무것도
못 잡는 스캐너가 됐다"는 실패 모드를 배제한다(CLAUDE.md "변별력 없는 검증 스텝 금지").
"""

from __future__ import annotations

from pathlib import Path

import pytest

from whymath_backend.ops.log_scrubber import SECRET_LITERAL_PATTERNS

_REPO_ROOT = Path(__file__).resolve().parents[3]
_SCAN_ROOT = _REPO_ROOT / "src" / "backend" / "whymath_backend"

# 의도적 예외 — 저장소 루트 기준 상대경로(POSIX) → 사유. 빈 사유는 무효(아래 assert).
_ALLOWLIST: dict[str, str] = {}


def _iter_python_files(root: Path) -> list[Path]:
    return sorted(p for p in root.rglob("*.py") if "__pycache__" not in p.parts)


def _find_violations(
    root: Path, *, allowlist_relative_to: Path | None = None
) -> list[tuple[Path, int, str]]:
    """`root` 아래 `.py` 전수를 스캔해 (파일, 줄번호, 매치문자열) 위반 목록을 돌려준다.

    `allowlist_relative_to`가 주어지면(프로덕션 스캔 경로) `_ALLOWLIST` 검사를 적용한다.
    플랜티드-위반 테스트(임시 디렉터리 스캔)는 `None`을 넘겨 allowlist 로직을 건너뛴다 —
    임시 경로는 저장소 상대경로로 환산할 수 없다.
    """
    violations: list[tuple[Path, int, str]] = []
    for path in _iter_python_files(root):
        if allowlist_relative_to is not None:
            rel = path.relative_to(allowlist_relative_to).as_posix()
            if rel in _ALLOWLIST:
                reason = _ALLOWLIST[rel]
                if not reason.strip():
                    raise AssertionError(f"allowlist 항목 '{rel}'의 사유가 비어 있음(무효)")
                continue
        text = path.read_text(encoding="utf-8")
        for lineno, line in enumerate(text.splitlines(), start=1):
            for pattern in SECRET_LITERAL_PATTERNS:
                match = pattern.search(line)
                if match:
                    violations.append((path, lineno, match.group(0)))
    return violations


def test_no_hardcoded_secret_shaped_literals_in_backend_source() -> None:
    """`src/backend/whymath_backend/`에 sk-/pk- API 키·Bearer 토큰·JWT 모양 리터럴이 없다."""
    assert _SCAN_ROOT.is_dir(), f"스캔 대상 디렉터리 없음: {_SCAN_ROOT}"
    violations = _find_violations(_SCAN_ROOT, allowlist_relative_to=_REPO_ROOT)
    if violations:
        detail = "\n".join(
            f"  {path.relative_to(_REPO_ROOT)}:{lineno} — {snippet!r}"
            for path, lineno, snippet in violations
        )
        pytest.fail(
            f"시크릿 형태 하드코딩 후보 {len(violations)}건 발견:\n{detail}\n"
            "실제 시크릿이면 즉시 회수·재발급하고 env-only(SecretStr)로 옮기세요. "
            "의도된 예시/픽스처라면 사유와 함께 이 테스트 파일의 _ALLOWLIST에 등재하세요."
        )


def test_scan_detects_planted_violation(tmp_path: Path) -> None:
    """변별력 — 스캐너가 항상 통과하는 위장 검사가 아님을 실제 위반을 심어 증명한다.

    오탐 방지를 위해 스캔 범위를 좁힌 나머지("`tests/`는 범위 밖") 스캐너 로직 자체가
    무력해지지 않았는지 확인 — 임시 디렉터리(스캔 범위 규칙과 무관한 장소)에 진짜 시크릿
    모양 문자열을 심고 검출을 확인한다.
    """
    planted = tmp_path / "leaky_module.py"
    planted.write_text(
        'ANTHROPIC_KEY = "sk-ant-api03-thisisadefinitelyfakeplantedkey000"\n',
        encoding="utf-8",
    )
    violations = _find_violations(planted.parent)
    assert violations, "심어둔 위반을 스캐너가 못 잡음 — 변별력 없음(오탐 회피가 과함)"
    assert violations[0][0] == planted
    assert "sk-ant-api03-thisisadefinitelyfakeplantedkey000" in violations[0][2]


def test_docstring_style_ellipsis_examples_do_not_false_positive(
    tmp_path: Path,
) -> None:
    """`sk-...`처럼 말줄임표로 예시를 든 docstring은 오탐을 내지 않는다(설계 의도 회귀)."""
    benign = tmp_path / "benign_module.py"
    benign.write_text(
        '"""Anthropic API 키(sk-ant-...). Langfuse 시크릿키(sk-...)."""\n',
        encoding="utf-8",
    )
    assert _find_violations(benign.parent) == []
