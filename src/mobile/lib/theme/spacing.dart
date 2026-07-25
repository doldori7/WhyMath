// 간격 토큰 — 화면의 매직 넘버를 대체하는 단일 간격 스케일(4pt 리듬 기반). MOB-10.
//
// 화면은 `SizedBox` 간격·`EdgeInsets` 패딩(`all`/`symmetric`/`only`/`fromLTRB`)에 raw 숫자 대신
// 이 토큰을 쓴다. 값은 기존 화면과 동일(외형 무변)하며, 향후 간격 조정을 한 곳에서 한다.
// 4pt 리듬 밖 미세값(2·6·10·14)은 아래 *오프리듬 토큰*으로 값 그대로 보존한다(시각 검증 가능
// 시점에 리듬 흡수 재검토 — 추후 정리).

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

  // ── 오프리듬 미세값 ────────────────────────────────────────────────
  // 밀집 UI(배지·칩·조밀한 행·버블 내부)에서 쓰는 2pt 단위 보정값. 4pt 리듬 밖이라
  // 새 코드는 위 스케일을 우선 쓰고, 아래는 기존 조밀 UI의 값을 *그대로* 보존하기 위한
  // 토큰이다(외형 무변). 시각 검증이 가능한 시점에 리듬으로 흡수할지 재검토한다(추후 정리).

  /// 2 — 하이라인(배지·칩 등 아주 조밀한 여백).
  static const double hairline = 2;

  /// 6 — xs(4)와 sm(8) 사이 미세 간격.
  static const double xs6 = 6;

  /// 10 — sm(8)과 md(12) 사이 미세 간격.
  static const double sm10 = 10;

  /// 14 — md(12)와 lg(16) 사이 미세 간격.
  static const double md14 = 14;
}
