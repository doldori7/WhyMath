// Dio HTTP 클라이언트 — 독립 수학 코어(L1-L4) API 소비 단일 경로.
//
// 모든 백엔드 호출은 이 Dio 인스턴스를 거친다(baseUrl·타임아웃·공통 헤더 일원화).
// LLM·수학 검증은 *서버에서만* 수행되고, 클라이언트는 결과 JSON을 구조 그대로 수신한다
// (CLAUDE.md: 수학 로직을 클라에 넣지 않는다·표현≠의미).
import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../features/auth/application/auth_controller.dart';
import 'auth_interceptor.dart';
import 'env.dart';
import 'token_store.dart';

/// 앱 전역에서 공유하는 Dio 인스턴스 provider.
///
/// - baseUrl: [Env.apiUrl](빌드 타임 주입·시크릿 하드코딩 금지).
/// - connect/receive/sendTimeout: 모바일 네트워크 변동을 견디는 보수적 값(sendTimeout은
///   MOB-15 — OCR multipart 이미지 업로드가 느린 네트워크에서 무한정 대기하지 않도록).
/// - [AuthInterceptor]: 저장된 액세스 토큰을 Bearer로 자동 첨부(OAuth-b·미인증이면 헤더 없이),
///   401 수신 시 토큰 클리어 + 로그아웃(MOB-15).
/// - certificate pinning은 후속 슬라이스.
final dioProvider = Provider<Dio>((ref) {
  final dio = Dio(
    BaseOptions(
      baseUrl: Env.apiUrl,
      connectTimeout: const Duration(seconds: 10),
      receiveTimeout: const Duration(seconds: 30),
      // OCR `/pages`는 SEC-17이 합계 50MB로 상한을 걸어 뒀으므로, receiveTimeout과 대칭인
      // 30초는 일반 모바일 업로드 대역폭 기준 합리적 여유다(이 저장소에 별도 상한 근거 없음).
      sendTimeout: const Duration(seconds: 30),
      // 코어 API는 JSON in/out — 구조(AST/JSON)를 그대로 주고받는다.
      // X-App-Version(OPS-17): 서버 최소버전 계약 게이트(app.py _service_metrics_middleware)가
      // 읽는 클라 버전 신고. Env.appVersion은 컴파일타임 상수라야 이 const 맵에 들어갈 수 있다
      // (pubspec.yaml version:과의 동기화는 tests/infra/test_app_version_pubspec_sync.py가 게이트).
      headers: const {
        'Content-Type': 'application/json',
        'X-App-Version': Env.appVersion,
      },
    ),
  );
  // 저장된 토큰을 모든 요청에 Bearer로 첨부(인증 플로우·OAuth-b).
  //
  // onUnauthorized(MOB-15): 401은 세션 자체가 무효라는 서버 판정이므로 `AuthController.logout()`
  // 전체(토큰 클리어 + isAuthenticated=false + activeProblem/chatController invalidate·MOB-12
  // 선례)를 그대로 태운다 — 부분 정리는 스테일 상태(이전 학생의 활성 문제·대화)를 남긴다.
  //
  // 순환 의존 주의: 이 `ref.read`는 dioProvider의 build 시점이 아니라 401 발생 시점에 실행되는
  // 클로저 안에 있어 즉시 build-time 순환은 아니다. `AuthController`는 build()에서 dioProvider를
  // 참조하지 않고(demoTokenProvider·tokenStoreProvider만 읽음), `authApiProvider`(dioProvider 의존)는
  // `completeLogin()` 호출 시점에만 read된다 — 즉 "dioProvider 생성 → AuthController 생성"의
  // build-time 사이클은 없다. 유일하게 맞물릴 수 있는 경로는 로그인 자체(`POST /v1/auth/*/callback`)가
  // 401을 내는 경우인데, 그 요청은 토큰 미보유 상태로 나가므로(Authorization 헤더 없음) 서버가
  // "토큰이 무효"라는 의미의 401을 낼 일이 없고(코드 교환 실패는 통상 400/401이더라도 의미가 다름),
  // 설령 발생해도 logout()은 dio를 다시 호출하지 않으므로 재귀·무한루프로 이어지지 않는다
  // (completeLogin()의 catch가 별도로 에러 메시지를 세팅할 뿐).
  dio.interceptors.add(
    AuthInterceptor(
      ref.read(tokenStoreProvider),
      onUnauthorized: () =>
          ref.read(authControllerProvider.notifier).logout(),
    ),
  );
  return dio;
});
