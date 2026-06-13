// Dio HTTP 클라이언트 — 독립 수학 코어(L1-L4) API 소비 단일 경로.
//
// 모든 백엔드 호출은 이 Dio 인스턴스를 거친다(baseUrl·타임아웃·공통 헤더 일원화).
// LLM·수학 검증은 *서버에서만* 수행되고, 클라이언트는 결과 JSON을 구조 그대로 수신한다
// (CLAUDE.md: 수학 로직을 클라에 넣지 않는다·표현≠의미).
import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'env.dart';

/// 앱 전역에서 공유하는 Dio 인스턴스 provider.
///
/// - baseUrl: [Env.apiUrl](빌드 타임 주입·시크릿 하드코딩 금지).
/// - connect/receive 타임아웃: 모바일 네트워크 변동을 견디는 보수적 값.
/// - 인증 토큰 인터셉터·certificate pinning은 후속 슬라이스(인증 플로우 도입 시).
final dioProvider = Provider<Dio>((ref) {
  final dio = Dio(
    BaseOptions(
      baseUrl: Env.apiUrl,
      connectTimeout: const Duration(seconds: 10),
      receiveTimeout: const Duration(seconds: 30),
      // 코어 API는 JSON in/out — 구조(AST/JSON)를 그대로 주고받는다.
      headers: const {'Content-Type': 'application/json'},
    ),
  );
  return dio;
});
