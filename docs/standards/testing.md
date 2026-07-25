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

커버리지의 단일 진실은 **CI에서 실제로 차단(exit 1)되는 게이트**다. 아래 "강제 게이트"가
정본이고, "권장 목표"는 아직 게이트로 강제하지 않는 계층별 지향점(비차단·측정만)이다.
(2026-07-25 ARCH-14 ② 정합 — 선언만 있고 미강제이던 계층별 수치가 강제되는 것처럼 읽히던
불일치를 해소: 강제되는 것과 지향하는 것을 분리 표기.)

### 강제 게이트 (CI 차단 — 미달 시 exit 1)

| 대상 | 게이트 | 강제 위치 |
|---|---|---|
| 백엔드 (`whymath_backend` — L2~L5 통합 단일 패키지) | 집계 ≥ 70% | `ci.yml` `--cov-fail-under=70` |
| 데이터 파이프라인 (`data_pipeline` — L1) | 집계 ≥ 70% | `ci.yml` `--cov-fail-under=70` |
| 웹 수학 코어 (`src/lib/**`) | 라인·함수·분기·구문 ≥ 70% | `vitest.config.js` `thresholds` |
| Flutter (모바일) | 라인 ≥ 60% | `ci.yml` mobile 커버리지 게이트(awk) |

프로젝트 표준(CLAUDE.md "커버리지 70%+")의 집행이 위 게이트다. 백엔드는 L2~L5가 한 패키지
(`whymath_backend`)로 묶여 있어 **계층별 분리 게이트가 아니라 패키지 집계 70%**를 강제한다
(계층별 서브패키지 게이트화 = 아래 권장 목표를 게이트로 승격하는 별도 과제).

### 권장 목표 (비게이트·계층별 지향점)

계층별로 더 높은 커버리지를 *지향*하되 아직 CI 게이트로 강제하지 않는다(측정만·차단 없음):

| 영역 | 지향 | 게이트화 |
|---|---|---|
| 도메인 로직 (L4) | 90% | 미강제(집계 70%에 포함) |
| 데이터 (L1) | 80% | 미강제(집계 70%) |
| ML 모델 (L2) | 80% | 미강제(집계 70%에 포함) |
| LLM 통합 (L3) | 70% (모킹) | 미강제(집계 70%에 포함) |
| API (L5) | 80% | 미강제(집계 70%에 포함) |
| Flutter UI | 60% (위젯·골든) | **강제 완료**(라인 ≥ 60%) |

이 지향점을 실제 서브패키지 게이트로 승격하려면 계층별 실측 베이스라인 확인 후 배선이
필요하다(ARCH-14 ②의 '강화' 경로 — 현재는 '완화'로 문서↔강제 정합만 반영).

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
