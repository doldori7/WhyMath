// OnboardingController 단위테스트 — 폼 수집·본문 조립·빈 값 제외·403 graceful. S1-c.
//
// 네트워크 없이: userApiProvider를 fake로 override해 전송 페이로드를 캡처한다
// (auth_controller_test·chat_controller_test 패턴). 화이트리스트·미성년 파생은 서버 —
// 여기선 채워진 필드만 부분 수정 dict로 조립되는지·실패해도 온보딩이 막히지 않는지만 본다.
import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:korean_math_app/features/onboarding/application/onboarding_controller.dart';
import 'package:korean_math_app/features/onboarding/data/user_api.dart';

/// 전송 본문을 캡처하는 fake — [shouldThrow]면 403 같은 실패를 흉내낸다.
class _FakeUserApi extends UserApi {
  _FakeUserApi({this.shouldThrow = false}) : super(Dio());

  final bool shouldThrow;

  /// patchMe 호출 횟수(빈 본문일 때 미호출을 검증).
  int callCount = 0;

  /// 마지막으로 받은 본문(전송 페이로드 단언).
  Map<String, dynamic>? lastBody;

  @override
  Future<void> patchMe(Map<String, dynamic> body) async {
    callCount++;
    lastBody = body;
    if (shouldThrow) {
      throw DioException(
        requestOptions: RequestOptions(path: '/v1/users/me'),
        response: Response(
          requestOptions: RequestOptions(path: '/v1/users/me'),
          statusCode: 403,
        ),
        error: '미성년 미동의(테스트)',
      );
    }
  }
}

ProviderContainer _containerWith(_FakeUserApi fake) {
  final container = ProviderContainer(
    overrides: [userApiProvider.overrideWithValue(fake)],
  );
  addTearDown(container.dispose);
  return container;
}

void main() {
  test('submit: 채워진 필드만 올바른 본문으로 조립한다(날짜 YYYY-MM-DD)', () async {
    final fake = _FakeUserApi();
    final container = _containerWith(fake);
    final notifier = container.read(onboardingControllerProvider.notifier);

    notifier.setTargetGrade(2);
    notifier.setTargetScore(130);
    notifier.setTargetExamDate(DateTime(2026, 11, 19));
    notifier.setBirthYear(2008);

    await notifier.submit();

    expect(fake.callCount, 1);
    expect(fake.lastBody, <String, dynamic>{
      'target_grade': 2,
      'target_score': 130,
      'target_exam_date': '2026-11-19',
      'birth_year': 2008,
    });

    final state = container.read(onboardingControllerProvider);
    expect(state.isSubmitting, isFalse);
    expect(state.isSubmitted, isTrue);
    expect(state.error, isNull);
  });

  test('submit: 미입력 필드는 본문에서 제외한다(부분 수정)', () async {
    final fake = _FakeUserApi();
    final container = _containerWith(fake);
    final notifier = container.read(onboardingControllerProvider.notifier);

    // 목표 등급만 입력하고 나머지는 비운다.
    notifier.setTargetGrade(1);

    await notifier.submit();

    expect(fake.lastBody, <String, dynamic>{'target_grade': 1});
    expect(fake.lastBody!.containsKey('target_score'), isFalse);
    expect(fake.lastBody!.containsKey('target_exam_date'), isFalse);
    expect(fake.lastBody!.containsKey('birth_year'), isFalse);
  });

  test('submit: 전부 미입력이면 전송하지 않고 완료 처리한다(선택 입력)', () async {
    final fake = _FakeUserApi();
    final container = _containerWith(fake);
    final notifier = container.read(onboardingControllerProvider.notifier);

    await notifier.submit();

    // 보낼 게 없으면 patchMe를 부르지 않는다 — 온보딩은 그대로 진행(isSubmitted=true).
    expect(fake.callCount, 0);
    final state = container.read(onboardingControllerProvider);
    expect(state.isSubmitted, isTrue);
    expect(state.error, isNull);
  });

  test('submit: 403(미성년 미동의)은 삼켜 온보딩을 막지 않는다(graceful)', () async {
    final fake = _FakeUserApi(shouldThrow: true);
    final container = _containerWith(fake);
    final notifier = container.read(onboardingControllerProvider.notifier);

    notifier.setBirthYear(2015); // 미성년 → 서버 403 흉내.

    // 예외를 밖으로 던지지 않는다(호출 자체가 완료돼야 한다).
    await notifier.submit();

    final state = container.read(onboardingControllerProvider);
    expect(state.isSubmitting, isFalse);
    // 실패해도 온보딩은 진행한다(채팅으로 넘어감) — 에러 메시지만 남긴다.
    expect(state.isSubmitted, isTrue);
    expect(state.error, isNotNull);
  });

  test('setter는 값을 갱신하고 null로 되돌릴 수 있다', () async {
    final container = _containerWith(_FakeUserApi());
    final notifier = container.read(onboardingControllerProvider.notifier);

    notifier.setTargetScore(120);
    expect(container.read(onboardingControllerProvider).targetScore, 120);

    // 입력 필드를 비우면(int.tryParse('') → null) 미입력으로 되돌아간다.
    notifier.setTargetScore(null);
    expect(container.read(onboardingControllerProvider).targetScore, isNull);
  });
}
