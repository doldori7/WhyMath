// MeTabController 테스트 — 진단 결과·학습 경로·성장의 증거 로드·정직 신호 분리 검증
// (PATH-05 · MOB-17).
//
// 네트워크를 타지 않는다 — problemsApiProvider·growthEvidenceApiProvider를 미리 짠 응답
// (또는 401/일반 throw)을 돌려주는 fake로 override한다. 컨트롤러는 순수 상태 전이라 결과를
// 직접 검증한다.
import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:korean_math_app/features/problems/data/problem_models.dart';
import 'package:korean_math_app/features/problems/data/problems_api.dart';
import 'package:korean_math_app/features/profile/application/me_tab_controller.dart';
import 'package:korean_math_app/features/profile/application/me_tab_state.dart';
import 'package:korean_math_app/features/profile/data/growth_evidence_api.dart';
import 'package:korean_math_app/features/profile/data/growth_evidence_models.dart';

/// 미리 짠 응답(또는 지정한 상태코드로 throw)을 돌려주는 fake.
class _FakeProblemsApi extends ProblemsApi {
  _FakeProblemsApi({
    this.diagnoses = const <ConceptDiagnosisItem>[],
    this.diagnosisStatusCode,
    this.diagnosisThrowsGeneric = false,
    this.learningPath,
    this.learningPathStatusCode,
    this.learningPathThrowsGeneric = false,
  }) : super(Dio());

  final List<ConceptDiagnosisItem> diagnoses;
  final int? diagnosisStatusCode;
  final bool diagnosisThrowsGeneric;

  final LearningPath? learningPath;
  final int? learningPathStatusCode;
  final bool learningPathThrowsGeneric;

  int diagnosisCalls = 0;
  int learningPathCalls = 0;
  String? lastLearningPathConceptId;

  @override
  Future<List<ConceptDiagnosisItem>> getDiagnosisConcepts({int? limit}) async {
    diagnosisCalls++;
    if (diagnosisStatusCode != null) {
      throw DioException(
        requestOptions: RequestOptions(path: '/v1/me/diagnosis/concepts'),
        response: Response(
          requestOptions: RequestOptions(path: '/v1/me/diagnosis/concepts'),
          statusCode: diagnosisStatusCode,
        ),
      );
    }
    if (diagnosisThrowsGeneric) {
      throw Exception('네트워크 실패(테스트)');
    }
    return diagnoses;
  }

  @override
  Future<LearningPath> getLearningPath(String conceptId) async {
    learningPathCalls++;
    lastLearningPathConceptId = conceptId;
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
    if (learningPathThrowsGeneric) {
      throw Exception('네트워크 실패(테스트)');
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

  int calls = 0;

  @override
  Future<GrowthEvidenceResponse> getGrowthEvidence() async {
    calls++;
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

/// 성장의 증거 API fake — 401 외 일반 실패용.
class _FakeGrowthEvidenceApiFailing extends GrowthEvidenceApi {
  _FakeGrowthEvidenceApiFailing() : super(Dio());

  int calls = 0;

  @override
  Future<GrowthEvidenceResponse> getGrowthEvidence() async {
    calls++;
    throw Exception('네트워크 실패(테스트)');
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

ConceptDiagnosisItem _diag({String conceptId = 'c1', String? name = '함수의 극한'}) =>
    ConceptDiagnosisItem(
      conceptId: conceptId,
      conceptName: name,
      coaching: const DiagnosisCoaching(
        focus: 'foundation',
        rationale: '기초 개념을 다시 확인해볼까요?',
        prompt: '이 개념을 어떻게 이해하고 있나요?',
      ),
    );

LearningStep _step({int position = 0, String name = '함수의 정의'}) => LearningStep(
      position: position,
      conceptId: 'p$position',
      conceptName: name,
      depth: 1,
    );

ProviderContainer _containerWith(
  ProblemsApi problemsApi, {
  GrowthEvidenceApi? growthApi,
}) {
  final container = ProviderContainer(
    overrides: [
      problemsApiProvider.overrideWithValue(problemsApi),
      growthEvidenceApiProvider.overrideWithValue(
        growthApi ?? _FakeGrowthEvidenceApi(),
      ),
    ],
  );
  addTearDown(container.dispose);
  return container;
}

void main() {
  group('MeTabController.load — 성공', () {
    test('진단 목록 + 가장 약한 개념(첫 항목)의 학습 경로 + 성장의 증거를 함께 로드한다',
        () async {
      final api = _FakeProblemsApi(
        diagnoses: <ConceptDiagnosisItem>[
          _diag(conceptId: 'weakest', name: '함수의 극한'),
        ],
        learningPath: LearningPath(
          steps: <LearningStep>[_step(position: 0), _step(position: 1, name: '극한의 성질')],
          orderingBasis: 'topological',
          orderingEdgeCount: 1,
        ),
      );
      final growthApi = _FakeGrowthEvidenceApi();
      final container = _containerWith(api, growthApi: growthApi);

      await container.read(meTabControllerProvider.notifier).load();

      final s = container.read(meTabControllerProvider);
      expect(s.diagnosisStatus, SectionStatus.loaded);
      expect(s.diagnoses, hasLength(1));
      expect(s.learningPathStatus, SectionStatus.loaded);
      expect(s.learningPath?.steps, hasLength(2));
      expect(s.learningPath?.hasCycle, isFalse);
      expect(s.learningPathConceptName, '함수의 극한');
      expect(api.lastLearningPathConceptId, 'weakest'); // 가장 약한(첫) 개념으로 조회.
      expect(s.growthEvidenceStatus, SectionStatus.loaded);
      expect(s.growthEvidence, isNotNull);
      expect(growthApi.calls, 1); // MOB-17: 실제로 /v1/me/growth-evidence를 부른다.
    });

    test('성장의 증거 응답을 상태에 그대로 보관한다', () async {
      const customReason = '아직 이 지표는 준비 중이에요.';
      final evidence = GrowthEvidenceResponse(
        verifyPassRate: _metric(status: 'no_data', suppressedReason: customReason),
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
      final growthApi = _FakeGrowthEvidenceApi(evidence: evidence);
      final api = _FakeProblemsApi(
        diagnoses: <ConceptDiagnosisItem>[_diag()],
        learningPath: const LearningPath(steps: <LearningStep>[]),
      );
      final container = _containerWith(api, growthApi: growthApi);

      await container.read(meTabControllerProvider.notifier).load();

      final s = container.read(meTabControllerProvider);
      expect(s.growthEvidenceStatus, SectionStatus.loaded);
      expect(s.growthEvidence?.verifyPassRate.suppressedReason, customReason);
    });
  });

  group('MeTabController.load — 정직 신호: 빈 경로', () {
    test('진단은 있으나 학습 경로 steps가 0건이면 정상 loaded로 표시한다(에러 아님)', () async {
      final api = _FakeProblemsApi(
        diagnoses: <ConceptDiagnosisItem>[_diag()],
        learningPath: const LearningPath(steps: <LearningStep>[]),
      );
      final container = _containerWith(api);

      await container.read(meTabControllerProvider.notifier).load();

      final s = container.read(meTabControllerProvider);
      expect(s.learningPathStatus, SectionStatus.loaded);
      expect(s.learningPath?.steps, isEmpty);
      expect(s.learningPathError, isNull); // 빈 경로는 오류 메시지가 아니다.
      expect(s.growthEvidenceStatus, SectionStatus.loaded);
    });

    test('진단 목록 자체가 비어 있으면 학습 경로는 대상 없음(null)으로 loaded 처리한다', () async {
      final api = _FakeProblemsApi(diagnoses: const <ConceptDiagnosisItem>[]);
      final growthApi = _FakeGrowthEvidenceApi();
      final container = _containerWith(api, growthApi: growthApi);

      await container.read(meTabControllerProvider.notifier).load();

      final s = container.read(meTabControllerProvider);
      expect(s.diagnosisStatus, SectionStatus.loaded);
      expect(s.diagnoses, isEmpty);
      expect(s.learningPathStatus, SectionStatus.loaded);
      expect(s.learningPath, isNull);
      expect(api.learningPathCalls, 0); // 대상이 없으니 호출 자체를 안 한다.
      expect(s.growthEvidenceStatus, SectionStatus.loaded);
      expect(growthApi.calls, 1); // 진단이 비어도 성장의 증거는 독립적으로 조회.
    });
  });

  group('MeTabController.load — 정직 신호: has_cycle', () {
    test('has_cycle=true를 그대로 상태에 보관한다(가공·삼킴 없음)', () async {
      final api = _FakeProblemsApi(
        diagnoses: <ConceptDiagnosisItem>[_diag()],
        learningPath: LearningPath(
          steps: <LearningStep>[_step(position: 0)],
          hasCycle: true,
          orderingBasis: 'tiebreak_only',
        ),
      );
      final container = _containerWith(api);

      await container.read(meTabControllerProvider.notifier).load();

      final s = container.read(meTabControllerProvider);
      expect(s.learningPathStatus, SectionStatus.loaded);
      expect(s.learningPath?.hasCycle, isTrue);
      expect(s.growthEvidenceStatus, SectionStatus.loaded);
    });
  });

  group('MeTabController.load — 정직 신호: 401(미인증)', () {
    test('진단 조회 401이면 세 섹션 모두 unauthenticated로 표시한다(일반 error와 분리)',
        () async {
      final api = _FakeProblemsApi(diagnosisStatusCode: 401);
      final growthApi = _FakeGrowthEvidenceApi();
      final container = _containerWith(api, growthApi: growthApi);

      await container.read(meTabControllerProvider.notifier).load();

      final s = container.read(meTabControllerProvider);
      expect(s.diagnosisStatus, SectionStatus.unauthenticated);
      expect(s.learningPathStatus, SectionStatus.unauthenticated);
      expect(s.growthEvidenceStatus, SectionStatus.unauthenticated);
      expect(s.diagnosisError, isNull); // unauthenticated는 error 문구가 아니라 전용 상태.
      expect(growthApi.calls, 0); // 진단이 막혔으니 성장의 증거도 시도조차 안 한다.
    });

    test('성장의 증거 조회만 401이면 진단·학습 경로는 정상 loaded, 성장의 증거만 unauthenticated',
        () async {
      final api = _FakeProblemsApi(
        diagnoses: <ConceptDiagnosisItem>[_diag()],
        learningPath: const LearningPath(steps: <LearningStep>[]),
      );
      final growthApi = _FakeGrowthEvidenceApi(statusCode: 401);
      final container = _containerWith(api, growthApi: growthApi);

      await container.read(meTabControllerProvider.notifier).load();

      final s = container.read(meTabControllerProvider);
      expect(s.diagnosisStatus, SectionStatus.loaded);
      expect(s.learningPathStatus, SectionStatus.loaded);
      expect(s.growthEvidenceStatus, SectionStatus.unauthenticated);
      expect(s.growthEvidenceError, isNull);
    });

    test('학습 경로 조회만 401이면 진단·성장의 증거는 loaded, 학습 경로만 unauthenticated',
        () async {
      final api = _FakeProblemsApi(
        diagnoses: <ConceptDiagnosisItem>[_diag()],
        learningPathStatusCode: 401,
      );
      final container = _containerWith(api);

      await container.read(meTabControllerProvider.notifier).load();

      final s = container.read(meTabControllerProvider);
      expect(s.diagnosisStatus, SectionStatus.loaded);
      expect(s.learningPathStatus, SectionStatus.unauthenticated);
      expect(s.learningPathError, isNull);
      expect(s.growthEvidenceStatus, SectionStatus.loaded);
    });
  });

  group('MeTabController.load — 일반 실패(401 외)', () {
    test('진단 조회 네트워크 실패는 error로 기록하고 학습 경로·성장의 증거는 의존 실패로 error 처리한다',
        () async {
      final api = _FakeProblemsApi(diagnosisThrowsGeneric: true);
      final container = _containerWith(api);

      await container.read(meTabControllerProvider.notifier).load();

      final s = container.read(meTabControllerProvider);
      expect(s.diagnosisStatus, SectionStatus.error);
      expect(s.diagnosisError, isNotNull);
      expect(s.learningPathStatus, SectionStatus.error);
      expect(s.learningPathError, isNotNull);
      expect(s.growthEvidenceStatus, SectionStatus.error);
      expect(s.growthEvidenceError, isNotNull);
      expect(s.diagnosisStatus, isNot(SectionStatus.unauthenticated));
    });

    test('학습 경로 조회만 네트워크 실패면 진단은 loaded, 학습 경로만 error, 성장의 증거는 loaded',
        () async {
      final api = _FakeProblemsApi(
        diagnoses: <ConceptDiagnosisItem>[_diag()],
        learningPathThrowsGeneric: true,
      );
      final container = _containerWith(api);

      await container.read(meTabControllerProvider.notifier).load();

      final s = container.read(meTabControllerProvider);
      expect(s.diagnosisStatus, SectionStatus.loaded);
      expect(s.learningPathStatus, SectionStatus.error);
      expect(s.learningPathError, isNotNull);
      expect(s.growthEvidenceStatus, SectionStatus.loaded);
    });

    test('성장의 증거 조회만 네트워크 실패면 진단·학습 경로는 loaded, 성장의 증거만 error',
        () async {
      final api = _FakeProblemsApi(
        diagnoses: <ConceptDiagnosisItem>[_diag()],
        learningPath: const LearningPath(steps: <LearningStep>[]),
      );
      final growthApi = _FakeGrowthEvidenceApiFailing();
      final container = _containerWith(api, growthApi: growthApi);

      await container.read(meTabControllerProvider.notifier).load();

      final s = container.read(meTabControllerProvider);
      expect(s.diagnosisStatus, SectionStatus.loaded);
      expect(s.learningPathStatus, SectionStatus.loaded);
      expect(s.growthEvidenceStatus, SectionStatus.error);
      expect(s.growthEvidenceError, isNotNull);
    });
  });

  group('MeTabController.load — 재진입', () {
    test('조회 중 재호출은 무시한다(중복 호출 방지)', () async {
      final api = _FakeProblemsApi(
        diagnoses: <ConceptDiagnosisItem>[_diag()],
        learningPath: const LearningPath(steps: <LearningStep>[]),
      );
      final growthApi = _FakeGrowthEvidenceApi();
      final container = _containerWith(api, growthApi: growthApi);
      final notifier = container.read(meTabControllerProvider.notifier);

      final first = notifier.load();
      final second = notifier.load(); // isLoading 중이라 즉시 반환돼야 함.
      await Future.wait(<Future<void>>[first, second]);

      expect(api.diagnosisCalls, 1);
      expect(growthApi.calls, 1);
    });
  });
}
