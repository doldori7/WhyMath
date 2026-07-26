"""dialogue_turn image 봉투 암호화 컬럼 — SEC-01

`image_uri`(손글씨 이미지 URI)·`image_analysis`(Qwen3-VL 분석 JSONB)는 **미성년 풀이 전사가
가능한** 데이터인데 암호화 경로가 아예 없었다(평문 Text/JSONB). `content`와 동일한 봉투 암호화
(AES-256-GCM) 컬럼을 additive로 추가한다.

- **키는 content와 동일**(`dialogue_content_encryption_key`) — 같은 테이블·같은 요청·같은 데이터
  주체라 키를 쪼개도 폭발 반경이 실질적으로 줄지 않는 반면, 키가 늘면 "미설정→평문 폴백" 함정이
  하나 더 생긴다(Kiki 결정).
- **additive·nullable**: 기존 행은 평문 컬럼을 그대로 유지하고 신규 행만 암호화된다(dual-read).
  기존 데이터 백필은 이 마이그레이션 범위가 아니다 — 실사용자 0(Phase 1)이라 백필 대상이 없고,
  있다면 별도 재암호화 슬라이스가 맞다(마이그레이션에서 키를 읽지 않는다).

마이그레이션 ID는 sliding-window hex 스킴을 따른다(임의 id는 alembic CycleDetected 유발 —
MEMORY 2026-07-03 실측). down_revision = 직전 head `f1a2b3c4d5e7`.

Revision ID: a2b3c4d5e6f1
Revises: f1a2b3c4d5e7
Create Date: 2026-07-26
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "a2b3c4d5e6f1"
down_revision = "f1a2b3c4d5e7"
branch_labels = None
depends_on = None

# (컬럼명, 주석) — up/down이 같은 목록을 공유해 한쪽만 수정되는 표류를 막는다.
_COLUMNS: tuple[str, ...] = (
    "image_uri_encrypted",
    "image_uri_nonce",
    "image_analysis_encrypted",
    "image_analysis_nonce",
)


def upgrade() -> None:
    """봉투 암호화 컬럼 4개 추가(전부 nullable LargeBinary·기존 행 무영향)."""
    for column in _COLUMNS:
        op.add_column("dialogue_turn", sa.Column(column, sa.LargeBinary(), nullable=True))


def downgrade() -> None:
    """컬럼 제거 — 역적용 시 암호화 행의 본문이 *소실*된다는 점에 유의.

    평문 컬럼은 암호화 행에서 NULL이므로, 이 다운그레이드는 그 행들의 이미지 데이터를 복구
    불가능하게 만든다. 운영 롤백 전에 재복호·백필이 선행돼야 한다(스키마 왕복 테스트는
    데이터 없는 fresh DB 기준이라 통과한다).
    """
    for column in reversed(_COLUMNS):
        op.drop_column("dialogue_turn", column)
