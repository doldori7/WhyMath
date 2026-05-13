# ML Models — L2 학습자 모델

> ml-engineer 서브에이전트가 작업하는 영역.

## 구조

```
src/ml-models/
├── bkt/                     # Bayesian Knowledge Tracing
│   ├── model.py
│   ├── parameters.py
│   └── update.py
├── irt/                     # Item Response Theory
│   ├── rasch.py             # Phase 1
│   ├── pl2.py               # Phase 2
│   └── pl3.py               # Phase 3+
├── dkt/                     # Deep Knowledge Tracing (Phase 3+)
├── affect/                  # 정서 분류
├── misconception/           # 오개념 매칭
└── common/
```

## 데이터

```
data/
├── student_responses/       # 학생 풀이 시계열
├── item_bank/               # 문항 풀
└── checkpoints/             # 모델 체크포인트
```

## 명령

```bash
# BKT 파라미터 추정
python -m src.ml_models.bkt.train

# IRT 추정
python -m src.ml_models.irt.train

# 정서 분류기 학습
python -m src.ml_models.affect.train

# 평가
python -m src.ml_models.evaluate
```
