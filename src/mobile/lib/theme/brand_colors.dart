// OAuth 사업자 브랜드 식별색 — 정서 안전 팔레트와 분리된 "브랜드 예외" 카테고리. MOB-09.
//
// 카카오/네이버 로그인 버튼은 각 사업자의 *규정 브랜드 색*을 써야 식별성이 유지된다(사업자 가이드).
// 따라서 이 색들은 WhyMath 정서 안전 팔레트(빨강 금지 등)의 적용 대상이 아니라 *예외*이며,
// 테마 토큰(`WhyMathTheme`)과 섞지 않고 여기에 별도로 둔다. 정서 신호(오답·주의)에는 쓰지 않는다.
import 'package:flutter/material.dart';

/// OAuth 사업자 브랜드 색 상수(정서 팔레트 예외).
abstract final class BrandColors {
  /// 카카오 시그니처 옐로우.
  static const Color kakao = Color(0xFFFEE500);

  /// 카카오 버튼 전경(글자).
  static const Color onKakao = Colors.black87;

  /// 네이버 시그니처 그린.
  static const Color naver = Color(0xFF03C75A);

  /// 네이버 버튼 전경(글자).
  static const Color onNaver = Colors.white;
}
