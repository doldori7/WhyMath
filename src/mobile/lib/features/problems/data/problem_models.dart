// 문제·진단 API 데이터 모델 — S1 E2E 루프의 진단(CAT)→문제제시 구간 계약을 구조 그대로 옮긴다.
//
// 정본: `src/backend/whymath_backend/schema/problem.py`(`Problem`),
// `api/me.py`(`NextProblemResponse`·`ConceptDiagnosisItem`).
//
// **경계(CLAUDE.md)**: 이 클래스들은 *수신 컨테이너*일 뿐이다 — 출제·진단 로직은 전부 서버
// (L2 IRT/BKT)가 내리고 클라는 구조 그대로 받아 렌더만 한다(표현≠의미·수학 로직 클라 미구현).
//
// **⚠️ 안전(절대 원칙 #1·CLAUDE.md 절대금기 "막혔을 때 바로 정답 제공 금지")**: 백엔드
// `GET /v1/problems/{id}`는 `answer`·`answer_explanation`을 그대로 반환한다(학생 대면 answer
// 비노출은 코치/verify 계층의 불변식이지 이 CRUD-read에서 강제되지 않는다). 따라서 클라 [Problem]
// 모델은 `answer`·`answer_explanation`·정답 파생 필드(answer_constraint·answer_transform·
// multiple_answers)를 **아예 선언하지 않는다** — json_serializable은 미선언 키를 무시하므로 정답이
// 클라 객체 그래프에 진입 자체를 못 한다(구조적 차단). 정오 판단은 오직 verify/coach 신호로 한다.
//
// **enum 표현 방침**: 백엔드 문자열 enum(source_type·question_format·subject 등)은 `String`으로
// 유지한다(coach_models.dart 동일 방침·과확장/codegen 리스크 최소화·백엔드 한글 값 보존).
import 'package:freezed_annotation/freezed_annotation.dart';

part 'problem_models.freezed.dart';
part 'problem_models.g.dart';

// ─────────────────────────────────────────────────────────────────────────
// GET /v1/me/next-problem — NextProblemResponse (me.py)
// ─────────────────────────────────────────────────────────────────────────

/// IRT 적응 출제(CAT) 응답 — 다음 문항 추천 + 능력 추정 스냅샷.
///
/// [problemId]가 null이면 추천 후보가 없다(측정 충분·또는 미시딩). [measurementSufficient]가
/// true면 표준오차가 임계(SE ≤ 0.3) 이하라 CAT 중단을 권고한다. 판정은 서버가 하고 클라는 렌더만.
@freezed
abstract class NextProblemResponse with _$NextProblemResponse {
  const factory NextProblemResponse({
    /// 추천 문항 PK(UUID 문자열). 후보 없으면 null.
    @JsonKey(name: 'problem_id') String? problemId,

    /// 현재 능력 추정 θ(logit). 응답 이력 없으면 0.
    @JsonKey(name: 'theta') @Default(0.0) double theta,

    /// 추천 문항 난이도(1~5)·후보 없으면 null.
    @JsonKey(name: 'difficulty') double? difficulty,

    /// θ 표준오차(응답 없으면 null).
    @JsonKey(name: 'standard_error') double? standardError,

    /// SE ≤ 0.3이면 true(적응 검사 중단 권고).
    @JsonKey(name: 'measurement_sufficient')
    @Default(false) bool measurementSufficient,
  }) = _NextProblemResponse;

  factory NextProblemResponse.fromJson(Map<String, dynamic> json) =>
      _$NextProblemResponseFromJson(json);
}

// ─────────────────────────────────────────────────────────────────────────
// GET /v1/me/diagnosis/concepts — list[ConceptDiagnosisItem] (me.py)
// ─────────────────────────────────────────────────────────────────────────

/// 개념 진단 1건 — BKT 숙달 ↔ IRT θ 교차검증 결과 + 코칭 트리거.
///
/// [coaching].focus가 코치 세션 진입 시 `coaching_focus` 후보로 쓰인다(진단→코치 다리).
@freezed
abstract class ConceptDiagnosisItem with _$ConceptDiagnosisItem {
  const factory ConceptDiagnosisItem({
    /// 개념 PK(UUID 문자열).
    @JsonKey(name: 'concept_id') required String conceptId,

    /// 개념 코드(예: 'math.calculus.limit')·없으면 null.
    @JsonKey(name: 'concept_code') String? conceptCode,

    /// 개념 한글명·없으면 null.
    @JsonKey(name: 'concept_name') String? conceptName,

    /// BKT 숙달 확률(0~1)·없으면 null.
    @JsonKey(name: 'bkt_mastery') double? bktMastery,

    /// IRT 능력 추정 θ·없으면 null.
    @JsonKey(name: 'irt_theta') double? irtTheta,

    /// θ→숙달 근사(0~1)·없으면 null.
    @JsonKey(name: 'irt_mastery_proxy') double? irtMasteryProxy,

    /// 응답 수(진단 근거 표본).
    @JsonKey(name: 'response_count') @Default(0) int responseCount,

    /// BKT↔IRT 일치 라벨('agree'·'irt_higher'·'bkt_higher'·'insufficient').
    @JsonKey(name: 'agreement') @Default('insufficient') String agreement,

    /// 메타인지 코칭 트리거(focus가 코치 진입 시드).
    @JsonKey(name: 'coaching') required DiagnosisCoaching coaching,
  }) = _ConceptDiagnosisItem;

  factory ConceptDiagnosisItem.fromJson(Map<String, dynamic> json) =>
      _$ConceptDiagnosisItemFromJson(json);
}

/// 진단 코칭 트리거(백엔드 `CoachingTrigger` 미러 — problems 로컬 정의로 chat feature 결합 회피).
///
/// 누출 안전: [prompt]는 답을 제공하지 않는 메타인지 유도 발화다(교수학 자산·정답 아님).
@freezed
abstract class DiagnosisCoaching with _$DiagnosisCoaching {
  const factory DiagnosisCoaching({
    /// 코칭 포커스('verify'·'consolidate'·'retrieval'·'foundation'·'advance' 등).
    @JsonKey(name: 'focus') required String focus,

    /// 결정 근거(학생/교사 노출 가능 한국어).
    @JsonKey(name: 'rationale') required String rationale,

    /// 학생에게 보일 수 있는 메타인지 유도 발화(답 미제공).
    @JsonKey(name: 'prompt') required String prompt,

    /// 대화 진입 소크라테스 카테고리 문자열.
    @JsonKey(name: 'socratic_category') @Default('') String socraticCategory,

    /// verify 포커스가 가리키는 첫 incorrect 전이 인덱스(0-based)·없으면 null.
    @JsonKey(name: 'focus_step_index') int? focusStepIndex,
  }) = _DiagnosisCoaching;

  factory DiagnosisCoaching.fromJson(Map<String, dynamic> json) =>
      _$DiagnosisCoachingFromJson(json);
}

// ─────────────────────────────────────────────────────────────────────────
// GET /v1/problems/{id} — Problem (schema/problem.py)
// ─────────────────────────────────────────────────────────────────────────

/// 학생 대면 문제 — 발문·형식·맥락만 담는다.
///
/// ⚠️ **정답 계열 필드는 의도적으로 미선언**(파일 상단 안전 주석): `answer`·`answer_explanation`·
/// `answer_constraint`·`answer_transform`·`multiple_answers`는 백엔드가 응답에 실어 보내더라도
/// 이 모델에 역직렬화되지 않는다(json_serializable 미선언 키 무시 → 정답이 UI에 진입 불가).
/// `choices`(객관식 보기)는 학생 대면 자산이므로 유지한다(정답 표시가 아니라 선택지).
@freezed
abstract class Problem with _$Problem {
  const factory Problem({
    /// 문제 PK(UUID 문자열).
    @JsonKey(name: 'problem_id') required String problemId,

    /// 사람이 읽는 식별자·없으면 null.
    @JsonKey(name: 'slug') String? slug,

    /// 출처('자체생성'·'평가원'·'EBS' 등).
    @JsonKey(name: 'source_type') required String sourceType,

    /// 과목('공통'·'미적분'·'확통'·'기하' 등).
    @JsonKey(name: 'subject') required String subject,

    /// 소단원명(자연어)·없으면 null.
    @JsonKey(name: 'subunit') String? subunit,

    /// 단원 코드 배열(예: ['CAL-INT-DEF']).
    @JsonKey(name: 'unit_codes') @Default(<String>[]) List<String> unitCodes,

    /// 문항 형식('객관식'·'단답형'·'서술형' 등)·없으면 null.
    @JsonKey(name: 'question_format') String? questionFormat,

    /// 정답 형식('자연수'·'분수'·'실수'·'식' 등)·없으면 null(정답값이 아니라 형식 라벨).
    @JsonKey(name: 'answer_format') String? answerFormat,

    /// 배점·없으면 null.
    @JsonKey(name: 'points') int? points,

    /// 발문 원문(자체생성만 보유·평가원/EBS/교과서는 비어 있음).
    @JsonKey(name: 'question_text') String? questionText,

    /// 마크다운+LaTeX 발문(렌더용)·없으면 null.
    @JsonKey(name: 'question_text_md') String? questionTextMd,

    /// 도형/그래프 이미지 URI·없으면 null.
    @JsonKey(name: 'question_image_uri') String? questionImageUri,

    /// 객관식 보기(학생 대면 선택지·정답 아님)·단답형이면 null.
    @JsonKey(name: 'choices') List<String>? choices,

    /// 전체 난이도(1~5)·없으면 null.
    @JsonKey(name: 'difficulty_overall') double? difficultyOverall,
  }) = _Problem;

  factory Problem.fromJson(Map<String, dynamic> json) =>
      _$ProblemFromJson(json);
}
