// 간격 토큰 — 화면의 매직 넘버를 대체하는 단일 간격 스케일(4pt 리듬 기반). MOB-10.
//
// 화면은 `SizedBox` 간격·`EdgeInsets` 패딩에 raw 숫자 대신 이 토큰을 쓴다. 값은 기존 화면과
// 동일(외형 무변)하며, 향후 간격 조정을 한 곳에서 한다. 비표준 미세값(6·10·14 등)과 비대칭
// 패딩(`EdgeInsets.symmetric`/`only`/`fromLTRB`)은 이번 스코프 밖 — 후속에서 정리한다.

/// WhyMath 간격 토큰(4pt 리듬 스케일).
abstract final class AppSpacing {
  /// 4 — 미세 간격(아이콘-라벨 등).
  static const double xs = 4;

  /// 8 — 기본 간격(가장 빈번).
  static const double sm = 8;

  /// 12 — 요소 간 간격.
  static const double md = 12;

  /// 16 — 블록·카드 패딩.
  static const double lg = 16;

  /// 20 — 섹션 간 간격.
  static const double xl = 20;

  /// 24 — 큰 섹션·화면 패딩.
  static const double xxl = 24;

  /// 32 — 주요 구획 간격.
  static const double xxxl = 32;

  /// 48 — 대형 여백(로고 아래 등).
  static const double huge = 48;
}
