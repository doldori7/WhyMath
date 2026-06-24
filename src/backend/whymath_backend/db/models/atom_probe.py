"""②진단문항·③소크라테스 *PG 프로젝션* ORM — code 키 원자 진단·소크라테스 (Phase 3 Slice 3).

`concept_content`(콘텐츠 4종 프로젝션·Phase 3 Slice 1)·`atom_node`(원자 안전 메타·Phase 2a)의
*교수학 탐침* 짝이다. 원자 백본 코퍼스(`data/corpus/atom_graph_v1/graph.json`)의 세부개념 원자가
보유한 **②진단문항**(발문·정답/통과기준·오답신호)과 **③소크라테스 질문**을 code 키로 영속 투영한다
— 학습 장면(L2 진단·L4 소크라테스 코칭·L6 모드)이 backend 조인으로 끌어쓰기 위한 백킹
(`atom_node`·`concept_content`와 동일 설계 철학).

────────────────────────────────────────────────────────────────────────────
additive — 신규 테이블 (왜 problem/dialogue 결합이 아닌가)
────────────────────────────────────────────────────────────────────────────
`problem`(UUID PK·provenance·저작권 validator·문항형식 enum·`problem_step`/`problem_concept`)은
원자 code-grain의 3필드 진단 탐침과 grain이 어긋나고, 끼워넣으면 UUID·source_type 등 *날조*가
필요하다(가드레일 위반). `dialogue`/`dialogue_turn`은 *런타임* 대화 로그(user_id·attempt_id)라
*정적 저작* 콘텐츠인 ③소크라테스와 맞지 않는다. 따라서 Slice 1(`concept_content`)·Phase 2a
(`atom_node`) 선례대로 **신규 경량 code-PK 프로젝션 테이블**을 만든다(구 437·concept_node·
atom_node·concept_content·misconception_catalog와 무충돌·FK 0). ②(3필드)와 ③(1필드)는 같은 원자
행·code 1:1이라 한 테이블에 묶는다(concept_content가 4종을 한 테이블에 묶은 선례).

PK는 `code`(원자 세부개념 code 예 `2수01-01-2`·`CALC1-C01`). **FK는 두지 않는다**(loose ref·
`misconception_catalog.concept_src_id`·`concept_content` 선례) — 적재 순서·재적재 독립성.

────────────────────────────────────────────────────────────────────────────
법적·노출 (CLAUDE.md 우선순위 #2)
────────────────────────────────────────────────────────────────────────────
②진단문항·③소크라테스는 원천 데이터카드상 **전량 와이매스 자체/AI 작성**이라 보유 허용이다. NCIC
성취기준 *본문*은 코퍼스에 *없고*(연결 `standard_codes` *코드*만 다리·구조 차단), 이 테이블도
standard_codes만 둔다(redaction-safe·atom_node·concept_content 동형). 성취기준 본문 슬롯을 두지
않아 구조적으로 차단한다.

review_status는 PG enum 타입을 새로 만들지 않고 **plain `sa.Text`**로 둔다(`atom_node`·
`concept_content` 동형). 탐침은 안내 시트상 *AI 추정·검수필요*라 기본값 상수 `'ai_estimated'`로
적재한다(정직 표기·게이팅).

7계층: L1 데이터 기반의 *영속 프로젝션*(탐침 서빙 백킹). 보관만 하며 소비(L2/L4/L6)는 후속
(역방향 의존 금지).
"""

from __future__ import annotations

from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column

from whymath_backend.db.base import Base

# 탐침 검수 상태 기본값 — 안내 시트상 *AI 추정·검수필요*라 '검수 완료'가 아닌 'ai_estimated'.
# 게이팅 필터가 이 리터럴과 비교한다(정직 표기·검수 승격 시 'reviewed'로 갱신 가능·plain text·
# atom_node·concept_content 동형).
ATOM_PROBE_REVIEW_STATUS_AI_ESTIMATED: str = "ai_estimated"


class AtomProbe(Base):
    """②진단문항·③소크라테스 PG 프로젝션 — code 키 진단(발문·정답·오답신호) + 소크라테스 질문.

    한 행 = 한 원자(세부개념)의 ②진단문항 3필드 + ③소크라테스 질문 + 난이도 + 연결 성취기준 코드.
    PK(code)는 원자 세부개념 code(K-12·대학 겹침 0). upsert로 멱등 적재한다(`ON CONFLICT(code) DO
    UPDATE`). 성취기준 *본문* 슬롯은 없다(redaction·standard_codes 코드만).
    """

    __tablename__ = "atom_probe"

    # PK = 원자 세부개념 code(예 '2수01-01-2'·'CALC1-C01'). upsert 충돌 키.
    code: Mapped[str] = mapped_column(sa.Text, primary_key=True)
    # 원자명(corpus `name`·필수). 표시 핵심.
    name: Mapped[str] = mapped_column(sa.Text, nullable=False)
    # 학교급(초등/중학/고등/대학교·corpus `school_level`·필터). plain TEXT(보조 인덱스).
    school_level: Mapped[str | None] = mapped_column(sa.Text)
    # 영역·과목(corpus `subject_area`·필터). plain TEXT(보조 인덱스).
    subject_area: Mapped[str | None] = mapped_column(sa.Text)
    # 소단원명(corpus `subunit`·nullable).
    subunit: Mapped[str | None] = mapped_column(sa.Text)
    # ②진단문항 — 전량 자체/AI 작성(보유 허용). nullable(코퍼스 빈 값 가능).
    diagnostic_item: Mapped[str | None] = mapped_column(sa.Text)
    # ②정답·통과기준.
    diagnostic_answer: Mapped[str | None] = mapped_column(sa.Text)
    # ②미통과·오답신호.
    diagnostic_signal: Mapped[str | None] = mapped_column(sa.Text)
    # ③소크라테스 질문(단일 발문·자체/AI 작성).
    socratic_question: Mapped[str | None] = mapped_column(sa.Text)
    # 내재 난이도(corpus `intrinsic_difficulty`·1~5·nullable).
    intrinsic_difficulty: Mapped[int | None] = mapped_column(sa.Integer)
    # 연결 NCIC 성취기준 *코드* 목록(corpus `standard_codes`·코드는 사실정보·*본문 statement 아님*·
    # redaction 무관·atom_node·concept_content 동형). nullable=False·server_default 빈 배열.
    standard_codes: Mapped[list[str]] = mapped_column(
        ARRAY(sa.Text), nullable=False, server_default=sa.text("'{}'::text[]")
    )
    # 검수 게이팅 플래그 — 탐침은 *AI 추정·검수필요*라 기본 'ai_estimated'(정직 표기). PG native
    # enum 미생성(atom_node·concept_content 동형·plain text). 게이팅이 이 값과 리터럴 비교.
    review_status: Mapped[str] = mapped_column(sa.Text, nullable=False)
    # 마지막 upsert 시각 — 운영·신선도. server_default now()(upsert 시 코드가 갱신·concept_content).
    updated_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
    )

    __table_args__ = (
        # school_level(학교급)·subject_area(과목) 필터 보조 인덱스(탐침 서빙·검수 빈번).
        sa.Index("ix_atom_probe_school_level", "school_level"),
        sa.Index("ix_atom_probe_subject_area", "subject_area"),
    )


__all__ = [
    "AtomProbe",
    "ATOM_PROBE_REVIEW_STATUS_AI_ESTIMATED",
]
