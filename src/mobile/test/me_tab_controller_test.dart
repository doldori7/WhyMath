// MeTabController 테스트 — 진단 결과→학습 경로 순차 로드·정직 신호(401·has_cycle·빈 경로)
// 분리 검증 (PATH-05).
//
// 네트워크를 타지 않는다 — problemsApiProvider를 미리 짠 응답(또는 401/일반 throw)을 돌려주는
// fake로 override한다(diagnosis_controller_test 답습). 컨트롤러는 순수 상태 전이라 결과를
// 직접 검증한다.
import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:korean_math_app/features/problems/data/problem_models.dart';
import 'package:korean_math_app/features/problems/data/problems_api.dart';
import 'package:korean_math_app/features/profile/application/me_tab_controller.dart';
import 'package:korean_math_app/features/profile/application/me_tab_state.dart';

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

ProviderContainer _containerWith(ProblemsApi api) {
  final container = ProviderContainer(
    overrides: [problemsApiProvider.overrideWithValue(api)],
  );
  addTearDown(container.dispose);
  return container;
}

void main() {
  group('MeTabController.load — 성공', () {
    test('진단 목록 + 가장 약한 개념(첫 항목)의 학습 경로를 함께 로드한다', () async {
      final api = _FakeProblemsApi(
        diagnoses: <ConceptDiagnosisItem>[_diag(conceptId: 'weakest', name: '함수의 극한')],
        learningPath: LearningPath(
          steps: <LearningStep>[_step(position: 0), _step(position: 1, name: '극한의 성질')],
          orderingBasis: 'topological',
          orderingEdgeCount: 1,
        ),
      );
      final container = _containerWith(api);

      await container.read(meTabControllerProvider.notifier).load();

      final s = container.read(meTabControllerProvider);
      expect(s.diagnosisStatus, SectionStatus.loaded);
      expect(s.diagnoses, hasLength(1));
      expect(s.learningPathStatus, SectionStatus.loaded);
      expect(s.learningPath?.steps, hasLength(2));
      expect(s.learningPath?.hasCycle, isFalse);
      expect(s.learningPathConceptName, '함수의 극한');
      expect(api.lastLearningPathConceptId, 'weakest'); // 가장 약한(첫) 개념으로 조회.
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
    });

    test('진단 목록 자체가 비어 있으면 학습 경로는 대상 없음(null)으로 loaded 처리한다', () async {
      final api = _FakeProblemsApi(diagnoses: const <ConceptDiagnosisItem>[]);
      final container = _containerWith(api);

      await container.read(meTabControllerProvider.notifier).load();

      final s = container.read(meTabControllerProvider);
      expect(s.diagnosisStatus, SectionStatus.loaded);
      expect(s.diagnoses, isEmpty);
      expect(s.learningPathStatus, SectionStatus.loaded);
      expect(s.learningPath, isNull);
      expect(api.learningPathCalls, 0); // 대상이 없으니 호출 자체를 안 한다.
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
    });
  });

  group('MeTabController.load — 정직 신호: 401(미인증)', () {
    test('진단 조회 401이면 두 섹션 모두 unauthenticated로 표시한다(일반 error와 분리)', () async {
      final api = _FakeProblemsApi(diagnosisStatusCode: 401);
      final container = _containerWith(api);

      await container.read(meTabControllerProvider.notifier).load();

      final s = container.read(meTabControllerProvider);
      expect(s.diagnosisStatus, SectionStatus.unauthenticated);
      expect(s.learningPathStatus, SectionStatus.unauthenticated);
      expect(s.diagnosisError, isNull); // unauthenticated는 error 문구가 아니라 전용 상태.
      expect(api.learningPathCalls, 0); // 진단이 막혔으니 학습 경로는 시도조차 안 한다.
    });

    test('학습 경로 조회만 401이면 진단은 정상 loaded, 학습 경로만 unauthenticated', () async {
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
    });
  });

  group('MeTabController.load — 일반 실패(401 외)', () {
    test('진단 조회 네트워크 실패는 error로 기록하고 학습 경로는 의존 실패로 error 처리한다', () async {
      final api = _FakeProblemsApi(diagnosisThrowsGeneric: true);
      final container = _containerWith(api);

      await container.read(meTabControllerProvider.notifier).load();

      final s = container.read(meTabControllerProvider);
      expect(s.diagnosisStatus, SectionStatus.error);
      expect(s.diagnosisError, isNotNull);
      expect(s.learningPathStatus, SectionStatus.error);
      expect(s.learningPathError, isNotNull);
      expect(s.diagnosisStatus, isNot(SectionStatus.unauthenticated));
    });

    test('학습 경로 조회만 네트워크 실패면 진단은 loaded, 학습 경로만 error', () async {
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
    });
  });

  group('MeTabController.load — 재진입', () {
    test('조회 중 재호출은 무시한다(중복 호출 방지)', () async {
      final api = _FakeProblemsApi(
        diagnoses: <ConceptDiagnosisItem>[_diag()],
        learningPath: const LearningPath(steps: <LearningStep>[]),
      );
      final container = _containerWith(api);
      final notifier = container.read(meTabControllerProvider.notifier);

      final first = notifier.load();
      final second = notifier.load(); // isLoading 중이라 즉시 반환돼야 함.
      await Future.wait(<Future<void>>[first, second]);

      expect(api.diagnosisCalls, 1);
    });
  });
}
