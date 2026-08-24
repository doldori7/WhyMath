// MeScreen 위젯 테스트 — 학습 경로·진단 결과·성장의 증거 실 API 렌더 + 정직 신호
// (has_cycle·빈 경로·401·NO_DATA·원시 스칼라 미노출) 노출 검증 (PATH-05 · MOB-17).
//
// problemsApiProvider·growthEvidenceApiProvider를 fake로 override해 네트워크 없이 화면 동작을
// 확인한다(problem_screen_test 답습). 설정 섹션은 여전히 "준비 중"이라 그대로 남아 있는지도
// 확인한다.
import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:korean_math_app/features/problems/data/problem_models.dart';
import 'package:korean_math_app/features/problems/data/problems_api.dart';
import 'package:korean_math_app/features/profile/presentation/me_screen.dart';
import 'package:korean_math_app/features/profile/data/growth_evidence_api.dart';
import 'package:korean_math_app/features/profile/data/growth_evidence_models.dart';

/// 미리 짠 응답(또는 지정한 상태코드로 throw)을 돌려주는 fake.
class _FakeProblemsApi extends ProblemsApi {
  _FakeProblemsApi({
    this.diagnoses = const <ConceptDiagnosisItem>[],
    this.diagnosisStatusCode,
    this.learningPath,
    this.learningPathStatusCode,
  }) : super(Dio());

  final List<ConceptDiagnosisItem> diagnoses;
  final int? diagnosisStatusCode;
  final LearningPath? learningPath;
  final int? learningPathStatusCode;

  @override
  Future<List<ConceptDiagnosisItem>> getDiagnosisConcepts({int? limit}) async {
    if (diagnosisStatusCode != null) {
      throw DioException(
        requestOptions: RequestOptions(path: '/v1/me/diagnosis/concepts'),
        response: Response(
          requestOptions: RequestOptions(path: '/v1/me/diagnosis/concepts'),
          statusCode: diagnosisStatusCode,
        ),
      );
    }
    return diagnoses;
  }

  @override
  Future<LearningPath> getLearningPath(String conceptId) async {
    if (learningPathStatusCode != null) {
      throw DioException(
        requestOptions: RequestOptions(path: '/v1/me/weak-concepts/$conceptId/learning-path'),
        response: Response(
          requestOptions:
              RequestOptions(path: '/v1/me/weak-concepts/$conceptId/learning-path'),
          statusCode: learningPathStatusCode,
        ),
      );
    }
    return learningPath!;
  }
}

/// 성장의 증거 API fake.
class _FakeGrowthEvidenceApi extends GrowthEvidenceApi {
  _FakeGrowthEvidenceApi({
    this.evidence,
    this.statusCode,
  }) : super(Dio());

  final GrowthEvidenceResponse? evidence;
  final int? statusCode;

  @override
  Future<GrowthEvidenceResponse> getGrowthEvidence() async {
    if (statusCode != null) {
      throw DioException(
        requestOptions: RequestOptions(path: '/v1/me/growth-evidence'),
        response: Response(
          requestOptions: RequestOptions(path: '/v1/me/growth-evidence'),
          statusCode: statusCode,
        ),
      );
    }
    return evidence ?? _emptyGrowthEvidence();
  }
}

GrowthEvidenceResponse _emptyGrowthEvidence() => GrowthEvidenceResponse(
      verifyPassRate: _metric(status: 'no_data'),
      sessionCompletionRate: _metric(status: 'no_data'),
      helpReductionSlope: _metric(status: 'no_data'),
      helpDemandSupplyRatio: _metric(status: 'no_data'),
      transferScore: _metric(status: 'no_data'),
      hintDepthReached: _metric(status: 'no_data'),
      masteryGainRate: _metric(status: 'no_data'),
      misconceptionResolutionRate: _metric(status: 'no_data'),
      selfSolveRate: _metric(status: 'no_data'),
      calibrationBrier: const GrowthEvidenceBrierView(
        narrative: '아직 예측 확신도 데이터가 없어요.',
      ),
    );

GrowthEvidenceMetricView _metric({
  required String status,
  bool exposableNow = false,
  String? suppressedReason,
  double? rawValue,
}) =>
    GrowthEvidenceMetricView(
      status: status,
      exposableNow: exposableNow,
      suppressedReason: suppressedReason,
      rawValue: rawValue,
    );

ConceptDiagnosisItem _diag({
  String conceptId = 'c1',
  String? name = '함수의 극한',
  String? masteryLevel,
  double? bktMastery,
  double? irtTheta,
  double? irtMasteryProxy,
}) =>
    ConceptDiagnosisItem(
      conceptId: conceptId,
      conceptName: name,
      bktMastery: bktMastery,
      irtTheta: irtTheta,
      irtMasteryProxy: irtMasteryProxy,
      masteryLevel: masteryLevel,
      coaching: const DiagnosisCoaching(
        focus: 'foundation',
        rationale: '기초 개념을 다시 확인해볼까요?',
        prompt: '이 개념을 어떻게 이해하고 있나요?',
      ),
    );

Widget _wrap(
  ProblemsApi problemsApi, {
  GrowthEvidenceApi? growthApi,
}) {
  return ProviderScope(
    overrides: [
      problemsApiProvider.overrideWithValue(problemsApi),
      growthEvidenceApiProvider.overrideWithValue(
        growthApi ?? _FakeGrowthEvidenceApi(),
      ),
    ],
    child: const MaterialApp(home: MeScreen()),
  );
}

void main() {
  testWidgets('성공: 진단 결과·학습 경로·성장의 증거 데이터를 그대로 렌더한다', (tester) async {
    final api = _FakeProblemsApi(
      diagnoses: <ConceptDiagnosisItem>[
        _diag(conceptId: 'weakest', name: '함수의 극한', masteryLevel: '발전 중'),
      ],
      learningPath: const LearningPath(
        steps: <LearningStep>[
          LearningStep(position: 0, conceptId: 'p0', conceptName: '함수의 정의', depth: 1),
          LearningStep(position: 1, conceptId: 'p1', conceptName: '극한의 성질', depth: 1),
        ],
        orderingBasis: 'topological',
        orderingEdgeCount: 1,
      ),
    );
    await tester.pumpWidget(_wrap(api));
    await tester.pumpAndSettle();

    // 진단 결과 섹션.
    expect(find.text('함수의 극한'), findsOneWidget);
    expect(find.text('기초 개념을 다시 확인해볼까요?'), findsOneWidget);
    // MOB-10: 숙달 상태 라벨(서버 산출) 렌더.
    expect(find.text('발전 중'), findsOneWidget);
    // 학습 경로 섹션 — 순서대로 두 단계.
    expect(find.text('함수의 정의'), findsOneWidget);
    expect(find.text('극한의 성질'), findsOneWidget);
    // 성장의 증거 섹션 — title들이 보인다.
    expect(find.text('성장의 증거'), findsOneWidget);
    expect(find.text('풀이 검증 통과율'), findsOneWidget);
    expect(find.text('예측 확신도 보정'), findsOneWidget);
    // Brier narrative.
    expect(find.text('아직 예측 확신도 데이터가 없어요.'), findsOneWidget);
    // "준비 중" placeholder는 설정 섹션에만 남아 있어야 한다. 성장의 증거 섹션 타일이
    // 길어지면 viewport 밖으로 밀릴 수 있어 스크롤 후 확인한다.
    await tester.scrollUntilVisible(
      find.text('준비 중'),
      100.0,
      scrollable: find.byType(Scrollable),
    );
    expect(find.text('준비 중'), findsOneWidget);
  });

  testWidgets('MOB-10: mastery_level=null이면 라벨을 렌더하지 않는다(무데이터 정직 표기)',
      (tester) async {
    final api = _FakeProblemsApi(
      diagnoses: <ConceptDiagnosisItem>[_diag(name: '이차방정식')],
    );
    await tester.pumpWidget(_wrap(api));
    await tester.pumpAndSettle();

    expect(find.text('이차방정식'), findsOneWidget);
    expect(find.text('초보'), findsNothing);
    expect(find.text('발전 중'), findsNothing);
    expect(find.text('숙달'), findsNothing);
  });

  testWidgets('MOB-17: _concept_orchestration.py:86의 "초보" 폴백이 미측정 데이터로 도달하면 라벨을 숨긴다',
      (tester) async {
    final api = _FakeProblemsApi(
      diagnoses: <ConceptDiagnosisItem>[
        _diag(name: '이차방정식', masteryLevel: '초보'),
      ],
    );
    await tester.pumpWidget(_wrap(api));
    await tester.pumpAndSettle();

    expect(find.text('이차방정식'), findsOneWidget);
    // 원시 숙달 지표가 모두 null인데 mastery_level만 '초보'로 오면 폴백으로 간주해 숨긴다.
    expect(find.text('초보'), findsNothing);
  });

  testWidgets('MOB-10: 원시 BKT 확률·θ 숫자는 화면 어디에도 렌더되지 않는다', (tester) async {
    final api = _FakeProblemsApi(
      diagnoses: <ConceptDiagnosisItem>[
        _diag(name: '삼각함수', masteryLevel: '숙달', bktMastery: 0.87, irtTheta: 1.42),
      ],
    );
    await tester.pumpWidget(_wrap(api));
    await tester.pumpAndSettle();

    expect(find.text('숙달'), findsOneWidget);
    expect(find.textContaining('0.87'), findsNothing);
    expect(find.textContaining('1.42'), findsNothing);
  });

  testWidgets('빈 학습 경로(steps==0)는 정상 안내로 표시한다(에러 문구 아님)', (tester) async {
    final api = _FakeProblemsApi(
      diagnoses: <ConceptDiagnosisItem>[_diag()],
      learningPath: const LearningPath(steps: <LearningStep>[]),
    );
    await tester.pumpWidget(_wrap(api));
    await tester.pumpAndSettle();

    expect(find.textContaining('복습할 막힌 선수개념이 없어요'), findsOneWidget);
    expect(find.textContaining('불러오지 못했'), findsNothing);
  });

  testWidgets('진단 데이터 자체가 없으면 두 섹션 모두 "정상, 데이터 없음" 안내를 보인다',
      (tester) async {
    final api = _FakeProblemsApi();
    await tester.pumpWidget(_wrap(api));
    await tester.pumpAndSettle();

    expect(find.textContaining('아직 진단 데이터가 없어요'), findsNWidgets(2));
  });

  testWidgets('has_cycle=true는 순환 경고를 그대로 노출한다(삼키지 않음)', (tester) async {
    final api = _FakeProblemsApi(
      diagnoses: <ConceptDiagnosisItem>[_diag()],
      learningPath: const LearningPath(
        steps: <LearningStep>[
          LearningStep(position: 0, conceptId: 'p0', conceptName: '개념 A', depth: 1),
        ],
        hasCycle: true,
        orderingBasis: 'tiebreak_only',
      ),
    );
    await tester.pumpWidget(_wrap(api));
    await tester.pumpAndSettle();

    expect(find.textContaining('순환 구조가 감지'), findsOneWidget);
    // 순환이 있어도 단계 자체는 계속 보인다(잔여로라도 정직하게 보여줌).
    expect(find.text('개념 A'), findsOneWidget);
  });

  testWidgets('401(미인증)은 로그인 필요 안내로 명확히 구분한다(일반 오류 문구 아님)', (tester) async {
    final api = _FakeProblemsApi(diagnosisStatusCode: 401);
    await tester.pumpWidget(_wrap(api));
    await tester.pumpAndSettle();

    // 학습 경로·진단 결과·성장의 증거 세 섹션 모두.
    expect(find.text('로그인이 필요해요.'), findsNWidgets(3));
    expect(find.textContaining('불러오지 못했'), findsNothing);
    expect(find.textContaining('오류가 발생'), findsNothing);
  });

  testWidgets('학습 경로만 일반 실패(401 외)면 재시도 버튼과 함께 error로 표시한다', (tester) async {
    final api = _FakeProblemsApi(
      diagnoses: <ConceptDiagnosisItem>[_diag()],
      learningPathStatusCode: 500,
    );
    await tester.pumpWidget(_wrap(api));
    await tester.pumpAndSettle();

    expect(find.textContaining('학습 경로를 불러오지 못했어요'), findsOneWidget);
    expect(find.widgetWithText(TextButton, '다시 시도'), findsOneWidget);
    // 진단 결과 섹션은 정상 렌더돼야 한다(섹션 독립성).
    expect(find.text('함수의 극한'), findsOneWidget);
    // 성장의 증거 섹션도 정상 렌더돼야 한다(섹션 독립성).
    expect(find.text('성장의 증거'), findsOneWidget);
  });

  // ── PATH-10: ordering_basis 렌더 착지 ─────────────────────────────────────
  // PATH-02가 응답에 실어 보낸 정직 표기를 화면이 읽지 않던 문제(파싱만 하고 읽는 위젯 0개).
  // 실측상 기본 파라미터에서 96.4%가 tiebreak_only인데, 그때 학생은 "근거 있는 순서"와
  // 구별할 수 없었다. 대칭 사례인 has_cycle은 발생률 0%인데도 원래부터 렌더되고 있었다.

  /// 두 basis fixture가 공유하는 **완전히 동일한** steps — 변별력 테스트의 전제.
  const sharedSteps = <LearningStep>[
    LearningStep(position: 0, conceptId: 'p0', conceptName: '함수의 정의', depth: 1),
    LearningStep(position: 1, conceptId: 'p1', conceptName: '극한의 성질', depth: 1),
  ];

  testWidgets('PATH-10: tiebreak_only면 순서가 참고용임을 화면이 알린다(삼키지 않음)', (tester) async {
    final api = _FakeProblemsApi(
      diagnoses: <ConceptDiagnosisItem>[_diag()],
      learningPath: const LearningPath(
        steps: sharedSteps,
        orderingBasis: 'tiebreak_only',
        orderingEdgeCount: 0,
      ),
    );
    await tester.pumpWidget(_wrap(api));
    await tester.pumpAndSettle();

    expect(find.textContaining('참고용'), findsOneWidget);
    // 단계 자체는 그대로 보인다(표기를 붙였다고 경로를 숨기지 않는다).
    expect(find.text('함수의 정의'), findsOneWidget);
    expect(find.text('극한의 성질'), findsOneWidget);
  });

  testWidgets('PATH-10 변별력: steps가 동일해도 basis가 다르면 화면 텍스트가 갈린다', (tester) async {
    /// 같은 tester에서 화면을 갈아끼운다. 사이에 빈 트리를 한 번 pump해 이전 ProviderScope를
    /// 확실히 폐기한다 — 그러지 않으면 Flutter가 엘리먼트 트리를 재사용해 두 번째 상태가
    /// 반영되지 않고, 그 결과 "두 경우가 같다"는 *거짓 통과*가 난다(이 테스트 자체가 위장이 됨).
    Future<void> renderWith(String basis, int edgeCount) async {
      await tester.pumpWidget(const SizedBox.shrink());
      await tester.pumpAndSettle();
      await tester.pumpWidget(_wrap(_FakeProblemsApi(
        diagnoses: <ConceptDiagnosisItem>[_diag()],
        learningPath: LearningPath(
          steps: sharedSteps,
          orderingBasis: basis,
          orderingEdgeCount: edgeCount,
        ),
      )));
      await tester.pumpAndSettle();
    }

    // ① topological — 제약 엣지가 실제로 순서를 정했으므로 참고용 표기가 없어야 한다.
    await renderWith('topological', 3);
    expect(find.textContaining('참고용'), findsNothing);
    // 전제 확인: 단계는 정상 렌더된다(문구 부재가 렌더 실패 때문이 아님).
    expect(find.text('함수의 정의'), findsOneWidget);

    // ② tiebreak_only — steps는 ①과 완전히 동일한데 표기가 나타나야 한다.
    await renderWith('tiebreak_only', 0);
    expect(find.textContaining('참고용'), findsOneWidget);
    expect(find.text('함수의 정의'), findsOneWidget);
  });

  testWidgets('PATH-10 어조·반게임화: 문구는 학생이 아니라 데이터 한계를 말하고 숫자·연출이 없다',
      (tester) async {
    final api = _FakeProblemsApi(
      diagnoses: <ConceptDiagnosisItem>[_diag()],
      learningPath: const LearningPath(
        steps: sharedSteps,
        orderingBasis: 'tiebreak_only',
        orderingEdgeCount: 0,
      ),
    );
    await tester.pumpWidget(_wrap(api));
    await tester.pumpAndSettle();

    // 어조: 학생의 부족·실패를 지적하는 표현이 없다(CLAUDE.md 부정 피드백 강화 금지).
    for (final blamed in <String>['부족', '못했', '틀렸', '실패', '미달']) {
      expect(find.textContaining(blamed), findsNothing);
    }
    // 반게임화(전역 UI 불변식 2): 랭킹·스트릭·카운트다운·보상 연출 0.
    // 단일 음절('점'·'등'·'위')은 쓰지 않는다 — 섹션 부제 "강점·약점 개념 분석" 같은
    // 평범한 한국어에 오탐한다. 실제로 게임화 UI에만 나타나는 어구로만 검사한다.
    for (final gamified in <String>[
      '랭킹',
      '순위',
      '스트릭',
      '연속 학습',
      '일째',
      '포인트',
      '배지',
      '레벨',
      '축하',
      '남았어',
    ]) {
      expect(find.textContaining(gamified), findsNothing);
    }
    // 범위 밖(⑥): orderingEdgeCount 숫자는 학생에게 노출하지 않는다.
    expect(find.textContaining('엣지'), findsNothing);
    expect(find.textContaining('제약'), findsNothing);
    // 진척 연출(게이지·프로그레스바)도 이 섹션에 없다.
    expect(find.byType(LinearProgressIndicator), findsNothing);
  });

  testWidgets('PATH-10 정직 신호 전수: 네 신호가 모두 화면에 도달한다(다음 재작성 누락 방지)',
      (tester) async {
    // ① steps.isEmpty — "막힌 선수개념 없음"이 정상 결과로 표시된다.
    await tester.pumpWidget(_wrap(_FakeProblemsApi(
      diagnoses: <ConceptDiagnosisItem>[_diag()],
      learningPath: const LearningPath(steps: <LearningStep>[]),
    )));
    await tester.pumpAndSettle();
    expect(find.textContaining('복습할 막힌 선수개념이 없어요'), findsOneWidget);

    // ②hasCycle ③isCycleResidual ④orderingBasis — 한 경로에서 셋이 동시에 도달한다.
    // 화면을 갈아끼우기 전에 빈 트리를 pump해 이전 ProviderScope를 폐기한다(트리 재사용 방지).
    await tester.pumpWidget(const SizedBox.shrink());
    await tester.pumpAndSettle();
    await tester.pumpWidget(_wrap(_FakeProblemsApi(
      diagnoses: <ConceptDiagnosisItem>[_diag()],
      learningPath: const LearningPath(
        steps: <LearningStep>[
          LearningStep(
            position: 0,
            conceptId: 'p0',
            conceptName: '개념 A',
            depth: 1,
            isCycleResidual: true,
          ),
        ],
        hasCycle: true,
        orderingBasis: 'tiebreak_only',
      ),
    )));
    await tester.pumpAndSettle();
    expect(find.textContaining('순환 구조가 감지'), findsOneWidget); // ②
    expect(find.text('순환 잔여 단계'), findsOneWidget); // ③
    expect(find.textContaining('참고용이에요'), findsOneWidget); // ④
  });

  // ── MOB-17: 성장의 증거 섹션 추가 검증 ──────────────────────────────────────

  testWidgets('MOB-17: NO_DATA·suppressed_reason을 숨기지 않고 서술로 보인다', (tester) async {
    const reason = '아직 이 지표를 계산할 데이터가 모아지지 않았어요.';
    final growthApi = _FakeGrowthEvidenceApi(
      evidence: GrowthEvidenceResponse(
        verifyPassRate: _metric(
          status: 'no_data',
          exposableNow: false,
          suppressedReason: reason,
        ),
        sessionCompletionRate: _metric(status: 'no_data'),
        helpReductionSlope: _metric(status: 'no_data'),
        helpDemandSupplyRatio: _metric(status: 'no_data'),
        transferScore: _metric(status: 'no_data'),
        hintDepthReached: _metric(status: 'no_data'),
        masteryGainRate: _metric(status: 'no_data'),
        misconceptionResolutionRate: _metric(status: 'no_data'),
        selfSolveRate: _metric(status: 'no_data'),
        calibrationBrier: const GrowthEvidenceBrierView(
          narrative: '아직 예측 확신도 데이터가 없어요.',
        ),
      ),
    );
    final api = _FakeProblemsApi(
      diagnoses: <ConceptDiagnosisItem>[_diag()],
      learningPath: const LearningPath(steps: <LearningStep>[]),
    );
    await tester.pumpWidget(_wrap(api, growthApi: growthApi));
    await tester.pumpAndSettle();

    expect(find.text(reason), findsOneWidget);
    expect(find.text('성장의 증거'), findsOneWidget);
  });

  testWidgets('MOB-17: 원시 스칼라(value)는 화면에 노출되지 않는다', (tester) async {
    final growthApi = _FakeGrowthEvidenceApi(
      evidence: GrowthEvidenceResponse(
        verifyPassRate: _metric(
          status: 'measured',
          exposableNow: true,
          rawValue: 0.87,
        ),
        sessionCompletionRate: _metric(status: 'no_data'),
        helpReductionSlope: _metric(status: 'no_data'),
        helpDemandSupplyRatio: _metric(status: 'no_data'),
        transferScore: _metric(status: 'no_data'),
        hintDepthReached: _metric(status: 'no_data'),
        masteryGainRate: _metric(status: 'no_data'),
        misconceptionResolutionRate: _metric(status: 'no_data'),
        selfSolveRate: _metric(status: 'no_data'),
        calibrationBrier: const GrowthEvidenceBrierView(
          narrative: '아직 예측 확신도 데이터가 없어요.',
        ),
      ),
    );
    final api = _FakeProblemsApi(
      diagnoses: <ConceptDiagnosisItem>[_diag()],
      learningPath: const LearningPath(steps: <LearningStep>[]),
    );
    await tester.pumpWidget(_wrap(api, growthApi: growthApi));
    await tester.pumpAndSettle();

    expect(find.text('measured'), findsOneWidget); // status는 그대로 노출.
    expect(find.textContaining('0.87'), findsNothing); // value는 노출 금지.
    expect(find.textContaining('87'), findsNothing);
  });

  testWidgets('MOB-17: Brier는 narrative만 보이고 원 스칼라는 없다', (tester) async {
    const narrative = '네 예측이 실제 정답과 꽤 잘 맞고 있어요.';
    final growthApi = _FakeGrowthEvidenceApi(
      evidence: GrowthEvidenceResponse(
        verifyPassRate: _metric(status: 'no_data'),
        sessionCompletionRate: _metric(status: 'no_data'),
        helpReductionSlope: _metric(status: 'no_data'),
        helpDemandSupplyRatio: _metric(status: 'no_data'),
        transferScore: _metric(status: 'no_data'),
        hintDepthReached: _metric(status: 'no_data'),
        masteryGainRate: _metric(status: 'no_data'),
        misconceptionResolutionRate: _metric(status: 'no_data'),
        selfSolveRate: _metric(status: 'no_data'),
        calibrationBrier: const GrowthEvidenceBrierView(narrative: narrative),
      ),
    );
    final api = _FakeProblemsApi(
      diagnoses: <ConceptDiagnosisItem>[_diag()],
      learningPath: const LearningPath(steps: <LearningStep>[]),
    );
    await tester.pumpWidget(_wrap(api, growthApi: growthApi));
    await tester.pumpAndSettle();

    expect(find.text(narrative), findsOneWidget);
  });

  testWidgets('MOB-17: 성장의 증거만 일반 실패(401 외)면 재시도 버튼과 함께 error로 표시한다',
      (tester) async {
    final api = _FakeProblemsApi(
      diagnoses: <ConceptDiagnosisItem>[_diag()],
      learningPath: const LearningPath(steps: <LearningStep>[]),
    );
    final growthApi = _FakeGrowthEvidenceApi(statusCode: 500);
    await tester.pumpWidget(_wrap(api, growthApi: growthApi));
    await tester.pumpAndSettle();

    expect(find.textContaining('성장의 증거를 불러오지 못했어요'), findsOneWidget);
    expect(find.widgetWithText(TextButton, '다시 시도'), findsOneWidget);
    // 다른 섹션은 정상 렌더돼야 한다(섹션 독립성).
    expect(find.text('함수의 극한'), findsOneWidget);
  });
}
