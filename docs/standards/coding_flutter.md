# Flutter 코딩 표준

## 환경
- Flutter 3.x stable
- Dart 3.x
- 패키지 관리: `pubspec.yaml`
- 코드 생성: `build_runner`

## 포맷·린터
- 포맷: `dart format`
- 린터: `flutter analyze`
- 룰: `package:flutter_lints` + 커스텀

## 아키텍처
- **상태관리**: Riverpod 2.x (Provider 모두 `@riverpod` 코드 생성)
- **모델**: Freezed (불변)
- **API**: Retrofit + dio
- **라우팅**: go_router

## 폴더 구조 (feature-first)

```
lib/
├── main.dart
├── app.dart
├── router.dart
├── theme/
├── features/
│   └── [feature]/
│       ├── widgets/
│       ├── providers/
│       ├── models/
│       └── screens/
├── shared/
│   ├── models/
│   ├── api/
│   ├── widgets/
│   └── utils/
└── core/
```

## 스타일

```dart
// 모든 주석은 한국어
// public API에 doc comment 필수

/// 학생 채팅 메시지 모델
@freezed
class ChatMessage with _$ChatMessage {
  /// 학생 메시지
  const factory ChatMessage.user({
    required String id,
    required String text,
    required DateTime timestamp,
  }) = UserMessage;
  
  /// AI 메시지
  const factory ChatMessage.ai({
    required String id,
    required String text,
    required DateTime timestamp,
    required int hintLevel,
    required PolyaStage stage,
  }) = AiMessage;
  
  factory ChatMessage.fromJson(Map<String, Object?> json) =>
      _$ChatMessageFromJson(json);
}
```

## 정서 안전 UI 원칙
- 빨강 금지 (학생 좌절 강화)
- 게이미피케이션 금지
- 부정 표현 금지
- 접근성 100% (Semantics·대비·탭 영역)

## 성능
- 60fps 유지 (스크롤·애니메이션)
- `const` 위젯 적극 사용
- 큰 리스트는 `ListView.builder`
- 이미지 캐싱 (`cached_network_image`)

## 테스트
- 위젯 테스트 + 골든 테스트
- `mocktail`로 의존성 모킹
- 핵심 위젯은 *반드시* 골든 테스트 (회귀 방지)
