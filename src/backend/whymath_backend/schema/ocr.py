"""L5 OCR 산출 스키마 — 손글씨 풀이 인식 결과의 *구조*(AST/JSON) 표현.

7계층 경계(CLAUDE.md "표현 ≠ 의미"): OCR 결과는 *화면 문자열*이 아니라 항상 구조로
코어에 들어온다. 한 장의 손글씨 풀이 이미지는 여러 영역(`OcrRegion`)으로 분해되고, 각
영역은 *위치*(`BBox`)·*유형*(`ContentType`: 텍스트/수식)·*인식 결과*(LaTeX 또는 한글 산문)·
*신뢰도*를 가진다. 영역들을 읽기 순서로 모은 것이 `OcrResult`다.

L4 코치 핸드오프(`api/coach.CoachRequest`)와의 *깔끔한 매핑*(coach.py 무변경):
  - `OcrResult.plain_latex`         → `CoachRequest.student_solution`
  - `OcrResult.overall_confidence`  → `CoachRequest.ocr_confidence`
  - `OcrResult.solution_steps`      → `CoachRequest.solution_steps`
  - `OcrResult.solution_step_types` → `CoachRequest.solution_step_types`
  - 전체 `OcrResult` 덤프            → `DialogueTurn.image_analysis`(자유형 JSONB)
  - 원본 이미지 URI                  → `DialogueTurn.image_uri`
클라이언트는 `/v1/ocr`로 구조를 받고, 이어서 `/v1/coach/sessions`에 위 매핑으로 다시
호출한다(2-콜 핸드오프). 백엔드가 두 호출을 *조합*하지 않는다 — OCR 엔드포인트는 순수
인식만 한다(7계층 경계: L5는 하위를 호출하나 합치는 책임은 호출자/오케스트레이션).

컨벤션(`schema/problem.py`·`l3/verify_answer.py` 답습):
  - `ConfigDict(extra="forbid", use_enum_values=True, str_strip_whitespace=True)`.
  - enum은 `enums.py` 재사용(`ContentType`·`StepType`) — 새 enum을 만들지 않는다.
  - 한국어 docstring·주석(Kiki 선호).
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, model_validator

from whymath_backend.schema.enums import ContentType, StepType

# 미성년 풀이 데이터(저장계층 보호 책임·CLAUDE.md): 이 모델들의 인스턴스는 손글씨 풀이에서
# 인식된 *미성년 개인 학습 데이터*다. 평문 장기 저장·외부 공유 금지(저장은 L5 서버 책임).


class BBox(BaseModel):
    """이미지 좌표계의 직사각형 경계 상자 — 영역의 *위치*(픽셀 단위, 좌상단 원점).

    `(x, y)`는 좌상단 꼭짓점, `(width, height)`는 크기다. 음수는 금지(ge=0). 라우팅·
    조립(읽기순·IoU 병합)이 모두 이 좌표를 *순수 계산*으로 쓴다 — 모델 의존 0.
    """

    model_config = ConfigDict(
        extra="forbid",
        use_enum_values=True,
        str_strip_whitespace=True,
    )

    x: float = Field(..., ge=0.0, description="좌상단 x(픽셀·좌→우 증가)")
    y: float = Field(..., ge=0.0, description="좌상단 y(픽셀·위→아래 증가)")
    width: float = Field(..., ge=0.0, description="상자 너비(픽셀)")
    height: float = Field(..., ge=0.0, description="상자 높이(픽셀)")

    @property
    def x2(self) -> float:
        """우하단 x(= x + width). IoU·포함 판정의 보조."""
        return self.x + self.width

    @property
    def y2(self) -> float:
        """우하단 y(= y + height)."""
        return self.y + self.height

    @property
    def area(self) -> float:
        """상자 면적(= width × height). IoU·포함 비율 계산의 분모."""
        return self.width * self.height


class OcrRegion(BaseModel):
    """인식된 영역 1개 — 위치(`BBox`) + 유형(`ContentType`) + 인식 텍스트 + 신뢰도.

    `content_type`은 `ContentType`(enums.py 재사용)의 *텍스트*(한글 산문)·*수식*(LaTeX)만
    쓴다 — OCR 영역은 이미지/혼합이 아니라 *분해된 단위*라 둘 중 하나다. `latex`는 수식
    영역이면 LaTeX, 텍스트 영역이면 한글 산문 그대로다(필드명은 수식이 본질이라 latex로
    두되 텍스트 영역도 같은 필드에 담는다 — 읽기순 조립이 단일 필드를 잇기 쉽다).
    """

    model_config = ConfigDict(
        extra="forbid",
        use_enum_values=True,
        str_strip_whitespace=True,
    )

    bbox: BBox = Field(..., description="영역의 이미지 좌표 경계 상자")
    content_type: ContentType = Field(
        ...,
        description="영역 유형 — 텍스트(한글 산문)·수식(LaTeX). 이미지/혼합 미사용(분해 단위).",
    )
    latex: str = Field(
        default="",
        description=(
            "인식 결과 문자열 — 수식이면 LaTeX, 텍스트면 한글 산문. 빈 문자열 허용"
            "(인식 실패·공백 영역). *표현 ≠ 의미*: 화면 문자열이 아니라 구조의 한 필드."
        ),
    )
    confidence: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="이 영역의 인식 신뢰도(0~1). 검증(verify) 실패 시 강등될 수 있다.",
    )
    verified: bool | None = Field(
        default=None,
        description=(
            "수식 영역의 SymPy 왕복 파싱 검증 결과(verify.py). True=파싱 성공·"
            "False=파싱 불가(신뢰도 강등 근거)·None=미검증(텍스트 영역 등)."
        ),
    )
    needs_review: bool = Field(
        default=False,
        description=(
            "이 영역이 재확인(저신뢰) 후보인지 — (강등 후) confidence < `ocr_min_confidence`면 "
            "True. 기본 False(임계 0=비활성·현 동작). 영역을 *드롭하지 않고* 신호만 단다"
            "(학생 손글씨 데이터 비파괴·표현≠의미). coach overall<0.8 게이트와는 별도(영역 레벨)."
        ),
    )


class OcrResult(BaseModel):
    """한 장의 풀이 이미지 OCR 결과 — 영역 목록 + 집계 뷰(LaTeX·단계·마크다운·신뢰도).

    `regions`는 *읽기 순서*(위→아래·좌→우)로 정렬된 영역 목록이다(조립 `assemble.py`).
    아래 집계 필드는 영역에서 *파생*된 편의 뷰로, L4 코치 핸드오프 매핑의 착지점이다
    (모듈 docstring 매핑 표). `solution_steps`·`solution_step_types`는 길이가 같다
    (전이별 단계 유형 — coach `verify_solution` 규약).
    """

    model_config = ConfigDict(
        extra="forbid",
        use_enum_values=True,
        str_strip_whitespace=True,
    )

    regions: list[OcrRegion] = Field(
        default_factory=list,
        description="읽기순(위→아래·좌→우) 정렬된 인식 영역 목록.",
    )
    plain_latex: str = Field(
        default="",
        description=(
            "영역 인식 결과를 읽기순으로 이은 단일 문자열 — `CoachRequest.student_solution`의 "
            "착지점. *표현이 아니라 구조의 파생 뷰*."
        ),
    )
    solution_steps: list[str] = Field(
        default_factory=list,
        description=(
            "공간정보로 분해한 풀이 단계 시퀀스 — `CoachRequest.solution_steps`의 착지점. "
            "수식 영역을 단계로 본다(텍스트 영역은 단계 아님)."
        ),
    )
    solution_step_types: list[StepType] = Field(
        default_factory=list,
        description=(
            "전이별 단계 유형(조건해석/케이스분류/그래프스케치/계산/검산) — "
            "`CoachRequest.solution_step_types`의 착지점. 길이는 `len(solution_steps)-1`"
            "(전이 수)이며, 단계가 0·1개면 빈 목록(전이 없음)."
        ),
    )
    markdown: str = Field(
        default="",
        description="영역을 사람이 읽기 좋게 이은 마크다운(텍스트는 그대로·수식은 $...$). 표시용.",
    )
    overall_confidence: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description=(
            "전체 신뢰도(영역 신뢰도의 *평균*) — `CoachRequest.ocr_confidence`의 착지점. "
            "<0.8이면 coach가 §3.3 게이트로 재확인을 유도(coach.py 규약)."
        ),
    )
    min_confidence: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="영역 신뢰도의 *최솟값* — 가장 약한 영역(재확인 우선 후보)을 가린다.",
    )
    needs_reconfirmation: bool = Field(
        default=False,
        description=(
            "영역 중 하나라도 `needs_review=True`면 True — L5/클라이언트가 재확인을 유도하라는 "
            "신호(`ocr_min_confidence` 게이트). 임계 0(기본)이면 항상 False(현 동작 불변). "
            "coach `overall_confidence<0.8` 게이트(match_low_quality)와 *독립*(영역 레벨 신호)."
        ),
    )

    @model_validator(mode="after")
    def _check_step_types_length(self) -> OcrResult:
        """`solution_step_types`는 전이 수(= max(len(steps)-1, 0))와 길이가 같아야 한다.

        coach `verify_solution`이 전이별로 단계 유형을 읽으므로(전이 = 인접 단계 쌍) 규약을
        스키마에서 강제한다. 단계가 0·1개면 전이가 없어 유형 목록은 비어야 한다.
        """
        expected = max(len(self.solution_steps) - 1, 0)
        if len(self.solution_step_types) not in (0, expected):
            raise ValueError(
                "solution_step_types 길이는 0(미지정) 또는 전이 수"
                f"(len(solution_steps)-1={expected})여야 합니다."
            )
        return self
