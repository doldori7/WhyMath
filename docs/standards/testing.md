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

커버리지의 단일 진실은 **CI에서 실제로 차단(exit 1)되는 게이트**다. 두 축으로 강제한다 —
① **집계 하한**(패키지 전체) ② **계층별 하한**(백엔드 서브패키지). (2026-07-25 ARCH-14 ② '강화'
— 그동안 집계 70%만 강제되고 계층별 목표는 문서 선언만이던 불일치를, 계층별 게이트를 실제로
배선해 해소.)

### ① 집계 하한 (CI 차단 — 미달 시 exit 1)

| 대상 | 게이트 | 강제 위치 |
|---|---|---|
| 백엔드 (`whymath_backend`) | 집계 ≥ 70% | `ci.yml` `--cov-fail-under=70` |
| 데이터 파이프라인 (`data_pipeline` — L1) | 집계 ≥ 70% | `ci.yml` `--cov-fail-under=70` |
| 웹 수학 코어 (`src/lib/**`) | 라인·함수·분기·구문 ≥ 70% | `vitest.config.js` `thresholds` |
| Flutter (모바일) | 라인 ≥ 60% | `ci.yml` mobile 커버리지 게이트(awk) |

### ② 계층별 하한 (백엔드 서브패키지 게이트)

백엔드는 L2~L5가 한 패키지(`whymath_backend`)로 묶여 집계 70%만으로는 한 계층이 낮아도
평균에 묻힌다. 이를 막기 위해 **서브패키지별 라인 커버리지 바닥선을 별도 게이트로 강제**한다
(`scripts/coverage/check_layer_coverage.py` · `ci.yml` "계층별 커버리지 게이트" 스텝 · 집계와 상보).
바닥선의 **정본은 스크립트의 `LAYER_FLOORS`**다. 2026-07-25 CI 실측이 전 계층에서 선언 목표를
상회해(아래 '실측' 열) **바닥선 = 선언 목표**로 강제한다(즉 아래 목표치가 곧 CI가 차단하는 하한):

| 서브패키지 | 목표 = 강제 floor | 실측(2026-07-25) |
|---|---|---|
| 도메인 로직 `l4` | 90% | 95.2% |
| 데이터 `l1` | 80% | 86.7% |
| ML 모델 `l2` | 80% | 96.9% |
| LLM 통합 `l3` | 70% (모킹) | 95.4% |
| API `api` (L5) | 80% | 98.3% |
| Flutter UI | 60% (위젯·골든) | 86.6% (모바일 잡) |

백엔드 집계 실측은 92.83%. `l5`(상호작용·OCR/Manim 등 외부 의존)·`l6`·횡단(db·schema·ops·
privacy·whs)은 계층 게이트를 부여하지 않고 집계 70%로 커버한다(외부 의존 과다 또는 미선언).
목표(=floor)는 **하향 금지·상향만 허용**한다(점진 강화) — 커버리지가 목표 아래로 내려가면 red.

프로젝트 표준(CLAUDE.md "커버리지 70%+")의 집행이 위 게이트다.

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
