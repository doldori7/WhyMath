"""`scripts/ops/probe_prod_schema_revision.sql` 계약 동결 (hermetic — 실 DB 불요).

`G-operator-seat-first-grant`: whymath-pg의 `alembic_version`이 이 저장소의 체인에 없는
`d6e7f8a9b0c1`이라 alembic이 아예 동작하지 않는다(`Can't locate revision`·exit 255 실측).
그래서 stamp 대상은 **버전 테이블이 아니라 스키마 실물**에서 정해야 한다(CLAUDE.md
"간접 신호를 성공 판정으로 쓰는 안내 금지"). 이 프로브가 그 측정이고, 이 테스트가
프로브를 체인에 동결한다.

동결하는 계약:
  ① **ASCII 전용** — 한국어 Windows(cp949) 호스트에서 psql로 파이프된다. 비ASCII 1바이트가
     운영자 머신에서 파일을 깨뜨린다(`test_backup_script.py` ① 동형).
  ② **읽기 전용** — prod DB에 그대로 실행되므로 DDL/DML이 한 줄도 없어야 한다
     (유일한 예외 = 세션 한정 `CREATE TEMP VIEW`).
  ③ **체인 동기화** — 프로브가 검사하는 리비전이 실제 마이그레이션 체인에 존재하고,
     선언한 `seq`가 체인 위치와 일치하며, **체인 꼬리를 빠짐없이 덮는다**. 마이그레이션이
     추가되면 이 테스트가 빨개져 프로브 갱신을 강제한다 — 갱신 없이 두면 프로브는
     "pending 0"이라는 *틀린 통과*를 낸다(측정이 아니라 위장).
  ④ **head 일치** — 프로브의 마지막 리비전 = `schema_version.EXPECTED_ALEMBIC_HEAD`.
  ⑤ **판정자 실재** — 마지막 SELECT가 `stamp_target`·`pending_count`·`present_after_gap`
     세 판정치를 낸다. 특히 `present_after_gap`은 "뒤쪽 리비전 혼입" 탐지기라 빠지면
     stamp가 위험해진다.

한계(명시): ③의 판별자(테이블·컬럼) 검증은 해당 마이그레이션 파일 *텍스트*에 그 이름이
등장하는지까지만 본다. `upgrade()` AST를 해석하지는 않는다 — `a2b3c4d5e6f1`처럼 컬럼명을
모듈 상수 튜플에서 루프로 돌리는 형태가 있어 정적 해석이 일반적으로 성립하지 않기 때문이다.
잘못된 리비전에 판별자를 붙이는 실수는 잡히지만, 같은 파일 안의 엉뚱한 이름을 고르는
실수는 잡히지 않는다.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[2]
_PROBE = _ROOT / "scripts" / "ops" / "probe_prod_schema_revision.sql"
_VERSIONS = _ROOT / "src" / "backend" / "alembic" / "versions"
_SCHEMA_VERSION = _ROOT / "src" / "backend" / "whymath_backend" / "db" / "schema_version.py"

# 체인의 이 위치부터는 프로브가 **전부** 덮어야 한다. 2026-08-11 실측에서 whymath-pg가
# 그 부근(`concept_visual_style` 있음 / `user_profile.role` 없음)에 있었기 때문이고,
# 그 앞은 앵커 2개(63·64)로만 확인한다 — 앞쪽까지 전수로 덮으려면 뒤 리비전이 이미
# 지워버린 객체를 판별자로 써야 해서 거짓 음성이 난다.
_TAIL_START_SEQ = 66
# 예외: seq 65(`f1a2b3c4d5e7`)는 컬럼 *삭제* 마이그레이션이라 "있으면 적용됨"이 성립하는
# 양(positive) 판별자가 없다. 부재는 미적용과 구분되지 않으므로 프로브에서 제외한다.
_NO_POSITIVE_DISCRIMINATOR = {"f1a2b3c4d5e7"}


def _probe_text() -> str:
    """ASCII로 읽는다 — ①이 깨지면 여기서 즉시 실패(이중 방어)."""
    return _PROBE.read_text(encoding="ascii")


def _probe_body() -> str:
    """주석(`--`)과 psql 메타명령(`\\echo`)을 제거한 실행 SQL만 돌려준다."""
    lines = []
    for line in _probe_text().splitlines():
        stripped = line.lstrip()
        if stripped.startswith("--") or stripped.startswith("\\"):
            continue
        lines.append(line.split("--")[0] if "--" in line else line)
    return "\n".join(lines)


def _chain() -> list[str]:
    """마이그레이션 파일에서 선형 체인을 복원해 리비전을 순서대로 돌려준다."""
    revs: dict[str, str] = {}
    for path in sorted(_VERSIONS.glob("*.py")):
        text = path.read_text(encoding="utf-8")
        rev = re.search(r"^revision[^=\n]*=\s*[\"']([^\"']+)", text, re.M)
        down = re.search(r"^down_revision[^=\n]*=\s*(.+)$", text, re.M)
        assert rev and down, f"리비전 헤더를 읽지 못했습니다: {path.name}"
        raw = down.group(1).strip()
        quoted = re.match(r"[\"']([^\"']+)[\"']", raw)
        revs[rev.group(1)] = quoted.group(1) if quoted else "None"

    children: dict[str, list[str]] = {}
    for rev, parent in revs.items():
        children.setdefault(parent, []).append(rev)
    branches = {p: c for p, c in children.items() if len(c) > 1}
    assert not branches, f"체인이 분기했습니다(프로브의 seq 전제가 깨짐): {branches}"

    order: list[str] = []
    cursor = "None"
    while cursor in children:
        cursor = children[cursor][0]
        order.append(cursor)
    assert len(order) == len(revs), f"체인 복원 실패: {len(order)}/{len(revs)}"
    return order


def _probe_rows() -> list[tuple[int, str, str, str]]:
    """프로브의 VALUES 목록을 (seq, revision, table, column)으로 파싱한다."""
    block = re.search(r"VALUES(.*?)\n\)\nSELECT", _probe_text(), re.S)
    assert block, "프로브에서 VALUES 목록을 찾지 못했습니다"
    rows = re.findall(r"\(\s*(\d+),\s*'([^']+)',\s*'([^']*)',\s*'([^']*)'\s*\)", block.group(1))
    assert rows, "VALUES 행을 하나도 파싱하지 못했습니다"
    return [(int(s), r, t, c) for s, r, t, c in rows]


def test_probe_exists() -> None:
    """프로브 파일 존재 — 경로 이동/개명 시 이 계약이 유령이 되는 것 방지."""
    assert _PROBE.is_file(), f"프로브 부재: {_PROBE}"


def test_probe_is_ascii_only() -> None:
    """① cp949 호스트 안전 — 비ASCII 바이트 0."""
    raw = _PROBE.read_bytes()
    offenders = [(i, b) for i, b in enumerate(raw) if b > 0x7F]
    assert not offenders, f"비ASCII 바이트 {len(offenders)}개(첫 위치 {offenders[0][0]})"


@pytest.mark.parametrize(
    "forbidden",
    ["INSERT", "UPDATE", "DELETE", "TRUNCATE", "DROP", "ALTER", "GRANT", "CREATE TABLE"],
)
def test_probe_has_no_write_statements(forbidden: str) -> None:
    """② prod에 그대로 실행되는 파일이다 — 쓰기 구문이 한 줄도 없어야 한다."""
    assert forbidden not in _probe_body().upper(), f"읽기 전용 프로브에 쓰기 구문: {forbidden}"


def test_only_temp_view_is_created() -> None:
    """② 유일하게 허용되는 생성은 세션 한정 TEMP VIEW다(영속 객체 0)."""
    creates = re.findall(r"CREATE\s+(?:OR\s+REPLACE\s+)?(\w+(?:\s+\w+)?)", _probe_body().upper())
    assert creates == ["TEMP VIEW"], f"예상 밖 생성 구문: {creates}"


def test_probe_revisions_exist_at_declared_seq() -> None:
    """③ 선언한 seq가 실제 체인 위치와 일치한다."""
    chain = _chain()
    for seq, revision, _table, _column in _probe_rows():
        assert revision in chain, f"체인에 없는 리비전: {revision}(seq {seq})"
        actual = chain.index(revision)
        assert actual == seq, f"{revision}: 프로브 seq {seq} != 체인 위치 {actual}"


def test_probe_covers_chain_tail() -> None:
    """③ 꼬리 전수 커버 — 마이그레이션이 늘면 이 테스트가 프로브 갱신을 강제한다."""
    chain = _chain()
    expected = {
        rev
        for idx, rev in enumerate(chain)
        if idx >= _TAIL_START_SEQ and rev not in _NO_POSITIVE_DISCRIMINATOR
    }
    covered = {rev for _seq, rev, _t, _c in _probe_rows()}
    missing = sorted(expected - covered, key=chain.index)
    assert not missing, (
        "프로브가 덮지 않는 리비전이 있습니다 — 판별자(생성 테이블 또는 추가 컬럼)를 "
        f"VALUES에 추가하세요: {missing}"
    )


def test_probe_last_row_is_expected_head() -> None:
    """④ 프로브의 마지막 행 = 코드가 기대하는 head."""
    declared = re.search(
        r"EXPECTED_ALEMBIC_HEAD:\s*str\s*=\s*KNOWN_REVISIONS\[-1\]",
        _SCHEMA_VERSION.read_text(encoding="utf-8"),
    )
    assert declared, "schema_version.py의 EXPECTED_ALEMBIC_HEAD 정의 형태가 바뀌었습니다"
    head = _chain()[-1]
    last_seq, last_rev, _t, _c = _probe_rows()[-1]
    assert last_rev == head, f"프로브 마지막 {last_rev} != 체인 head {head}(seq {last_seq})"


def test_discriminators_appear_in_their_migration() -> None:
    """③ 판별자가 그 리비전의 마이그레이션 파일에 실제로 등장한다(한계는 모듈 docstring)."""
    sources: dict[str, str] = {}
    for path in sorted(_VERSIONS.glob("*.py")):
        text = path.read_text(encoding="utf-8")
        rev = re.search(r"^revision[^=\n]*=\s*[\"']([^\"']+)", text, re.M)
        if rev:
            sources[rev.group(1)] = text
    for seq, revision, table, column in _probe_rows():
        body = sources[revision]
        assert f'"{table}"' in body, f"{revision}(seq {seq}): 파일에 테이블 {table!r} 없음"
        if column:
            assert f'"{column}"' in body, f"{revision}(seq {seq}): 파일에 컬럼 {column!r} 없음"


def test_verdict_columns_present() -> None:
    """⑤ 판정치 3개가 모두 산출된다 — 특히 혼입 탐지기(present_after_gap)."""
    text = _probe_text()
    for name in ("stamp_target", "pending_count", "present_after_gap"):
        assert f"AS {name}" in text, f"판정치 누락: {name}"
