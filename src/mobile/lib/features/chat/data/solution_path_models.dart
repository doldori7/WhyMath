// 풀이 경로 단계 조회 응답 모델 — `GET /v1/solution-paths/{id}/steps?up_to=n`(SOL-02) 계약을
// *구조 그대로* 옮긴다.
//
// 경계(CLAUDE.md·표현≠의미): 이 클래스들은 *수신 컨테이너*일 뿐이다. 단계 내용의 생성·검증
// (SymPy 동치·PRM)은 전부 서버(L3/L4)에 있고, 클라는 검증된 단계를 받아 렌더만 한다.
//
// 교수학 경계(SOL-02 acceptance ⑤·협상 불가): reveal_policy='deferred' — 서버는 요청한
// `up_to`까지만 단계를 내려주고(서버 측 점층 공개), 클라는 학생이 스스로 펼친 만큼만 요청한다.
// 따라서 미펼침 단계의 내용은 이 모델 인스턴스에 *애초에 존재하지 않는다*.
import 'package:freezed_annotation/freezed_annotation.dart';

part 'solution_path_models.freezed.dart';
part 'solution_path_models.g.dart';

/// 풀이 경로의 단계 1개 — 순서 + 자연어/LaTeX 혼합 내용.
///
/// `content`는 서버 원문(LaTeX·표기 포함)이다. 학생 표면에 보낼 때는 렌더 시점에 MATH-05
/// 정본 `latexToPlainSolution`을 거친다(원문 LaTeX 노출 금지).
@freezed
abstract class SolutionStep with _$SolutionStep {
  const factory SolutionStep({
    /// 단계 순서(1-base·서버 정본 순서).
    @JsonKey(name: 'step_order') required int stepOrder,

    /// 단계 내용 원문(자연어+LaTeX/표기 — 렌더 시 평문 표기로 변환).
    @JsonKey(name: 'content') required String content,
  }) = _SolutionStep;

  factory SolutionStep.fromJson(Map<String, dynamic> json) =>
      _$SolutionStepFromJson(json);
}

/// 단계 조회 응답 1페이지 — 지금까지 펼친 단계 목록 + 전체 단계 수.
///
/// `total`은 위치 정보("단계 2/5")로만 쓴다 — 점수·등급이 아니다(SOL-02 ⑤ 점수 노출 0).
@freezed
abstract class SolutionStepsPage with _$SolutionStepsPage {
  const factory SolutionStepsPage({
    /// 지금까지 펼친 단계(1..upTo·step_order 오름차순).
    @JsonKey(name: 'steps') @Default(<SolutionStep>[]) List<SolutionStep> steps,

    /// 풀이 경로의 전체 단계 수(위치 표시용·점수 아님).
    @JsonKey(name: 'total') required int total,

    /// 서버가 실제로 공개한 마지막 단계 번호(요청한 up_to와 동일하게 온다).
    @JsonKey(name: 'up_to') required int upTo,
  }) = _SolutionStepsPage;

  factory SolutionStepsPage.fromJson(Map<String, dynamic> json) =>
      _$SolutionStepsPageFromJson(json);
}
