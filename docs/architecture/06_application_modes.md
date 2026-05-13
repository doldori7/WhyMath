# L6. 응용 모드 (Application Modes)

> 동일한 7계층 코어 위에, 시장별 *진입점*만 다르게.

## 책임

같은 엔진을 *프롬프트·UI 레이어*로 분기. 7개 모드를 단일 코드베이스로 유지.

## 7개 모드

### 1. 학교 진도 모드 (학생 메인)
- **타깃**: 중1~고3 모든 학생
- **데이터**: 검정교과서 매핑 + 학교알리미
- **특징**: 학생 학교·학년 자동 매칭
- **Phase**: 2

### 2. 수능·내신 대비
- **타깃**: 고2~고3, N수
- **데이터**: 평가원 기출 + EBS 메타
- **특징**: 단계별 진단·약점 추적
- **Phase**: 2

### 3. 사고력·심화 (Phase 1 진입점!)
- **타깃**: 전 학년
- **데이터**: NRICH·Mathigon 영감 *오리지널*
- **특징**: 한국 *유일* 자원
- **Phase**: 1

### 4. 메타인지 코칭 (Phase 1 진입점!)
- **타깃**: 전 학년
- **데이터**: Polya·교수학·Kiki 기존 자산
- **특징**: 직접 활용 가능
- **Phase**: 1

### 5. 영재 트랙
- **타깃**: 영재교육원·KMO 준비
- **데이터**: KMO 디지털 자산·AoPS·MathNet
- **특징**: 객단가 높음 (월 49,900원)
- **Phase**: 3

### 6. 자유학기제 모드
- **타깃**: 중1 자유학기
- **데이터**: 사고력 + 게임화 (적정 수준)
- **특징**: B2B 학교 진입로
- **Phase**: 3~4

### 7. 디버깅 도장 (부가)
- **타깃**: 수학+코딩 융합 관심 학생
- **데이터**: 정보 교과 + 알고리즘
- **특징**: Phase 4+ 부가
- **Phase**: 4

## 모드 분기 패턴

```python
class ApplicationMode(str, Enum):
    SCHOOL_PROGRESS = "school_progress"
    EXAM_PREP = "exam_prep"
    THINKING = "thinking"  # Phase 1 진입
    METACOGNITION = "metacognition"  # Phase 1 진입
    GIFTED = "gifted"
    FREE_SEMESTER = "free_semester"
    CODING_DOJO = "coding_dojo"

class ModeConfig(BaseModel):
    """모드별 설정"""
    mode: ApplicationMode
    
    # 콘텐츠 풀
    content_filter: dict      # 어떤 콘텐츠 추출할지
    
    # 교수학 가중치
    polya_emphasis: float     # 0~1
    metacog_freq: float       # 메타 프롬프트 빈도
    
    # 정서·게이미피케이션
    gamification_level: int   # 0(없음) ~ 3(중간), 4+ 금지
    
    # 비용·티어
    default_llm_tier: LLMTier
    daily_cost_limit_won: int
    
    # UI
    primary_color: str
    ui_layout: str
```

## 진입 순서 (Phase별)

```
Phase 1: 사고력 + 메타인지 (한국 빈자리)
   ↓
Phase 2: + 학교 진도 + 수능 (메인 매출)
   ↓
Phase 3: + 영재 (프리미엄)
   ↓
Phase 4: + 자유학기 (B2B 진입로)
   ↓
Phase 4+: + 디버깅 도장 (부가)
```

## 모드 간 전환

- 학생은 *여러 모드를 동시* 가능
- 코어 상태(BKT·오개념)는 *공유*
- 모드만 UI·콘텐츠 필터 변경

## 가격 모델 — 모드별

| 모드 | 무료 | 보급 (9,900) | 프리미엄 (29,900) | 영재 (49,900) |
|---|---|---|---|---|
| 사고력 | 일부 | ✅ | ✅ | ✅ |
| 메타인지 | 일부 | ✅ | ✅ | ✅ |
| 학교진도 | X | ✅ | ✅ | ✅ |
| 수능내신 | X | X | ✅ | ✅ |
| 영재 | X | X | X | ✅ |
| 자유학기 | (B2B) | (B2B) | (B2B) | (B2B) |

## 성공 기준

### Phase 1
- ✅ 사고력·메타인지 2개 모드 가동
- ✅ β 사용자 100명

### Phase 2
- ✅ 학교진도·수능 추가
- ✅ 결제 1,000명

### Phase 3+
- ✅ 영재 트랙
- ✅ 자유학기 B2B 시범
