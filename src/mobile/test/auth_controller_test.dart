// AuthController 단위테스트 — code 교환→토큰 저장→상태·로그아웃. OAuth-c1.
//
// 네트워크·플랫폼 채널 없이: fake AuthApi + fake TokenStore를 provider override로 주입한다
// (chat_controller_test 패턴). 토큰 발급·저장의 *배선*만 검증 — 수학·인증 결정은 서버.
import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:korean_math_app/core/token_store.dart';
import 'package:korean_math_app/features/auth/application/auth_controller.dart';
import 'package:korean_math_app/features/auth/data/auth_api.dart';
import 'package:korean_math_app/features/chat/application/chat_controller.dart';
import 'package:korean_math_app/features/chat/data/coach_api.dart';
import 'package:korean_math_app/features/chat/data/coach_models.dart';
import 'package:korean_math_app/features/problems/application/active_problem.dart';
import 'package:korean_math_app/features/problems/data/problem_models.dart';

class _FakeAuthApi extends AuthApi {
  _FakeAuthApi({this.token, this.shouldThrow = false}) : super(Dio());

  final String? token;
  final bool shouldThrow;

  @override
  Future<String> login({
    required String provider,
    required String code,
    required String redirectUri,
  }) async {
    if (shouldThrow) {
      throw DioException(
        requestOptions: RequestOptions(path: '/v1/auth/$provider/callback'),
        error: '네트워크 실패(테스트)',
      );
    }
    return token!;
  }
}

class _FakeTokenStore implements TokenStore {
  String? saved;
  bool cleared = false;

  @override
  Future<String?> readAccessToken() async => saved;

  @override
  Future<void> saveAccessToken(String token) async => saved = token;

  @override
  Future<void> clear() async {
    saved = null;
    cleared = true;
  }
}

/// 읽기에서 오류를 던지는 TokenStore — restore()의 방어적 처리(앱 안 죽음)를 검증한다.
class _ThrowingTokenStore implements TokenStore {
  @override
  Future<String?> readAccessToken() async =>
      throw Exception('보안 저장소 오류(테스트)');

  @override
  Future<void> saveAccessToken(String token) async {}

  @override
  Future<void> clear() async {}
}

/// 세션 잔여 재현용 fake — 코치 응답 1개를 그대로 돌려준다(chat_controller_test 패턴 축약).
class _FakeCoachApi extends CoachApi {
  _FakeCoachApi() : super(Dio());

  @override
  Future<CoachTurnResult> createSession(
    CoachRequest request, {
    String? problemId,
  }) async {
    return CoachTurnResult(
      dialogueId: 'prev-student-dialogue',
      response: CoachResponse(
        decision: PedagogyDecision(
          polyaStageToAdvance: 'stay',
          prompt: '이전 학생 발화에 대한 응답(테스트)',
          system: '시스템(테스트)',
          socraticCategory: '',
        ),
      ),
      wh1TurnIndex: 1,
    );
  }

  @override
  Future<CoachTurnResult> addTurn(String dialogueId, CoachRequest request) {
    throw UnimplementedError('이 테스트는 첫 턴만 쓴다');
  }
}

ProviderContainer _container(AuthApi api, TokenStore store) {
  final container = ProviderContainer(
    overrides: [
      authApiProvider.overrideWithValue(api),
      tokenStoreProvider.overrideWithValue(store),
    ],
  );
  addTearDown(container.dispose);
  return container;
}

void main() {
  test('completeLogin 성공 → 토큰 저장 + isAuthenticated', () async {
    final store = _FakeTokenStore();
    final container = _container(_FakeAuthApi(token: 'tok'), store);
    await container
        .read(authControllerProvider.notifier)
        .completeLogin(provider: 'kakao', code: 'c', redirectUri: 'r');
    final state = container.read(authControllerProvider);
    expect(store.saved, 'tok');
    expect(state.isAuthenticated, isTrue);
    expect(state.isSubmitting, isFalse);
    expect(state.error, isNull);
  });

  test('completeLogin 실패 → error·미저장·미인증(앱 안 죽음)', () async {
    final store = _FakeTokenStore();
    final container = _container(_FakeAuthApi(shouldThrow: true), store);
    await container
        .read(authControllerProvider.notifier)
        .completeLogin(provider: 'kakao', code: 'c', redirectUri: 'r');
    final state = container.read(authControllerProvider);
    expect(store.saved, isNull);
    expect(state.error, isNotNull);
    expect(state.isAuthenticated, isFalse);
    expect(state.isSubmitting, isFalse);
  });

  test('logout → tokenStore.clear + isAuthenticated=false', () async {
    final store = _FakeTokenStore()..saved = 'tok';
    final container = _container(_FakeAuthApi(token: 'tok'), store);
    await container.read(authControllerProvider.notifier).logout();
    expect(store.cleared, isTrue);
    expect(container.read(authControllerProvider).isAuthenticated, isFalse);
  });

  test(
      'logout → activeProblemProvider·코치 대화(dialogueId·메시지)도 함께 초기화된다'
      '(다음 학생에게 잔여 노출 방지·MOB-12)', () async {
    final store = _FakeTokenStore()..saved = 'tok';
    final container = ProviderContainer(
      overrides: [
        authApiProvider.overrideWithValue(_FakeAuthApi(token: 'tok')),
        tokenStoreProvider.overrideWithValue(store),
        coachApiProvider.overrideWithValue(_FakeCoachApi()),
      ],
    );
    addTearDown(container.dispose);

    // 이전 학생이 풀던 문제가 남아있는 상태를 재현한다. `overrideWith`로 초기값을 고정하면
    // `invalidate`가 그 고정값으로 되돌아가 버려 리셋을 검증할 수 없으므로(실제 프로덕션
    // 빌더는 `(ref) => null`), 실제 빌더를 그대로 두고 세팅만 직접 한다(problem_screen.onStart와
    // 동형 — `.notifier.state =`).
    container.read(activeProblemProvider.notifier).state = const Problem(
      problemId: 'p-prev-student',
      sourceType: '자체생성',
      subject: '공통',
      unitCodes: <String>['ALG'],
    );

    // 이전 학생의 코치 대화 잔여(dialogueId·메시지)를 재현한다.
    await container.read(chatControllerProvider.notifier).send('이전 학생 발화');
    expect(container.read(chatControllerProvider).dialogueId, isNotNull);
    expect(container.read(chatControllerProvider).messages, isNotEmpty);
    expect(container.read(activeProblemProvider), isNotNull);

    await container.read(authControllerProvider.notifier).logout();

    // 다음 학생이 같은 기기로 로그인해도 이전 학생의 문제·대화가 보이지 않아야 한다.
    expect(container.read(activeProblemProvider), isNull);
    final chatState = container.read(chatControllerProvider);
    expect(chatState.dialogueId, isNull);
    expect(chatState.messages, isEmpty);
  });

  test('restore: 저장된 토큰 있으면 → isAuthenticated', () async {
    final store = _FakeTokenStore()..saved = 'tok';
    final container = _container(_FakeAuthApi(token: 'tok'), store);
    await container.read(authControllerProvider.notifier).restore();
    expect(container.read(authControllerProvider).isAuthenticated, isTrue);
  });

  test('restore: 토큰 없으면(null) → 미인증', () async {
    final container = _container(_FakeAuthApi(token: 'tok'), _FakeTokenStore());
    await container.read(authControllerProvider.notifier).restore();
    expect(container.read(authControllerProvider).isAuthenticated, isFalse);
  });

  test('restore: 빈 문자열 토큰 → 미인증', () async {
    final store = _FakeTokenStore()..saved = '';
    final container = _container(_FakeAuthApi(token: 'tok'), store);
    await container.read(authControllerProvider.notifier).restore();
    expect(container.read(authControllerProvider).isAuthenticated, isFalse);
  });

  test('restore: 저장소 오류 → 미인증·예외 없음(앱 안 죽음)', () async {
    final container =
        _container(_FakeAuthApi(token: 'tok'), _ThrowingTokenStore());
    await container.read(authControllerProvider.notifier).restore();
    expect(container.read(authControllerProvider).isAuthenticated, isFalse);
  });
}
