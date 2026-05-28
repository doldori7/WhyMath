"""Schema v1.1 교과서 매핑(TextbookMapping) 모델 (Pydantic) — 슬라이스 8b.

설계 정본: `schemas/v1.1/textbook_mapping.schema.yaml`(1)TextbookMapping·2)TextbookUnit·
3)TextbookToneProfile 3모델·`validation_invariants`·`license`·헤더 🚨저작권 안전선). v1.0
8개 도메인(슬라이스 1~7)·v1.1 CurriculumEntry(슬라이스 8a) *밖*의, v1.1에서 이식하는
*마지막 자산*이다 — 검정 교과서의 *구조*(목차·단원 트리·페이지 번호·교육과정 코드·서지)를
개념(concept_id)·NCIC 성취기준(standard_codes)에 잇는 매핑이다. 소유 7계층은 L1(데이터
기반), 매핑을 학생 맥락 정렬에 쓰는 엔진은 L6 소관(YAML 헤더).

Phase 메모: 코드베이스 전체가 *Pydantic-schema-only*(DB 미배포) — 이 슬라이스도 순수
Pydantic 모델이다. SQLAlchemy/alembic 매핑(YAML storage: PostgreSQL 16, ON DELETE CASCADE
격리)은 후속 Phase(슬라이스 1~8a 동일 패턴). 스키마는 한국 9종 × 8과목 풀 매핑을 *미리
수용*하되(필드는 개방형) 데이터는 Phase 1 파일럿 범위(미래엔·천재교육 2종 × 고1 단원)다.

🚨 저작권 안전선(이 모듈의 핵심 — YAML 헤더·`license`·CLAUDE.md 절대 금기):
  ✅ 사용 — *구조 메타데이터만*: 목차·단원명·차시명·단원번호·페이지 범위(*번호*)·학습
            순서·교육과정 코드(standard_codes)·서지(ISBN·출판사·서명·저자·개정연도).
  ❌ 미사용 — 일절 복제 안 함: 본문·개념 설명·예제·연습문제·단원평가·풀이·해설·그림·
            그래프·도표·삽화·폰트·디자인·레이아웃.
  교과서 예제·문제는 이 모델에 담지 않는다 — 학생이 "우리 교과서 같은 문제"를 원하면 그
  단원의 `standard_codes`·`concept_ids`를 키로 WhyMath 자체 문제 코퍼스(problem.schema.yaml
  — NuminaMath 등 공개 + 자체 생성)에서 *동등 문제*를 꺼낸다(12단계 파이프라인은 "교과서
  문제 수집" 단계를 *아예 갖지 않는다* — 그게 설계). 이는 CLAUDE.md 절대 금기 "검정 교과서
  본문·문제 복제 금지"의 *교과서 매핑 수준 구체화*이지 새 예외가 아니다.

  `learning_objective_text`(교과서 단원 첫머리 학습목표 문장)는 교과서 저작물이라 *변호사
  검토 전까지 null 고정*이다 — `TextbookMapping.legal_review_status='cleared'`가 아니면 모든
  단원에서 None이어야 하며 비-null 발견 시 적재를 거부한다(아래 `TextbookMapping` validator
  2). 근거: MEMORY PRD 허점 ⑥ — 한국 저작권법에 미국식 fair use 법리가 그대로 있지 않아
  교과서 문장을 "페어유즈" 단정으로 수집할 수 없다. 이 게이팅은 슬라이스 1 `Problem` 본문
  차단·슬라이스 2 `ContentProvenance` license 차단과 같은 *구조 신호(legal_review_status)
  기반 강제 가능* 케이스다(자유 서술 텍스트라 강제 불가했던 슬라이스 3 `Concept` 법적 메모와
  대비 — 여기선 진짜 invariant다).

컨벤션(`problem.py`·`concept.py`·`curriculum_entry.py` 답습):
  - `ConfigDict(extra="forbid", use_enum_values=True, str_strip_whitespace=True)`(3모델 공통).
  - enum은 `enums.py`의 `class X(str, Enum)`(Literal 아님). 이 모델은 `LegalReviewStatus`
    (3종, 영어) 신규 enum을 쓴다. ⚠️ 기존 `ReviewStatus`(pending/approved/rejected, 문제
    검수)와 *다른* enum이다 — 이쪽은 교과서 학습목표 *저작권* 검토 상태다.
  - 불변식은 `@model_validator(mode="after")`(자기참조 금지는 슬라이스 3 `Concept._no_self_
    parent` 패턴, 법적 게이팅은 슬라이스 1·2의 enum/문자열 정규화 패턴 답습).
  - 공유 베이스 클래스 없음(각 모델 독립). 서브모델(TextbookToneProfile·TextbookUnit)을
    먼저 정의한 뒤 TextbookMapping을 정의한다.

타입 매핑 판단(YAML `type:` → Pydantic, 슬라이스 1~8a 선례 그대로):
  - `string`(required:true) → required `str`(`Field(...)`)
  - `string`(required:false) → `str | None`(default 명시)
  - `string | null` → `str | None`(예: parent_unit_id·page_range·learning_objective_text)
  - `integer`(required:true) → required `int`(예: grade·revision_year)
  - `list<string>` → `list[str] = Field(default_factory=list)`
  - `list<TextbookUnit>`(required) → `list[TextbookUnit] = Field(..., min_length=1)`
  - `TextbookToneProfile`(required) → required 서브모델
  - `enum`(required, default 있음) → `LegalReviewStatus = Field(default=...)`

⚠️ str로 둔 필드(enum 날조 회피 — 슬라이스 4 gender·슬라이스 8a country_code 방침):
  YAML이 `subject`를 "8과목 enum"으로, `publisher`를 `enum_phase1=[미래엔, 천재교육]`로
  *언급*하나 값을 완전히 열거하지 않았고(subject는 8과목 체계를 예시로만 들고, publisher는
  examples로 8종 이상을 더 든다), 기존 NCIC `AchievementStandard.subject`가 `str`인 것과
  정합하므로 둘 다 `str`로 둔다. Phase 1 범위 가드(미래엔/천재교육 2종·8과목)는 *데이터/
  파이프라인* 책임이지 모델 강제가 아니다. enum으로 명시·열거된 것은 `legal_review_status`
  (3종)뿐이라 그것만 enum이다.

cross-dataset·파이프라인 책임 메모(YAML `validation_invariants` 중 모델 단독 강제 불가 항목):
  YAML invariant 중 *다른 데이터셋이 있어야 검증 가능한 것*·*list 전체가 필요한 것*은 모델이
  강제하지 않는다 — ① `standard_codes`가 NCIC standards.json에 실재(키 공간 정합), ②
  `concept_ids`가 개념 그래프/매트릭스 키 공간에 실재, ③ `unit_tree` 전체의 사이클·고아 노드
  없음(트리 전체 순회가 필요 — 단일 노드로는 검증 불가), ④ Phase 1 산출물 출판사가
  {미래엔, 천재교육}뿐(범위 가드), ⑤ 본문 혼입 휴리스틱 스캔(문장부호 패턴 등 사람 검수
  연계). 이들은 *파이프라인 책임*이다(슬라이스 8a cross-dataset 메모와 동일 방침 —
  모델 내부로 강제 가능한 invariant만 validator로 구현하고, 단원명 길이 상한 같은 *단일 노드
  레벨 신호*만 모델이 가드한다).
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, model_validator

from whymath_backend.schema.enums import LegalReviewStatus


# ──────────────────────────────────────────────────────────────────────────
# 서브모델: TextbookToneProfile (textbook_mapping.schema.yaml 3절 — WhyMath 분류 라벨)
# ──────────────────────────────────────────────────────────────────────────
class TextbookToneProfile(BaseModel):
    """교과서 톤 프로필 — YAML 3절. 교과서 서술 스타일을 WhyMath가 부여한 *분류 라벨·범주값*
    으로만 표현한 자체 분석물이다.

    본문 텍스트를 일절 담지 않는다 — 라벨을 만드는 분석 과정에서 본문을 *읽을* 수는 있으나
    저장·재배포하지 않는다(licensing_safety.md "분류·메타데이터는 되고 본문은 안 된다").
    """

    model_config = ConfigDict(
        # 추가 필드 금지 — Pydantic 모델이 스키마의 단일 진실
        extra="forbid",
        # 직렬화 시 enum 값을 그대로(이 서브모델엔 enum 없으나 3모델 ConfigDict 통일)
        use_enum_values=True,
        # 문자열 양끝 공백 제거
        str_strip_whitespace=True,
    )

    formality_level: str = Field(
        ...,
        description="서술 격식 수준 — WhyMath 자체 라벨(예: '높음'). 본문 아님.",
    )
    notation_preferences: list[str] = Field(
        default_factory=list,
        description="선호 표기 경향 — 라벨 목록(본문 아님).",
    )
    sequencing_style: str = Field(
        ...,
        description="단원 배열 스타일 — WhyMath 자체 라벨(예: '개념선행형'). 본문 아님.",
    )


# ──────────────────────────────────────────────────────────────────────────
# 서브모델: TextbookUnit (textbook_mapping.schema.yaml 2절 — 단원 트리 노드)
# ──────────────────────────────────────────────────────────────────────────
class TextbookUnit(BaseModel):
    """단원 트리 노드 — YAML 2절. 대→중→소단원 트리의 한 노드. 단원명·단원번호·페이지 *번호*
    범위는 *사실정보*(목차)이지 본문이 아니다.

    `parent_unit_id`로 상위 단원을 가리키는 자기참조 트리이며(대단원이면 None),
    `standard_codes`(NCIC 성취기준 코드)·`concept_ids`(Universal Concept ID)로 truth source에
    연결된다(둘 다 N:M, 실재 검증은 cross-dataset — 모듈 docstring 파이프라인 책임 메모).

    `learning_objective_text`는 교과서 저작물이라 기본 None이며, 비-null 허용 여부는 소속
    `TextbookMapping.legal_review_status`가 결정한다(게이팅은 `TextbookMapping` validator 2에서
    트리 전체를 보고 강제 — 단일 노드로는 소속 매핑의 상태를 알 수 없어 여기서 막지 않는다).

    불변식(`@model_validator(mode="after")`, 슬라이스 3 `Concept._no_self_parent` 패턴):
    `parent_unit_id`가 있으면 `unit_id != parent_unit_id`(자기 자신을 부모로 둘 수 없음).
    트리 전체의 사이클·고아 노드 검증은 list 전체 순회가 필요하므로 *파이프라인 책임*이다
    (모듈 docstring 메모 — 단일 노드 레벨에서 강제 가능한 자기부모 금지만 여기서 막는다).
    """

    model_config = ConfigDict(
        extra="forbid",
        use_enum_values=True,
        str_strip_whitespace=True,
    )

    unit_id: str = Field(
        ...,
        description="단원 노드 PK.",
    )
    parent_unit_id: str | None = Field(
        default=None,
        description="상위 단원 PK(대→중→소 트리 자기참조). 대단원이면 None. 자기 자신 불가"
        "(아래 불변식으로 강제).",
    )
    unit_number: str = Field(
        ...,
        description="단원 번호 — 사실정보(예: '1-2').",
    )
    unit_title: str = Field(
        ...,
        # YAML: "여러 문장·과도한 길이가 들어오면 본문 혼입 신호". 단원명은 보통 명사구이므로
        # max_length=200으로 *본문 혼입을 모델 레벨에서 가드*한다(휴리스틱 경고의 하드 상한 —
        # 문장부호 패턴 등 나머지 휴리스틱 스캔은 파이프라인 책임. 슬라이스 3 Concept.name_ko도
        # 200자 상한). 단원명 자체는 사실정보이지 본문이 아니다.
        max_length=200,
        description="단원명 — 사실정보(목차), 본문 아님. 보통 명사구(예: '이차함수의 그래프'). "
        "max_length=200은 과도한 길이=본문 혼입 신호를 막는 모델 레벨 가드.",
    )
    page_range: str | None = Field(
        default=None,
        description="페이지 *번호* 범위일 뿐 페이지 *내용*이 아님(예: '12-35').",
    )
    standard_codes: list[str] = Field(
        default_factory=list,
        description="매핑된 NCIC 성취기준 코드(예: '[10공수1-02-01]'). 교과서 매핑의 매칭 타겟이 "
        "NCIC 성취기준이다(공공누리 1유형). standards.json 실재는 cross-dataset(파이프라인 책임).",
    )
    concept_ids: list[str] = Field(
        default_factory=list,
        description="매트릭스·그래프 Universal Concept ID(한 단원 N개 개념 ↔ 한 개념 M개 단원, "
        "다대다). concept.schema.yaml과 동일 키 공간 — 실재는 cross-dataset(파이프라인 책임).",
    )
    learning_objective_text: str | None = Field(
        default=None,
        description="교과서 단원 첫머리 '학습목표' 문장 — 교과서 저작물. **변호사 검토"
        "(소속 TextbookMapping.legal_review_status='cleared') 전까지 null 고정.** 비-null 발견 "
        "시 적재 거부(TextbookMapping validator 2). 근거: MEMORY PRD 허점 ⑥(fair use 단정 위험).",
    )

    # ── 불변식 ────────────────────────────────────────────────────
    @model_validator(mode="after")
    def _no_self_parent(self) -> TextbookUnit:
        """자기 자신을 부모로 둘 수 없다 — parent_unit_id ≠ unit_id.

        슬라이스 3 `Concept._no_self_parent` 패턴. parent가 None이면 검사 대상 아님(대단원
        허용). 트리 전체의 사이클·고아 노드 검증은 list 전체가 필요해 *파이프라인 책임*이다
        (모듈 docstring 메모).
        """
        if self.parent_unit_id is not None and self.parent_unit_id == self.unit_id:
            raise ValueError(
                "단원 트리 위반: parent_unit_id가 unit_id와 같을 수 없다 "
                "(자기 자신이 부모일 수 없음)"
            )
        return self


# ──────────────────────────────────────────────────────────────────────────
# 핵심: TextbookMapping (textbook_mapping.schema.yaml 1절 — 교과서 1권, PK=isbn)
# ──────────────────────────────────────────────────────────────────────────
class TextbookMapping(BaseModel):
    """교과서 매핑 — YAML 1절. 검정 교과서 1권의 *구조*(서지 + 단원 트리 + 톤 프로필)를 개념·
    NCIC 성취기준에 잇는 매핑. PK는 `isbn`(13자리).

    🚨 저작권 안전선(모듈 docstring 참조): 서지(ISBN·출판사·서명·저자)·목차(단원 트리)·페이지
    *번호*·교육과정 코드 같은 *구조 메타데이터만* 담고 본문·예제·문제·풀이·그림은 일절 담지
    않는다. 교과서 예제·문제는 `standard_codes`·`concept_ids`로 자체 코퍼스 동등문제를 꺼내
    대체한다(CLAUDE.md "검정 교과서 본문·문제 복제 금지"의 구체화).

    불변식(`@model_validator(mode="after")` 2개, 모델 내부로 강제 가능한 것만 — 모듈 docstring
    파이프라인 책임 메모):
      1. `isbn` 13자리 형식 — 정확히 숫자 13자리(`^\\d{13}$`)가 아니면 ValueError(YAML
         "13자리 ISBN"). 하이픈·문자·12/14자리 거부.
      2. 🚨 `learning_objective_text` 게이팅 — `legal_review_status`가 `cleared`가 *아니면*
         `unit_tree`의 모든 `TextbookUnit`의 `learning_objective_text`가 *반드시 None*이어야
         한다(비-null이면 ValueError). 교과서 저작물인 학습목표 문장을 변호사 검토(cleared)
         전까지 수집·적재할 수 없다(MEMORY PRD 허점 ⑥ — 한국 저작권법에 미국식 fair use 없음).
         use_enum_values=True라 legal_review_status가 문자열 값일 수 있으므로 enum/문자열 양쪽을
         정규화해 `cleared`와 비교한다(슬라이스 2 `provenance.py` 패턴). 이는 슬라이스 1 Problem
         본문 차단·슬라이스 2 license 차단과 같은 *구조 신호 기반 진짜 invariant*다.

    `isolation_tag`는 즉시 격리용(출판사+ISBN 단위) — 출판사가 이의를 제기하면 이 태그로 해당
    교과서만 떼어낸다(DB는 ON DELETE CASCADE로 단원 동반 삭제). 격리 가능성은 사후 수습이
    아니라 *설계 요구사항*(YAML §4.5). 단원↔개념↔성취기준 매핑·톤 프로필 라벨은 WhyMath 창작
    물(자체 자산)이고, ISBN·서명·단원명·페이지는 사실정보(저작권 보호 대상 아님), NCIC 코드는
    공공누리 1유형(출처 표시 의무 승계)이다(YAML `license`).
    """

    model_config = ConfigDict(
        # 추가 필드 금지 — Pydantic 모델이 스키마의 단일 진실
        extra="forbid",
        # 직렬화 시 enum 값을 그대로(legal_review_status="not_required" 등 영어 값 보존)
        use_enum_values=True,
        # 문자열 양끝 공백 제거
        str_strip_whitespace=True,
    )

    # ===== 교과서 메타데이터 (서지 = 사실정보, 저작권 보호 대상 아님) =====
    isbn: str = Field(
        ...,
        description="PK. 13자리 ISBN(숫자 13자리 형식 — 아래 불변식으로 강제).",
    )
    publisher: str = Field(
        ...,
        description="출판사명(예: '미래엔', '천재교육'). YAML이 enum_phase1로 *언급*하나 값을 "
        "완전 열거 안 해 str로 둔다 — Phase 1 2종 범위 가드는 파이프라인 책임(NCIC subject가 "
        "str인 것과 정합).",
    )
    book_title: str = Field(
        ...,
        description="서명 — 사실정보(예: '고등학교 수학').",
    )
    authors: list[str] = Field(
        default_factory=list,
        description="저자 표시 — 사실정보.",
    )
    subject: str = Field(
        ...,
        description="과목 — NCIC 2022 개정 고등학교 8과목 체계와 정렬(공통수학1·2, 대수, 미적분 "
        "Ⅰ·Ⅱ, 확률과 통계, 기하 등). YAML이 '8과목 enum'으로 *언급*하나 열거 안 해 str로 둔다 "
        "(NCIC AchievementStandard.subject가 str인 것과 정합).",
    )
    grade: int = Field(
        ...,
        # YAML: 10·11·12(고1~3) | 7·8·9(중1~3). 중1~고3을 포괄해 ge=1 le=12로 둔다
        # (슬라이스 3 Concept.grade_introduced·슬라이스 8a 학년 필드 선례 — 중·고 포괄 보수값).
        ge=1,
        le=12,
        description="학년 — 10·11·12(고1~3) | 7·8·9(중1~3). 중1~고3 포괄해 ge=1 le=12.",
    )
    revision_year: int = Field(
        ...,
        description="교과서 개정 연도.",
    )
    curriculum_revision: str | None = Field(
        default="2022 개정",
        description="교육과정 개정 표시(YAML default '2022 개정').",
    )

    # ===== 단원 트리 (목차 = 사실정보) =====
    unit_tree: list[TextbookUnit] = Field(
        ...,
        min_length=1,
        description="대→중→소단원 트리(각 원소는 TextbookUnit). 최소 1개. 유효한 트리여야 함 — "
        "사이클·고아 노드 없음 검증은 트리 전체 순회가 필요해 파이프라인 책임(모듈 docstring).",
    )

    # ===== 톤 프로필 (WhyMath 자체 분석물 — 본문 아님, 분류 라벨만) =====
    tone_profile: TextbookToneProfile = Field(
        ...,
        description="교과서 서술 스타일을 WhyMath가 *분류 라벨*로만 표현한 자산(본문 미포함).",
    )

    # ===== 출처·격리 메타 =====
    source_urls: list[str] = Field(
        ...,
        min_length=1,
        description="목차 출처 — 출판사 공식 사이트·도서관 서지 메타데이터(본문 페이지 URL 아님). "
        "최소 1개.",
    )
    isolation_tag: str = Field(
        ...,
        description="즉시 격리용 태그(출판사+ISBN 단위). 출판사 이의 제기 시 이 태그로 "
        "해당 교과서만 떼어낸다(DB ON DELETE CASCADE). 격리 가능성은 설계 요구사항(YAML §4.5).",
    )
    legal_review_status: LegalReviewStatus = Field(
        default=LegalReviewStatus.not_required,
        description="변호사 검토 상태 — not_required/pending/cleared. learning_objective_text "
        "활성화 여부를 결정(cleared가 아니면 모든 단원 None 강제 — 아래 불변식 2).",
    )

    # ── 불변식 ────────────────────────────────────────────────────
    @model_validator(mode="after")
    def _isbn_is_13_digits(self) -> TextbookMapping:
        """isbn은 정확히 숫자 13자리여야 한다 — `^\\d{13}$`.

        YAML "13자리 ISBN" 형식 검증. 하이픈·문자가 섞이거나 12/14자리면 거부한다. (str_strip_
        whitespace로 양끝 공백은 이미 제거된 뒤 검사된다.)
        """
        if not (len(self.isbn) == 13 and self.isbn.isdigit()):
            raise ValueError(
                f"교과서 매핑 위반: isbn은 정확히 숫자 13자리여야 한다(현재 {self.isbn!r}). "
                "하이픈·문자 없이 13자리 숫자만 허용한다."
            )
        return self

    @model_validator(mode="after")
    def _gate_learning_objective_text_until_cleared(self) -> TextbookMapping:
        """🚨 법적 게이팅 — legal_review_status가 'cleared'가 아니면 모든 단원의
        learning_objective_text가 None이어야 한다.

        교과서 단원 학습목표 문장은 교과서 저작물이므로 변호사 검토(legal_review_status=
        'cleared') 전까지 수집·적재할 수 없다 — 비-null 발견 시 ValueError를 던져
        ValidationError로 전파한다(YAML: "비-null 발견 시 적재 거부"). 근거: MEMORY PRD 허점
        ⑥ — 한국 저작권법에 미국식 fair use 법리가 그대로 있지 않아 "페어유즈" 단정으로 수집할
        수 없다. 이는 슬라이스 1 `Problem` 본문 차단·슬라이스 2 `ContentProvenance` license
        차단과 같은 *구조 신호(legal_review_status) 기반 진짜 invariant*다.

        use_enum_values=True 환경: `legal_review_status`가 문자열 값일 수 있으므로 enum/문자열
        양쪽을 정규화해 'cleared'와 비교한다(슬라이스 2 `provenance.py` 패턴 답습).
        """
        # ── enum/문자열 정규화 (use_enum_values=True 대응) ──
        status_value = (
            self.legal_review_status.value
            if isinstance(self.legal_review_status, LegalReviewStatus)
            else self.legal_review_status
        )
        if status_value == LegalReviewStatus.cleared.value:
            # 검토 통과 — learning_objective_text 활성화 허용(게이팅 비적용)
            return self

        # cleared가 아니면(not_required·pending) 모든 단원의 학습목표 텍스트가 None이어야 함
        offending_units = [
            unit.unit_id for unit in self.unit_tree if unit.learning_objective_text is not None
        ]
        if offending_units:
            raise ValueError(
                f"저작권 게이팅 위반: legal_review_status={status_value!r}(cleared 아님)에서는 "
                "모든 단원의 learning_objective_text가 None이어야 한다(교과서 저작물 — 변호사 "
                f"검토 전 미수집). 비-null이 발견된 단원: {offending_units}. "
                "MEMORY PRD 허점 ⑥: 한국 저작권법에 미국식 fair use가 그대로 있지 않다."
            )
        return self
