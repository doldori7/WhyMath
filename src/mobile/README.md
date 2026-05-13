# Mobile — Flutter

## 셋업

```bash
cd src/mobile
flutter pub get
dart run build_runner build --delete-conflicting-outputs
flutter run
```

## 구조

```
src/mobile/lib/
├── main.dart
├── app.dart
├── router.dart
├── theme/
├── features/
│   ├── auth/
│   ├── onboarding/
│   ├── chat/
│   ├── solution_review/
│   ├── multi_solution/
│   ├── visualization/
│   ├── learning_curve/
│   ├── parent_report/
│   └── settings/
├── shared/
└── core/
```

## 명령

```bash
# 코드 생성 (Freezed·Riverpod·Retrofit)
dart run build_runner watch

# 테스트
flutter test

# 골든 테스트 업데이트
flutter test --update-goldens

# 분석
flutter analyze

# 빌드
flutter build apk --release
flutter build ios --release
```

## 환경

`lib/config/env.dart`:
```dart
class Env {
  static const apiUrl = String.fromEnvironment('API_URL', defaultValue: 'http://localhost:8000');
  static const sentryDsn = String.fromEnvironment('SENTRY_DSN');
}
```

빌드:
```bash
flutter run --dart-define=API_URL=https://api.example.com
```
