"""store.id_number_of — 슬러그 없는 ID 파싱 결함 (HARN-21 결함 ①).

`TASK_ID_RE`(models.py)는 슬러그가 **옵션**이라 `HARN-20`처럼 슬러그 없는 ID도 유효한
태스크 ID다. 그런데 구 `_ID_NUMBER_RE`는 캡처 그룹 뒤에 반드시 `-`가 와야 매치했다 —
슬러그 없는 ID는 `id_number_of`가 `None`을 돌려줬고, 그러면 `_taken_id_numbers`·
`_id_number_collisions`가 그 번호를 점유 목록에서 **누락**시켜 1선(`add`)·2선
(`validate`) 번호 충돌 검사를 양쪽 다 우회할 수 있었다.

이 파일은 `TASK_ID_RE`가 허용하는 전 형태(슬러그 있음/없음·접두 1~8자·번호 2자리
이상·슬러그 다단)에서 `id_number_of`가 정확히 `<PREFIX>-<번호>`를 뽑아내는지 표로
검증한다.
"""

from __future__ import annotations

import pytest
import store


class TestIdNumberOfCoversSluglessIds:
    """수정 전: 슬러그 없는 ID가 전부 None → 번호 충돌 검사에서 누락됐다."""

    @pytest.mark.parametrize(
        ("task_id", "expected"),
        [
            # 슬러그 없음 (TASK_ID_RE의 슬러그-옵션 형태) — 구현 전엔 전부 None이었다.
            ("HARN-20", "HARN-20"),
            ("S2-04", "S2-04"),
            ("E1-99", "E1-99"),
            ("A-01", "A-01"),  # 접두 1자
            ("ABCDEFGH-02", "ABCDEFGH-02"),  # 접두 8자(TASK_ID_RE 상한)
            # 슬러그 있음 — 기존에도 통과했어야 하는 형태(회귀 방지)
            ("HARN-20-foo", "HARN-20"),
            ("HARN-20-foo-bar", "HARN-20"),
            ("S2-04-alpha", "S2-04"),
            # 규약을 벗어난 ID — 여전히 None(검사 대상 아님)
            ("not-a-task-id", None),
            ("", None),
        ],
    )
    def test_id_number_of_table(self, task_id: str, expected: str | None):
        assert store.id_number_of(task_id) == expected
