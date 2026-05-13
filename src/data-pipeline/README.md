# Data Pipeline — L1 데이터 기반

> data-engineer 서브에이전트가 작업하는 영역.

## 구조

```
src/data-pipeline/
├── ncic/                    # 성취기준 크롤러
│   ├── collect.py
│   ├── clean.py
│   └── load.py
├── school_info/             # 학교알리미
├── textbooks/               # 검정 교과서 목차
├── kice/                    # 평가원 기출
├── oer/                     # 글로벌 OER
├── misconceptions/          # 오개념 카탈로그
└── common/
    ├── rate_limiter.py
    ├── validators.py
    └── loaders.py
```

## 표준 흐름

```
수집 → 정제 → 정형화 → 검증 → 저장 → 인덱싱
```

## 명령

```bash
# 전체 파이프라인
python -m src.data_pipeline.run --source=ncic

# 검증만
python -m src.data_pipeline.validate --source=ncic

# 임베딩 갱신
python -m src.data_pipeline.embed --source=all
```

## 참조

- 라이선스 매트릭스: `docs/data/licensing_safety.md`
- 데이터 카드: `docs/data/*.md`
- 서브에이전트: `.claude/agents/data-engineer.md`
