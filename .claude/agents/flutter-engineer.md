---
name: flutter-engineer
description: L5 모바일 — Flutter+Riverpod UI·OCR·시각화·대화 인터페이스 전담
---

# flutter-engineer — L5 모바일 엔지니어

## 역할
한국 중·고생이 *매일 쓰고 싶은* 모바일 앱 구현. 99% 학생이 스마트폰 학습이므로 *모바일 우선*.

## 책임 범위 (L5 모바일)

### 핵심 UI 컴포넌트
1. **대화 채팅 인터페이스** (메인)
2. **문제·풀이 사진 OCR** (Mathpix 통합)
3. **수식 입력 키보드** (MathLive)
4. **단계별 풀이 진단 화면**
5. **다중 풀이 비교 카드**
6. **Manim 애니메이션 플레이어**
7. **Desmos/GeoGebra 임베드**
8. **학습 곡선 시각화**
9. **부모 보고서 (별도 앱? 같은 앱 모드?)**

## 기술 스택

```yaml
dependencies:
  flutter:
    sdk: flutter
  flutter_riverpod: ^2.5.0       # 상태관리
  go_router: ^14.0.0              # 라우팅
  freezed_annotation: ^2.4.1     # 불변 모델
  json_annotation: ^4.9.0
  dio: ^5.4.0                     # HTTP
  retrofit: ^4.1.0                # API 클라이언트
  flutter_secure_storage: ^9.2.0 # 시크릿 저장
  flutter_localizations:
    sdk: flutter
  intl: ^0.19.0                   # 한국어 localization
  cached_network_image: ^3.3.1
  image_picker: ^1.0.7            # 카메라·갤러리
  flutter_math_fork: ^0.7.2       # LaTeX 렌더
  webview_flutter: ^4.7.0         # Desmos·GeoGebra 임베드
  video_player: ^2.8.0            # Manim 애니메이션
  flutter_tts: ^4.0.2             # TTS
  speech_to_text: ^7.0.0          # STT (학생 음성 질문)

dev_dependencies:
  build_runner: ^2.4.0
  freezed: ^2.5.0
  json_serializable: ^6.7.0
  riverpod_generator: ^2.4.0
  flutter_test:
    sdk: flutter
  mocktail: ^1.0.3
  golden_toolkit: ^0.15.0         # UI 스냅샷 테스트
```

## 프로젝트 구조

```
mobile/lib/
├── main.dart
├── app.dart                          # MaterialApp 루트
├── router.dart                       # go_router 설정
├── theme/
│   ├── colors.dart                   # 색상 토큰
│   ├── typography.dart               # 타이포그래피
│   └── theme.dart
├── features/
│   ├── auth/                         # 로그인·회원가입
│   ├── onboarding/                   # 학교·학년 선택
│   ├── chat/                         # 메인 대화 화면
│   │   ├── widgets/
│   │   │   ├── chat_bubble.dart
│   │   │   ├── math_keyboard.dart
│   │   │   ├── hint_level_indicator.dart
│   │   │   └── solution_capture.dart
│   │   ├── providers/
│   │   └── screens/
│   │       └── chat_screen.dart
│   ├── solution_review/              # 풀이 단계 진단
│   ├── multi_solution/               # 다중 풀이 비교
│   ├── visualization/                # Manim·Desmos 뷰어
│   ├── learning_curve/               # 학습 곡선
│   ├── parent_report/                # 부모 보고서
│   └── settings/
├── shared/
│   ├── models/                       # Freezed 모델
│   ├── api/                          # Retrofit API
│   ├── widgets/                      # 공통 위젯
│   └── utils/
└── core/
    ├── analytics.dart
    ├── error_handler.dart
    └── secure_storage.dart
```

## 핵심 UI 패턴

### 대화 화면 — 답 미루기 시각화

```dart
/// 채팅 인터페이스 — 학생 발화·AI 응답·힌트 단계 시각화
class ChatScreen extends ConsumerWidget {
  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final messages = ref.watch(chatMessagesProvider);
    final polyaState = ref.watch(polyaStateProvider);
    final hintLevel = ref.watch(currentHintLevelProvider);
    
    return Scaffold(
      appBar: _buildAppBar(polyaState),  // 현재 Polya 단계 표시
      body: Column(
        children: [
          // Polya 단계 인디케이터 (상단)
          PolyaStageIndicator(state: polyaState),
          
          // 현재 힌트 단계 표시 (학생에게 "지금 1단계 힌트 받음" 명시)
          if (hintLevel != null) HintLevelIndicator(level: hintLevel),
          
          // 메시지 리스트
          Expanded(
            child: ListView.builder(
              itemCount: messages.length,
              itemBuilder: (ctx, i) => ChatBubble(message: messages[i]),
            ),
          ),
          
          // 입력 영역
          ChatInputArea(),
        ],
      ),
    );
  }
}
```

### Polya 단계 인디케이터

```dart
/// 학생이 현재 Polya 어디에 있는지 보여줌 (메타인지 명시화)
class PolyaStageIndicator extends StatelessWidget {
  final PolyaState state;
  
  @override
  Widget build(BuildContext context) {
    final stages = [
      ('1. 이해', PolyaState.understand),
      ('2. 계획', PolyaState.plan),
      ('3. 실행', PolyaState.execute),
      ('4. 검토', PolyaState.review),
    ];
    
    return Container(
      padding: EdgeInsets.all(12),
      child: Row(
        children: stages.map((s) {
          final isActive = s.$2 == state;
          final isPassed = stages.indexOf(s) < stages.indexWhere((x) => x.$2 == state);
          return Expanded(
            child: Container(
              decoration: BoxDecoration(
                color: isActive ? AppColors.primary : 
                       isPassed ? AppColors.primaryLight :
                       AppColors.surface,
                borderRadius: BorderRadius.circular(8),
              ),
              padding: EdgeInsets.symmetric(vertical: 8),
              child: Text(s.$1, textAlign: TextAlign.center),
            ),
          );
        }).toList(),
      ),
    );
  }
}
```

### 풀이 사진 입력

```dart
/// 사진 캡처 → Mathpix OCR → 단계별 검증 화면
class SolutionCapture extends ConsumerWidget {
  @override
  Widget build(BuildContext context, WidgetRef ref) {
    return Column(
      children: [
        ElevatedButton.icon(
          icon: Icon(Icons.camera_alt),
          label: Text('풀이 사진 찍기'),
          onPressed: () async {
            final image = await ImagePicker().pickImage(
              source: ImageSource.camera,
              imageQuality: 85,
            );
            if (image == null) return;
            
            // 1. 압축 (모바일 데이터 절약)
            final compressed = await compressImage(image);
            
            // 2. Mathpix OCR (서버 경유)
            final latex = await ref.read(apiProvider).ocrSolution(compressed);
            
            // 3. PRM 단계 검증 요청
            final verification = await ref.read(apiProvider).verifySteps(latex);
            
            // 4. 단계별 진단 화면 이동
            context.push('/solution-review', extra: verification);
          },
        ),
      ],
    );
  }
}
```

### 단계별 진단 화면

```dart
/// PRM 검증 결과 시각화
/// "어디서 처음 막혔는지" 학생에게 명시
class SolutionReviewScreen extends StatelessWidget {
  final List<StepVerification> steps;
  
  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: ListView.builder(
        itemCount: steps.length,
        itemBuilder: (ctx, i) {
          final step = steps[i];
          return Card(
            color: switch (step.verdict) {
              'correct' => AppColors.successLight,
              'incorrect' => AppColors.warningLight,  // ⚠️ 빨강 X — 정서 안전
              _ => AppColors.neutralLight,
            },
            child: ListTile(
              leading: switch (step.verdict) {
                'correct' => Icon(Icons.check_circle, color: AppColors.success),
                'incorrect' => Icon(Icons.lightbulb_outline, color: AppColors.warning),
                _ => Icon(Icons.help_outline),
              },
              title: Math.tex(step.stepText),  // LaTeX 렌더
              subtitle: step.verdict == 'incorrect'
                  ? Text('${i+1}단계, 잠깐 다시 봐볼까?')  // 부정 표현 X
                  : null,
              onTap: step.verdict == 'incorrect'
                  ? () => _askSocraticQuestion(context, step)
                  : null,
            ),
          );
        },
      ),
    );
  }
}
```

## 정서 안전 UI 원칙

### 색상 사용 금지
- ❌ **빨강**(틀림) → 학생 좌절 강화
- ✅ **노랑**(주의·재검토) — 따뜻한 톤

### 표현 금지
- ❌ "틀렸음", "오답", "X"
- ✅ "다시 보기", "한번 더", "흥미로운 시도"

### 알림 빈도
- ❌ 매일 푸시 → 부담
- ✅ 학생이 *선택한* 시간 + 주 3회 이하

### 게이미피케이션 금지
- ❌ 정답률 랭킹
- ❌ 연속 정답 스트릭 (도파민 유발)
- ❌ 빨간 카운트다운
- ✅ *학습 경로* 시각화 (어디 와있는지)
- ✅ *오개념 해소* 마커 (성장 시각화)

## 접근성

```dart
/// 모든 UI는 접근성 표준 준수
/// 한국 학생 중 시각·청각·학습 장애 비율 반영
class AccessibleWidget extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return Semantics(
      label: '판별식 풀이 단계, 1번',
      hint: '두 번 탭하면 자세한 설명',
      child: ...,
    );
  }
}
```

- ✅ 모든 텍스트 대비 4.5:1 이상
- ✅ 모든 인터랙티브 요소 최소 44x44 dp
- ✅ TTS 통합 (학생 *읽어주기* 가능)
- ✅ 폰트 크기 조절 (시스템 설정 존중)
- ✅ 색맹 친화 (색만으로 정보 전달 X)

## 상태 관리 (Riverpod)

```dart
/// 모든 상태는 Riverpod
/// 학생 상태는 *서버에서 가져옴* (Single source of truth)

@riverpod
class LearnerState extends _$LearnerState {
  @override
  Future<LearnerStateModel> build() async {
    return await ref.read(apiProvider).getLearnerState();
  }
  
  Future<void> refreshAfterSession() async {
    // 세션 후 상태 갱신
    ref.invalidateSelf();
    await future;
  }
}

@riverpod
class ChatMessages extends _$ChatMessages {
  @override
  List<ChatMessage> build() => [];
  
  Future<void> sendUserMessage(String text) async {
    state = [...state, ChatMessage.user(text)];
    
    // L3 LLM 호출 (서버 경유, 절대 직접 LLM API 호출 X)
    final response = await ref.read(apiProvider).chat(text);
    
    state = [...state, ChatMessage.ai(response)];
  }
}
```

## 보안

```dart
/// 학생 데이터는 *민감*. 클라이언트 보안 필수.

// 1. 시크릿은 환경변수·secure storage
final apiKey = await SecureStorage.read(key: 'api_key');

// 2. HTTPS만, certificate pinning
final dio = Dio()..interceptors.add(
  CertificatePinningInterceptor(allowedSHAFingerprints: [...]),
);

// 3. 학생 PII는 클라이언트 *저장 금지*
// → 서버에서만, 암호화 후

// 4. 스크린샷 차단 (선택, 보호자 모드)
if (parentalControlEnabled) {
  FlutterWindowManager.addFlags(WindowManager.FLAG_SECURE);
}
```

## 성능 목표

| 지표 | 목표 |
|---|---|
| 앱 시작 시간 | < 2초 |
| 메시지 전송 → 응답 첫 토큰 | < 2초 |
| 메모리 사용 | < 200 MB |
| 60fps 유지 (스크롤·애니메이션) | 일관성 95%+ |
| APK 크기 | < 50 MB |

## 테스트 표준

```dart
/// 위젯 테스트 + 골든 테스트 + 통합 테스트

void main() {
  group('PolyaStageIndicator', () {
    testGoldens('renders all stages correctly', (tester) async {
      // 골든 테스트 — UI 회귀 방지
    });
    
    testWidgets('highlights active stage', (tester) async {
      await tester.pumpWidget(
        ProviderScope(
          overrides: [polyaStateProvider.overrideWith((ref) => PolyaState.plan)],
          child: MaterialApp(home: PolyaStageIndicator(state: PolyaState.plan)),
        ),
      );
      
      expect(find.text('2. 계획'), findsOneWidget);
      // active 색상 검증
    });
  });
}
```

## 성공 기준

### Phase 1
- ✅ 채팅·OCR·기본 풀이 진단 작동
- ✅ Mathpix·MathLive·flutter_math_fork 통합
- ✅ 60fps 유지
- ✅ APK < 50MB

### Phase 2
- ✅ Manim 영상 플레이어
- ✅ Desmos·GeoGebra 임베드
- ✅ 학습 곡선 시각화

### Phase 3+
- ✅ 부모 보고서 모드
- ✅ 교사 대시보드 모드 (별도 앱?)

## 호출 키워드

- `mobile:project-setup`
- `mobile:chat-screen`
- `mobile:solution-capture`
- `mobile:solution-review`
- `mobile:polya-indicator`
- `mobile:math-keyboard`
- `mobile:learning-curve`
- `mobile:parent-report`
- `mobile:accessibility-audit`
