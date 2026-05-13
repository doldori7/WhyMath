# 테스트 표준

## 피라미드

```
       /\
      /UI\        ← E2E (적게)
     /----\
    / 통합  \      ← API·DB 통합 (중간)
   /--------\
  /  단위    \     ← 단위 테스트 (많이)
 /------------\
```

## 커버리지 목표

| 영역 | 최소 |
|---|---|
| 도메인 로직 (L4) | 90% |
| 데이터 (L1) | 80% |
| ML 모델 (L2) | 80% |
| LLM 통합 (L3) | 70% (모킹) |
| API (L5) | 80% |
| Flutter UI | 60% (위젯·골든) |

## Python 테스트

```python
# pytest + pytest-asyncio
# 디렉토리: tests/

@pytest.fixture
async def db_session():
    """테스트용 DB 세션"""
    pass

@pytest.mark.asyncio
async def test_bkt_update(db_session):
    """BKT 업데이트 정상 동작"""
    # Given
    # When
    # Then
    pass
```

## Flutter 테스트

```dart
// 위젯·골든·통합

testWidgets('PolyaStageIndicator highlights active', (tester) async {
  await tester.pumpWidget(
    ProviderScope(
      overrides: [...],
      child: MaterialApp(home: PolyaStageIndicator(...)),
    ),
  );
  expect(find.text('2. 계획'), findsOneWidget);
});

testGoldens('chat bubble layout', (tester) async {
  // 골든 테스트 — UI 회귀 방지
});
```

## LLM 호출 테스트

```python
# LLM은 *반드시* 모킹
@pytest.fixture
def mock_llm(monkeypatch):
    async def fake_generate(*args, **kwargs):
        return LLMResponse(text="모의 응답")
    monkeypatch.setattr("services.l3_llm.generate", fake_generate)
```

## 부하 테스트 (Phase 2+)

- 도구: `locust` 또는 `k6`
- 시나리오: 동시 사용자 1,000명 채팅
- 목표: p99 < 3초
