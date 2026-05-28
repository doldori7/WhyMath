MathScope / WhyMath
국제·국내 수학 데이터베이스 저작권 종합 가이드 v2.0
— 한국 B2C 영리 출시 + 국제 데이터 활용 통합 참조 —
작성일: 2026-05-27
대상: 중·고등 수학 학습 앱 B2C 상업 출시 + TIPS 신청·IP 실사
근거: v1.0(2026-05-26) + 종합보고서(2026-05-27) + 실시간 약관 확인 7곳

변경 이력

v2.0 (2026-05-27) — 통합 개정판
핵심 신규 사항
공공누리 "AI유형" 신설(2026-01-28) 정식 편입 — 게임 체인저
저작권법 §32 단서(영리 시험문제 활용 금지), §93(DB제작자권), §125-2(법정손해배상), §136(형사처벌), §140(영리·상습 비친고죄) 추가
2024년 8월 대법원 판결(KICE 사용료 지급 의무) 반영
문체부 「생성형 AI 공정이용 안내서」(2026-02-26) 4요소 기준 추가
AI 기본법(2026 시행) 컴플라이언스 인프라 요건
MathNet 5-Layer 저작권 분석 신규 챕터(§1.6)
DMCA Safe Harbor 비대칭 책임 사슬 신규 챕터(§1.7)
한국 시장 매트릭스 7개 카테고리 전체 편입(§5)
위험 시나리오 4가지 정량 분석(§7)
4-Tier 활용 전략 확정(§6.3)
선의 입증 패키지 + Attorney-Client Privilege 활용(§8.4-8.5)
관계 기관 연락처 정식 부록화(부록 C)

v1.0 (2026-05-26) — 초판
국제 데이터셋 등급 분류 체계(A+ ~ E) 확립
NuminaMath, PRM800K, OpenMathInstruct 프로파일
5단계 ETL 통합 시나리오
PostgreSQL dataset_licenses 스키마 v1

Executive Summary — 5줄 결론

① 한국 교육부 고시 본문은 무제한 활용
저작권법 제7조에 따라 2022 개정 성취기준 코드는 보호 대상이 아님. 백본 데이터로 즉시 채택 가능.

② EBS·KICE·시·도교육청 기출은 영리 차단
공공누리 미부착 또는 2/4유형. 학습 데이터·서비스 콘텐츠로 사용 시 형사 5년 이하 징역 + 민사 1건당 최대 5천만 원(영리·고의) 리스크.

③ 공공누리 "AI유형"(2026-01-28 신설) = 게임 체인저
AI유형 마크가 부착된 자료는 학습 데이터 재판매만 금지될 뿐, 학습된 AI 모델의 상업적 이용은 허용. KOGL 검색 시 우선 확인 권장.

④ AI Hub 「지능정보산업 인프라 조성」 산출물은 영리 활용 명문 허용
수학 데이터셋 71718·71716·71859·479·71518 등. 출처 명시 + 데이터셋 재판매 금지 조건만 지키면 B2C 앱 학습 데이터로 사용 가능.

⑤ Khan Academy·NRICH·Wolfram·EBS 교재·검인정 교과서·사설 모의·경시는 완전 격리
학습 데이터·서비스 콘텐츠 양쪽 모두 사용 금지.

한 줄 결론
"NCIC 성취기준 + AI Hub(KR) + NuminaMath(Apache 2.0) + PRM800K(MIT) + PhET(CC BY 4.0)" 5개 조합만으로도 안전한 B2C 상업 출시가 가능하다.

목차

1. 라이선스 분류학의 법적 기반
1.1 "무료"와 "자유"는 다르다
1.2 한국 저작권법의 핵심 8개 조항
1.3 베른협약과 국제 적용
1.4 데이터베이스 보호 (별도 권리)
1.5 AI 학습 데이터 관련 2026년 동향
1.6 [신규] 5-Layer 저작권 체크 모델
1.7 [신규] DMCA Safe Harbor 비대칭 책임 사슬
1.8 [신규] 2024년 8월 대법원 판결의 충격

2. 등급별 심층 분석 (A+ ~ E)

3. 핵심 데이터셋별 상세 프로파일
3.1 NuminaMath 시리즈
3.2 PRM800K
3.3 OpenMathInstruct
3.4 형식수학 라이브러리
3.5 [신규] MathNet — 5-Layer 케이스 스터디
3.6 [신규] AI Hub 한국 수학 데이터셋
3.7 [신규] 공공누리 AI유형 자료 활용

4. 국가별 정책 환경 심화

5. [신규] 전체 데이터 사이트 라이선스 매트릭스 (7개 카테고리)

6. ETL 통합 + 4-Tier 활용 전략

7. [신규] 위험 시나리오 4가지 정량 분석

8. 법적 리스크 관리 + 선의 입증

9. PostgreSQL 운영 스키마 v2

10. 모니터링·갱신 체계

11. 즉시 실행 액션 (Week 1)

부록 A·B·C·D

1. 라이선스 분류학의 법적 기반
1.1 "무료"와 "자유"는 다른가
저작권 분류의 가장 흔한 오해부터 정리하고 시작합니다. "무료(free of charge)"와 "자유(free as in freedom)"는 완전히 다른 개념입니다.
예를 들어 NRICH(Cambridge)는 누구나 무료로 볼 수 있지만, 학습 데이터로 추출하는 것은 명시적으로 금지되어 있습니다. EBS 콘텐츠도 EBSi에서 누구나 무료로 다운로드 가능하지만, 상업 활용은 완전 차단입니다. 한국 NCERT 교과서(인도)도 PDF 무료 다운로드가 가능하나 출판사 © 보유로 영리 사용 불가입니다.
따라서 "라이선스 = 돈을 지불하는가"가 아니라 "라이선스 = 어떤 용도로 어디까지 쓸 수 있는가"의 문제입니다. B2C 영리 출시 관점에서는 &apos;학습 데이터로 쓸 수 있나&apos;, &apos;서비스 콘텐츠로 쓸 수 있나&apos;, &apos;paraphrase하면 되나&apos;의 세 갈래로 분리해서 봐야 합니다.
1.2 한국 저작권법의 핵심 8개 조항
영리 EdTech 활용 시 반드시 알아야 할 조항입니다. v1.0의 3개에서 v2.0에서는 8개로 확장합니다.
제7조 — 보호받지 못하는 저작물
헌법·법률·조약·명령·조례 및 규칙, 국가 또는 지방자치단체의 고시·공고·훈령 등은 저작권 보호 대상이 아니다.
이 조항이 한국 교육부 고시인 2022 개정 수학과 교육과정 성취기준 코드(예: [9수02-01])를 무제한 인용·DB화·AI 학습에 사용할 수 있는 법적 근거입니다. MathScope의 커리큘럼 백본을 이 위에 세우면 영구히 안전합니다.
제24조의2 — 공공저작물의 자유이용
국가·지방자치단체가 업무상 작성·공표한 저작물은 원칙적으로 자유 이용이 가능합니다. 다만 다음은 예외로 별도 허락이 필요합니다:
국가안전보장 관련 자료
개인의 사생활·사업상 비밀
다른 법률에 따라 공개가 제한된 정보
한국저작권위원회에 등록된 저작물로 국유재산 또는 공유재산
이 예외 조항 때문에 NCIC가 별도 등록한 해설서·홍보물은 공공누리 2유형으로 제한된 것입니다. KICE 수능·모의평가도 "별도 협의 필요"로 분류됩니다.
제32조 — 시험문제로서의 복제 단서 조항 [신규 강조]
학교 입학시험이나 그 밖에 학식 및 기능에 관한 시험을 위해 공표된 저작물을 복제·배포·공중송신할 수 있다. 다만 영리를 목적으로 하는 경우 그러하지 아니하다.
v2.0의 가장 중요한 신규 강조입니다. 영리 EdTech 앱에는 단서 조항이 적용되어 "공표된 시험문제 활용 면책"이 깨집니다.
쉽게 풀어 말하면: 학교가 시험에 EBS 지문을 인용하는 것은 합법이지만, MathScope 같은 영리 앱이 EBS 기출을 활용하는 것은 명백한 침해입니다. 이 한 조항만으로도 EBS·KICE·시·도교육청·KMO 기출 모두 영리 사용이 차단됩니다.
제35조의5 — 저작물의 공정한 이용 (한국판 페어유즈)
미국 페어유즈와 유사한 4요소 종합 판단:
이용의 목적·성격 (영리/비영리, 변형적/단순 복제)
저작물의 종류·용도 (사실적/창작적)
이용된 부분의 양·중요성
시장에 미치는 영향
실무 경고:
AI 학습 데이터 활용에서 자주 거론되지만, 영리 스타트업이 의존하기에는 매우 위험합니다. 판례가 거의 없어 예측 불가능하며, 문체부 안내서(2026-02-26)도 "참고 자료일 뿐 법원 판단은 별도"임을 명시합니다. B2C 영리 앱에 적용 시 4요소 중 (4) "시장 가치에 미치는 영향"이 결정적이며, EBS·평가원 기출의 시장 가치를 직접 잠식할 가능성이 있어 공정이용 인정 가능성이 낮습니다.
제93조 — 데이터베이스 제작자의 권리 [강조]
데이터베이스 제작자는 그 데이터베이스의 전부 또는 상당한 부분을 복제·배포·방송·전송할 권리를 가진다.
개별 문제 하나하나는 저작물성이 약해도, "기출문제집"이라는 DB로 묶이는 순간 별도 보호가 발생합니다. EBS 수능특강, 경문사 KMO 풀이집, MathNet 자체 컴파일이 모두 이에 해당합니다.
영리 활용 시 가장 자주 놓치는 부분이며, NRICH의 "추출 금지" 조항도 이 데이터베이스권에 근거합니다.
제125조의2 — 법정손해배상 [신규]
손해액 산정이 어려운 경우 저작물 1개당 최대 1,000만 원(영리 목적 또는 고의 침해의 경우 5,000만 원) 이내에서 청구 가능.
정량 의미:
30,000개 문항 무단 학습 시 이론상 최대 1,500억 원~3,000억 원 청구권 발생
영리 + 고의 입증되면 한 건당 5배 가중
실무상 침해 입증된 일부 건 합계 수억~수십억 원 수준이 일반적
제136조 — 형사처벌 [신규]
저작재산권 침해 시 5년 이하 징역 또는 5,000만 원 이하 벌금에 처할 수 있다. 한국에서는 징역형과 벌금형 동시 부과 가능.
일반적인 법률은 보통 징역 또는 벌금 중 하나로 선고되지만, 저작권 침해는 특이하게 동시 부과가 가능할 정도로 처벌 수위가 높습니다. 미수범 처벌 규정은 없으며 과실범도 처벌되지 않습니다.
제140조 — 영리·상습 비친고죄 [신규]
이 조항이 합의를 통한 종결을 막는 결정적 조항입니다.
일반 저작권 침해: 친고죄 → 피해자가 합의·고소 취하 시 종결
영리·상습 침해: 비친고죄 → 합의해도 검찰이 직권 기소 가능
MathScope처럼 영리 구독 모델은 자동으로 비친고죄 영역에 속하므로, EBS·평가원과 합의에 성공해도 검찰이 형사 절차를 계속 진행할 수 있습니다. 대표자 개인 형사책임이 발생하는 시나리오입니다.
1.3 베른협약과 국제 적용
한국은 베른협약 가입국이므로 외국 저작물도 한국 내에서 동일한 보호를 받습니다. 따라서 미국 MAA(AMC·AIME·USAMO) 문제, 일본 출판사 교과서, 중국 CMO를 한국 영리 앱이 무단 이용하는 것은 한국 저작권법 위반입니다.
반대로 미국 정부 저작물(NAEP·DLMF 등)은 미국법상 퍼블릭 도메인이지만 한국에서도 그 지위를 인정받습니다. 베른협약 제5조 내국민대우 원칙의 역적용입니다.
1.4 데이터베이스 보호 (별도 권리)
저작권과 별개로 EU와 한국은 "데이터베이스 제작자의 권리"를 인정합니다. §93에서 살펴봤듯, 개별 요소의 저작물성이 약해도 "DB로 묶이는 순간" 별도 보호가 발생합니다.
v2.0 신규 통찰 — 역방향 함정:
MathNet 같은 학술 데이터셋은 컴파일 자체는 Apache 2.0 자유 라이선스지만, 그 안에 포함된 30,676개 원본 문제는 47개국의 별개 저작물입니다. 즉 "DB는 자유, 원소는 비자유"인 역방향 함정 구조가 존재합니다. 자세한 분석은 §1.6과 §3.5를 참조하세요.
1.5 AI 학습 데이터 관련 2026년 동향
한국 — 공공누리 "AI유형" 신설 (2026-01-28) [게임 체인저]
v2.0의 가장 중요한 신규 사항입니다.
항목
내용 (KOGL 공식 약관 직접 인용)
적용 범위
기존 1·2·3·4유형과 병행. AI유형 마크가 함께 부착된 자료에 한정
허용 범위
"인공지능 학습용 데이터"로 이용할 경우 자유 이용 — 출처표시 조건 없음
상업적 이용
"공공저작물을 학습한 인공지능 모델의 상업적 이용은 가능"
금지
"공공저작물을 이용해 제작한 인공지능 학습용 데이터의 재판매는 금지"
기술적 조치
"공공저작물과 동일하거나 실질적으로 유사한 산출물이 생성되지 않도록 기술적 조치 필요"
일반 이용
AI 학습 외 일반 이용 시에는 함께 표시된 기존 유형(1~4)의 이용조건 준수

실무 의미:
기존에 "공공누리 2유형 = 영리 차단"으로 분류한 NCIC 해설서, KICE 일부 자료 중 AI유형 마크가 추가 부착된 항목은 학습 데이터로 사용 가능
학습된 AI 모델을 B2C 유료 앱으로 상업화하는 것은 허용 — 단 출력 결과가 원본과 동일·유사하지 않도록 n-gram 필터·임베딩 유사도 검사 등 기술적 가드레일 필수
데이터셋 자체를 패키징해 판매하는 행위만 금지되므로 "AI 모델 SaaS 형태의 상업 출시"에는 영향 없음
KOGL 검색 시 "AI유형" 필터를 우선 확인하고 AI유형 부착 여부를 데이터셋 메타데이터에 별도 컬럼으로 기록 권장
한국 — 문체부 「생성형 AI 공정이용 안내서」 (2026-02-26 발간)
문화체육관광부와 한국저작권위원회가 공식 발간한 안내서의 핵심 메시지:
상업 목적·웹 크롤링이 자동으로 공정이용을 배제하지는 않음 — 4요소 종합 평가 필요
4요소: (1) 이용 목적·성격 (2) 원저작물의 종류·목적 (3) 이용 비율·중요도 (4) 시장 가치에 미치는 영향
단, 이 안내서는 "참고 자료"일 뿐 정부 공식 해석이 아니며, 최종 판단은 법원이 함
한국 — 「AI 기본법」 (2026년 시행)
정식 명칭: 인공지능 발전과 신뢰 기반 조성 등에 관한 기본법
2026년부터 본격 시행됨에 따라 고위험 AI 시스템(교육 분야 포함 가능성)에 대해 학습 데이터 출처 입증 의무가 발생할 수 있습니다. 데이터셋 메타데이터 컬럼(라이선스·출처·검증일) 기록을 지금부터 인프라화하는 것이 향후 컴플라이언스 비용을 크게 절감합니다.
EU — AI Act 단계 적용
2024년 발효되어 2026년부터 단계적 적용. 고위험 AI 시스템(교육 평가 포함)은 학습 데이터의 라이선스 출처를 문서화해야 합니다. K-12 교육 AI는 고위험 분류 가능성이 매우 높아, MathNet처럼 47개국 원본 라이선스가 미문서화된 데이터셋은 CE 마킹 거부 → EU 시장 진입 차단 가능성이 있습니다.
미국 — AI 저작권 소송 진행 중
NYT vs OpenAI, Anthropic vs Music Publishers 등 판례 진행 중. 2025-2026년 판결이 글로벌 표준에 영향을 줄 가능성이 있어 모니터링이 필요합니다.
1.6 [신규] 5-Layer 저작권 체크 모델
MathNet 같은 학술 데이터셋은 "이중 라이선스 구조"라고 단순화하기에는 부족합니다. v2.0에서는 5겹 구조로 정밀 모델링합니다.
레이어
권리자
예시(MathNet)
영리 통과
Layer 1 — 컴파일 ©
DB 제작자
MIT/KAUST (Apache 2.0)
✅ 통과
Layer 2 — 원본 ©
각국 수학회·출판사
47개국 저작권
❌ 차단
Layer 3 — 풀이 ©
풀이 작성자·검수자
30+ 검수자 + GPT-4.1 정규화
❌ 잔존
Layer 4 — 국가별 특별법
각국 입법기관
한국 §32 단서, §125-2
❌ 영리 차단
Layer 5 — 베른협약
국제 조약
외국 권리자도 한국법 보호
❌ 적용

핵심 통찰 — 영리 통과 조건
MathNet의 경우 5개 Layer 중 1개(컴파일)만 통과하고 4개가 막힙니다.
영리 B2C 활용은 모든 5개 Layer를 동시에 통과해야 합니다.
→ Tier 0(평가 전용)만 즉시 가능, 그 외는 사실/표현 분리 또는 정식 라이선싱 필요.
1.7 [신규] DMCA Safe Harbor 비대칭 책임 사슬
MathNet 같은 학술 데이터셋이 "takedown 정책"을 운영하는 이유는 미국 DMCA §512(c) Safe Harbor에 들어가기 위함입니다. 그러나 이 보호는 영리 다운스트림 사용자(MathScope)에게는 적용되지 않습니다.
DMCA §512(c)(1) 4단계 요건
(A)(i) Actual Knowledge가 없을 것 — 주관적 인지
(A)(ii) Red Flag Knowledge가 없을 것 — 객관적 명백성
(A)(iii) 인지 시 즉시 제거(expeditious removal)
(B) 침해 활동에서 직접 금전적 이익 없음 AND 통제권 없음
(C) 적법한 takedown notice 즉시 응답
MIT vs MathScope 비대칭 매트릭스
DMCA Safe Harbor 요건
MIT (MathNet)
MathScope
1. 비영리 OSP
✅ 학술 비영리
❌ 영리법인
2. takedown 정책 운영
✅ shaden@mit.edu 운영
△ 운영해도 사후 약함
3. 침해 인지 후 즉시 제거
✅ PDF 파일 즉시 삭제 가능
△ 학습된 모델은 사실상 불가
4. 침해로부터 직접 수익 없음
✅ 무료 공개
❌ 구독료 직접 수익
5. Red Flag 미인지
✅ 일반 학술 활동
❌ 가이드 v2.0 작성 = 인지

가장 치명적 — 비대칭 #5 (Red Flag Knowledge)
Viacom v. YouTube (2d Cir. 2012) 판례: "Red flag provision turns on whether the provider was subjectively aware of facts that would have made the specific infringement &apos;objectively&apos; obvious to a reasonable person."
MathScope 적용:
가이드 v2.0 작성 자체가 "위험 인지"의 명시적 증거
디스커버리 시 원고 변호사가 그대로 사용 가능
이후 침해 발생 시 "willful infringement(고의 침해)" 인정
한국법 §125-2 적용 시 5배 가중 (5천만 원/건)
§140 비친고죄 + 양형 가중 → 실형 가능성 증가

역설의 해결책
가이드 작성 = 위험. 가이드 미작성 = 더 큰 위험(Willful Blindness).
정답: 가이드를 변호사 의견서의 별첨자료로 격상시켜 Attorney-Client Privilege 보호 안에 두기.
자세한 방어 전략은 §8.4-8.5 참조.
1.8 [신규] 2024년 8월 대법원 판결의 충격
대학수학능력시험·모의평가 문제에 인용된 시·소설 등 제3자 저작물에 대해 한국교육과정평가원조차 사용료 지급 의무가 인정된 판결입니다.
판결의 핵심 메시지:
"공익 목적"도 침해 면책 사유가 아님
국가 시험기관조차 제3자 저작물 사용료 지급 의무
"묵인 관행"에 의존한 영리 활용은 가시성이 큰 AI 학습부터 가장 먼저 제재 대상이 될 가능성

MathScope 시사점:
수학 도메인은 시·소설 인용이 거의 없어 평가원/교육청 단일 저작권만 다루면 됩니다. 그러나 "평가원도 사용료를 내야 하는데, 일개 영리 스타트업이 무단 사용?"이라는 비교 논리가 성립하므로 KICE·EBS·시·도교육청 기출의 무단 영리 활용은 절대 금기입니다.

2. 등급별 심층 분석 (A+ ~ E)
v1.0의 7개 등급 체계를 유지하되, 한국 시장 케이스와 공공누리 AI유형을 추가 반영합니다.
2.1 🟢 A+ 등급: 퍼블릭 도메인 / 법령류
저작권 자체가 존재하지 않거나 자유 활용이 무제한 보장된 영역.
대표 사례:
한국 교육부 고시 본문 (저작권법 §7) — 2022 개정 성취기준 코드
일본 학습지도요령 본문 (법령류)
Common Core State Standards (미국 NGA/CCSSO)
Metamath set.mm (CC0)
DLMF (NIST 특수함수) — US Gov Work
MathScope 활용:
커리큘럼 백본·검산 엔진의 기초. 영구히 안전하며 출처 표시 의무도 없습니다(권장은 함).
2.2 🟢 A 등급: CC BY / MIT / Apache 2.0
상업 활용·재배포·수정 모두 허용. 출처 표시 의무만 있음.
대표 사례 — 수학 학습 핵심:
NuminaMath 1.5 / CoT / TIR (Apache 2.0) — 90만+86만+7만 경시 문제
GSM8K (MIT) — OpenAI 8.5K 초등 서술형
MATH (MIT) — Hendrycks 12.5K 경시 + 단계별 풀이
PRM800K (MIT) — 단계별 정답/오답 라벨 [소크라테스 튜터링 핵심]
MetaMathQA (MIT) — 39.5만 증강 문제
OlympiadBench (Apache 2.0) — 8천 올림피아드 벤치마크
TheoremQA (CC BY 4.0) — 800 대학 수준 정리
miniF2F / PutnamBench (MIT/Apache) — 형식수학 벤치마크
PhET 시뮬레이션 (CC BY 4.0) — 미국 콜로라도대
Illustrative Mathematics 초판 2019-2021 (CC BY 4.0) — v.360 2024 신판은 NC라 ❌
OpenStax (CC BY 4.0) — 미국 Rice대
출처 표시 형식 예시:
데이터셋: NuminaMath 1.5
출처: AI-MO / Numina Math (Apache License 2.0)
URL: https://huggingface.co/datasets/AI-MO/NuminaMath-1.5
수정 사실: 한국어 번역 및 2022 개정 교육과정 매핑
2.3 🟢 A- 등급: 정부 OGL / 커스텀 상업 허용
상업 활용은 허용되나 일부 제한 조건이 붙는 등급.
대표 사례:
UK National Curriculum (Open Government Licence v3.0)
Australian Curriculum / ACARA (CC BY 4.0)
NZ Curriculum (CC BY 4.0)
Eduscol / Programmes (Etalab Licence — CC BY 호환, 프랑스)
AI Hub 「지능정보산업 인프라 조성」 수학 데이터셋 (영리 명문 허용)
OpenMathInstruct-1/2 (NVIDIA License — 상업 허용)
주의 — AI Hub의 4가지 조건:
출처 표시 의무: "한국지능정보사회진흥원 사업결과" 명시 + 2차 저작물에도 동일 표시
국외 반출 / 국외 법인 이용 시 별도 합의 필요
AI 데이터셋 자체의 재판매·양도·대여 금지 (AI 모델 형태의 서비스는 가능)
이용 목적·방법·내용이 위법·부적합 판단 시 환수·폐기 요구 가능
2.4 🟡 B 등급: CC BY-SA (ShareAlike의 함정)
출처 표시 + 동일 조건 배포(Share-Alike) 의무. AI 영리 활용 시 가장 주의해야 할 등급.
ShareAlike의 "바이러스성" 문제:
SA 라이선스 자료를 AI 학습에 사용하면, 그 모델의 출력물도 SA로 배포해야 한다는 해석이 가능합니다. 영리 SaaS 모델의 핵심 자산인 "모델 가중치"를 SA로 공개해야 할 수 있어 사업 모델 자체가 붕괴 가능성이 있습니다.
이 해석은 아직 판례로 확정되지 않았지만, 보수적 IP 변호사는 SA 자료의 학습 데이터 직접 사용을 권장하지 않습니다.
대표 사례:
Wikipedia (수학 포털) — CC BY-SA 4.0
Stack Exchange / MathOverflow — CC BY-SA 4.0
AoPS Wiki / Contest Collections — CC BY-SA
Encyclopedia of Mathematics — CC BY-SA 4.0 (Springer/EMS)
ProofWiki, nLab — CC BY-SA
Serlo (독일), DIKSHA (인도) — CC BY-SA
OpenWebMath — CC BY-SA
MathNet — 컴파일은 Apache 2.0이나 원본은 47개국 © 혼재 (Tier 0만 안전)
IMO 공식 기출 — 학술 관행상 자유이나 공식 라이선스는 "All Rights Reserved"
우회 패턴 — Tier 2 (§6.3 참조):
Feist v. Rural (1991, 미국), 한국 대법원 2000다61664에 따라 "사실(facts)은 저작권 보호 대상 아님"입니다. SA 자료에서 수학적 사실·구조만 추출하고 표현(expression)은 Claude/Qwen3로 자체 생성하면 SA 의무를 우회할 수 있습니다.
2.5 🟡 C 등급: NC (비영리 한정)
Non-Commercial 명시. 영리 활용 절대 차단.
대표 사례:
Khan Academy — CC BY-NC-SA [NC + SA 이중 독성, 가장 위험]
IM v.360 2024 신판 — CC BY-NC (초판은 A 등급이라 혼동 주의)
Open Middle, MathPile — CC BY-NC-SA
OEIS 정수열 본문 — CC BY-NC 3.0
NCIC 해설서·연구보고서·홍보물 — 공공누리 2유형 [AI유형 부착 시 별도 검토]
KICE 수능·6/9월 모의평가 — KOGL 미부착, "무단 복제·배포 금지" 명시
시·도교육청 학력평가 — KOGL 미부착
KMO·KJMO 대한수학회 — All Rights Reserved
싱가포르 MOE 강의계획서 — 정부 사용약관
주의 — Khan Academy 케이스:
Khan Academy의 "CC BY-NC-SA"는 NC와 SA를 동시에 부과하는 이중 독성 라이선스입니다. 영리 활용 차단 + SA 바이러스성 + Khan Academy 브랜드 보호의 삼중 차단으로 가장 위험한 자료입니다. 학습 데이터·서비스 콘텐츠 양쪽 모두 완전 격리 필수입니다.
2.6 🔴 D 등급: 출판사·기관 독점
어떤 형태로도 영리 사용 불가. 라이선싱 협상 가능성도 매우 낮음.
한국:
EBSi, EBS 수능특강·완성·올림포스 — EBS 독점
검·인정 교과서 (천재·미래엔·비상·동아·금성·지학사 등)
HME 해법수학학력평가 (천재교육 ©)
KMA 한국수학학력평가, KMC 한국수학경시, 성대경시
사설 모의고사: 메가스터디, 이투스, 대성마이맥, 종로학원
국제:
USAMO/AMC/AIME (MAA) — "revenue-generating purposes requires written permission" 명시
중국 CMO/CTST — 중국수학회 © 엄격
일본 JMO — 일본수학올림피아드재단 ©
일본 검정교과서 (7개 출판사)
중국 인민교육출판사 교과서
NCERT 교과서 (인도) — 무료 PDF ≠ 자유 [함정 사례]
Wolfram MathWorld — Wolfram Research 독점
Brilliant.org — 구독제 콘텐츠
2.7 🔴 E 등급: 추출 자체 금지
저작권법 §93(데이터베이스권) 또는 서비스 약관으로 추출 자체가 금지된 자료.
대표 사례:
NRICH (Cambridge) — 추출 자체 금지 명시
Project Euler — 풀이 공개 금지
Mathway, Photomath — 서비스 약관 추출 금지 (경쟁 서비스)
이 등급은 "무료로 볼 수 있다"와 가장 강한 대비를 이루는 영역입니다. 사용자가 직접 접근하는 것은 자유이나, AI 학습용 추출·DB화는 명시적 침해입니다.

3. 핵심 데이터셋별 상세 프로파일
3.1 NuminaMath 시리즈
MathScope 학습 데이터의 1차 추천 후보. 90만+86만+7만 = 약 183만 경시 수준 문제.
속성
내용
라이선스
Apache License 2.0 (Hugging Face 명시)
등급
🟢 A
규모
NuminaMath 1.5: 90만 / CoT: 86만 / TIR: 7만
콘텐츠
AMC/AIME, Olympiad shortlist 등 경시 문제 + Chain-of-Thought 풀이
언어
영어 (한국어 번역 필요)
출처
https://huggingface.co/datasets/AI-MO/NuminaMath-1.5
영리 활용
✅ 권장
주의사항
Apache 2.0은 NOTICE 파일 포함 의무 + 수정 사실 명시

MathScope 활용 패턴:
# NuminaMath 다운로드 및 한국어 변환 파이프라인
from datasets import load_dataset

# 1단계: 데이터셋 로드
ds = load_dataset(&apos;AI-MO/NuminaMath-1.5&apos;, split=&apos;train&apos;)

# 2단계: 한국 교육과정 매핑 (Qwen3 로컬)
import ollama
def classify_for_korea(problem_text):
    """한국 2022 개정 교육과정 코드 매핑"""
    response = ollama.chat(
        model=&apos;qwen3:32b&apos;,
        messages=[{
            &apos;role&apos;: &apos;system&apos;,
            &apos;content&apos;: &apos;한국 2022 개정 수학과 성취기준 코드를 매핑하세요.&apos;
        }, {
            &apos;role&apos;: &apos;user&apos;,
            &apos;content&apos;: problem_text
        }]
    )
    return response[&apos;message&apos;][&apos;content&apos;]

# 3단계: PostgreSQL 적재 (라이선스 메타데이터 포함)
import psycopg2
conn = psycopg2.connect(dsn=&apos;postgresql://localhost/mathscope&apos;)
cursor = conn.cursor()
cursor.execute("""
    INSERT INTO problems (statement, source_dataset, license_grade,
                          license_type, attribution)
    VALUES (%s, &apos;NuminaMath-1.5&apos;, &apos;A&apos;, &apos;apache-2.0&apos;,
            &apos;AI-MO / Numina Math, Apache License 2.0&apos;)
""", (problem_text,))
3.2 PRM800K (Process Reward Model 800K)
소크라테스 튜터링의 핵심 데이터셋. OpenAI가 공개한 단계별 정답/오답 라벨 80만 건.
속성
내용
라이선스
MIT License
등급
🟢 A (강력 권장)
규모
약 80만 단계별 라벨
콘텐츠
수학 문제 풀이의 각 단계를 +/-/뉴트럴로 라벨링
WhyMath 활용
학생의 풀이 단계 실시간 검증, 오개념 탐지
출처
https://github.com/openai/prm800k

핵심 활용 패턴:
# PRM800K를 활용한 소크라테스 튜터링 검증
import json

# 학생 풀이 단계를 검증하는 함수
def verify_student_step(step_text, problem_context):
    """학생의 풀이 한 단계가 올바른지 PRM 라벨로 평가"""
    # PRM800K 유사도 검색으로 비슷한 단계 찾기
    similar_steps = find_similar_in_prm800k(step_text)

    # 라벨 통계로 정/오답 확률 추정
    correct_ratio = sum(1 for s in similar_steps if s[&apos;rating&apos;] == 1)
    return {
        &apos;is_correct&apos;: correct_ratio / len(similar_steps) > 0.7,
        &apos;confidence&apos;: correct_ratio / len(similar_steps),
        &apos;similar_correct&apos;: [s for s in similar_steps if s[&apos;rating&apos;] == 1][:3],
        &apos;similar_wrong&apos;: [s for s in similar_steps if s[&apos;rating&apos;] == -1][:3]
    }
3.3 OpenMathInstruct 시리즈 (NVIDIA)
NVIDIA가 합성한 대규모 수학 instruction 데이터.
속성
내용
라이선스
NVIDIA License (상업 허용 명시)
등급
🟢 A-
규모
OpenMathInstruct-1: 180만 / -2: 추가 확장
콘텐츠
GSM8K/MATH 시드 + 합성 풀이
주의
NVIDIA 라이선스 약관 별도 확인 필수
3.4 형식수학 라이브러리 — 검산 엔진
학생 풀이의 수학적 정확성을 "증명 가능한 수준"으로 검증하는 백엔드.
라이브러리
라이선스
규모
활용
Lean Mathlib
Apache 2.0
약 200만 라인
풀이 검산
Isabelle AFP
BSD/LGPL
440만 라인
정리 증명
Coq/Rocq mathcomp
CeCILL-B (BSD 호환)
15만 라인
수학 정리
Metamath set.mm
CC0 (Public Domain)
ZFC 4만+ 정리
기초 수학
Mizar MML
조건부 무료
폴란드 형식수학
조건 확인 필요
3.5 [신규] MathNet — 5-Layer 케이스 스터디
2026년 4월 MIT CSAIL + KAUST + HUMAIN이 공개한 30,676개 전문가 검증 문제. 47개국, 17개 언어, 143개 대회. 차순위 데이터셋의 5배 규모로 ICLR 2026 발표 예정.
5-Layer 라이선스 분석
Layer
권리자
라이선스
통과
L1 컴파일
MIT/KAUST/HUMAIN
Apache 2.0
✅
L2 원본 문제
47개국 수학회
각국 default ©
❌
L3 풀이/주석
30+ 검수자 + GPT-4.1
출처별 상이
❌
L4 한국법 §32 단서
한국 입법
영리 시험문제 금지
❌
L5 베른협약
국제 조약
외국 권리자 한국법 보호
❌
출처별 정밀 분류 (추정)
출처 유형
비중
권리자
영리 활용
IMO 본선 공개분
~3%
IMO Foundation
✅ 출처표시
IMO Shortlist 공개분
~5%
IMO Foundation
✅ 출처표시
IMO Longlist/TST 비공개
~5%
출처 불명확
❌ E등급
미국 MAA (AMC/AIME/USAMO)
~10%
MAA
❌ 영리 라이선싱 운영
한국 KMO
~2-3%
대한수학회
❌ §32 단서
영국 BMO/UKMT
~3%
UKMT
⚠️ 일부 OGL
루마니아 RMC
~6%
RMC
❌
중국 CMO/CTST
~10%
중국수학회
❌
일본 JMO
~3%
JMO재단
❌
National Booklets 비공개
~5%
각국 IMO 위원회
❌ E등급
기타 30+개국
~35-40%
각국 수학회
⚠️ 미검증
정량 결론
30,676개 중 영리 활용 가능량
🟢 즉시 가능 (A+/A): 약 2,500~3,700개 (8-12%)
🟡 회색 영역 (B/C): 약 4,500~6,100개 (15-20%)
🔴 영리 차단 (D/E): 약 21,500~22,500개 (70-75%)

MathScope 활용 결론
MathNet은 "학술 벤치마크로는 황금, 영리 서비스 콘텐츠로는 지뢰밭"
Tier 0 (평가 전용 격리) → 즉시 활용
Tier 1 (IMO 공식분 분리) → 4주 내 작업
Tier 2 (사실/표현 분리 paraphrase) → 분기 단위 확장
Tier 3 (IMO Foundation 정식 라이선싱) → 12개월 로드맵
3.6 [신규] AI Hub 한국 수학 데이터셋
한국지능정보사회진흥원이 운영하는 AI 학습용 데이터 허브. 영리 활용을 명문 허용한다는 점에서 한국 시장 진출의 핵심 자원.
주요 수학 데이터셋
dataSetSn
데이터셋명
특징
71718
수학 풀이 데이터
초·중·고 수학 문제 및 단계별 풀이
71716
수학 교과 학습 데이터
교육과정별 문제·해설
71859
수학 문제 자연어 처리
한국어 수학 문제 NLP
479
수학 학습 콘텐츠
다단계 풀이 데이터
71518
수학 자동채점
채점·피드백 데이터
이용정책 — 영리 허용 명문
"본 AI데이터 등은 인공지능 기술 및 제품·서비스 발전을 위하여 구축하였으며, 지능형 제품·서비스, 챗봇 등 다양한 분야에서 영리적·비영리적 연구·개발 목적으로 활용할 수 있습니다."
준수 의무 4가지
출처 표시: "한국지능정보사회진흥원 사업결과" 명시 + 2차 저작물 동일 표시
국외 반출 / 국외 법인 이용 시 별도 합의 필요
AI 데이터셋 자체의 재판매·양도·대여 금지 (AI 모델 형태 서비스는 가능)
이용 목적·방법·내용이 위법·부적합 판단 시 환수·폐기 요구 가능
주의 사항
AI Hub 내에서도 "지능정보산업 인프라 조성 사업 산출물"이 아닌 외부 기관 제공 데이터(KETI 데이터, 카이스트 오디오북 등)는 별도 정책이 적용되며 대부분 "비상업 연구·개발 목적만" 허용됩니다. 데이터셋별로 개별 확인이 필수입니다.
3.7 [신규] 공공누리 AI유형 자료 활용
2026-01-28 신설된 "AI유형" 마크가 부착된 자료는 영리 EdTech의 보석함입니다. 기존 1·2·3·4유형과 병행 표시되며, AI 학습 용도에 한해 자유 이용이 허용됩니다.
KOGL 검색 워크플로우
KOGL 사이트(kogl.or.kr) 접속
자료 검색 시 "AI유형" 필터 활성화
결과 자료의 마크 확인 — "AI유형" + 기존 유형 병행 표시
데이터셋 메타데이터의 `ai_type_attached` 컬럼에 true 기록
AI 학습 데이터로 사용 + 모델 출력 가드레일 적용
기술적 가드레일 구현
# 공공누리 AI유형 준수 — 출력 유사도 가드레일
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity

# 1. n-gram 기반 직접 일치 검사
def check_ngram_overlap(generated, originals, n=8, threshold=0.7):
    """8-gram 일치율이 70% 이상이면 재생성 필요"""
    gen_ngrams = set(generate_ngrams(generated, n))
    for orig in originals:
        orig_ngrams = set(generate_ngrams(orig, n))
        overlap = len(gen_ngrams & orig_ngrams) / max(len(gen_ngrams), 1)
        if overlap > threshold:
            return False, f&apos;8-gram 일치율 {overlap:.1%} - 재생성 필요&apos;
    return True, &apos;통과&apos;

# 2. 임베딩 기반 의미 유사도
model = SentenceTransformer(&apos;jhgan/ko-sbert-nli&apos;)
def check_semantic_similarity(generated, originals, threshold=0.85):
    """의미 유사도 85% 이상이면 재생성 필요"""
    gen_emb = model.encode([generated])
    orig_embs = model.encode(originals)
    sims = cosine_similarity(gen_emb, orig_embs)[0]
    if max(sims) > threshold:
        return False, f&apos;의미 유사도 {max(sims):.1%} - 재생성 필요&apos;
    return True, &apos;통과&apos;

4. 국가별 정책 환경 심화
4.1 한국 — 미묘함의 미로
MathScope의 1차 시장이자 가장 복잡한 라이선스 지형.
교육부 vs 평가원 vs EBS vs 시·도교육청 — 4중 구조
기관
자료
저작권 정책
영리 활용
교육부
성취기준 고시
§7 면제
✅ 무제한
NCIC
교육과정 본문
§7 면제
✅ 무제한
NCIC
해설서·연구보고
공공누리 2유형
❌ AI유형 부착 시만
KICE
수능·6/9월 모의
KOGL 미부착
❌ 영리 차단
KICE
공공데이터포털
대부분 KOGL 1유형
✅ 통계 메타만
EBS
수능특강·완성·연계
EBS 독점
❌ 완전 차단
EBSi
강의·해설
EBS 독점
❌ 완전 차단
시·도교육청
3·4·7·10월 학력평가
교육청 © + KICE ©
❌ 영리 차단
사설 영역 — 천재·메가스터디 등
HME (천재교육) — 사설 라이선스 비용 큼
KMA / KMC / 성대경시 — 주최기관 © (비상교육·성균관대 등)
메가스터디, 이투스, 대성마이맥, 종로학원 — 사설 모의고사 완전 차단
경문사 KMO 풀이집 — 출판사 라이선스 독점
KMO — 대한수학회
kmo.or.kr 푸터에 "Copyright ⓒ 대한수학회 All Rights Reserved" 명시. 영리 활용 직접 차단.
협상 가능성:
KMO는 학회 비영리 사업이므로 EBS·천재교육보다 협상 여지가 큽니다. "한국 수학 영재 교육 AI 향상 R&D" 명목으로 협업 제안 + 데이터셋 출처에 KMO 명기 + 공동 연구 제안하는 방식이 권장됩니다. 연락처: kmo@kms.or.kr
공공누리 5유형 체계 (2026 기준)
유형
조건
영리 활용
1유형
출처 표시
✅
2유형
출처 표시 + 비영리
❌
3유형
출처 표시 + 변경 금지
✅
4유형
출처 표시 + 비영리 + 변경 금지
❌
AI유형 (2026.01.28 신설)
AI 학습 자유 + 모델 상업화 OK + 데이터셋 재판매 금지
✅
4.2 일본 — 검정교과서 시스템의 의미
일본은 학습지도요령 본문은 법령류(§7 유사 면제)이지만 교과서는 7개 출판사가 검정을 받아 학교가 채택하는 구조. 출판사 저작권이 강력하며 영리 활용은 사실상 불가능합니다.
학습지도요령 본문 (문부과학성) — 🟢 A+ 무제한
검정교과서 7개사 — 🔴 D 완전 차단
JMO (일본수학올림피아드재단) — 🔴 D 별도 협상
4.3 영국 — OGL의 모범성
Open Government Licence v3.0이 모범 사례. CC BY 4.0과 호환되며 상업 활용을 명시적으로 허용합니다.
National Curriculum — 🟢 A- OGL v3.0
BMO/UKMT — 🟡 B-C 일부 OGL, 대부분 UKMT ©
4.4 EU — AI Act와 교육 AI
EU AI Act 부속서 III에서 "교육 시스템"을 고위험으로 분류 가능. 고위험 시스템은 학습 데이터의 라이선스 출처를 입증해야 합니다.
MathScope 시사점:
EU 진출 시 모든 학습 데이터의 라이선스 출처 문서화 필수
MathNet처럼 47개국 원본 라이선스가 미문서화된 데이터셋 사용 시 CE 마킹 거부 가능성
PostgreSQL `dataset_licenses` 테이블이 EU AI Act 컴플라이언스 인프라
4.5 [신규] 미국 — MAA 영리 라이선싱
미국 Mathematical Association of America(MAA)는 AMC·AIME·USAMO 영리 활용에 대해 명시적 라이선싱을 운영합니다.
"The use of the competition&apos;s problems or solutions for revenue-generating purposes requires written permission from the Mathematical Association of America (MAA)."
한국 영리 앱이 MAA 문제를 무단 활용하면?
베른협약 제5조 내국민대우 원칙에 따라 한국 법원에서 MAA가 한국 저작권법으로 보호받습니다. 미국 회사라서 무시할 수 있는 것이 아니며, 한국 형사·민사 절차가 모두 가능합니다.

5. [신규] 전체 데이터 사이트 라이선스 매트릭스
v1.0 등급 분류 + 종합보고서 매트릭스를 통합한 7개 카테고리 단일 참조. B2C 상업 출시 관점에서 사용 가능 여부를 한눈에 확인할 수 있도록 정리했습니다. 등급 기준: 🟢 안전 / 🟡 조건부 / 🔴 차단.
5.1 카테고리 1 — 한국 교육 표준·공공 데이터
사이트 / 데이터
등급
라이선스
B2C 활용
NCIC 교육과정 고시 본문 (ncic.re.kr)
🟢 A+
저작권법 §7 면제
✅ 무제한
NCIC 해설서·연구보고서·홍보물
🔴 C
공공누리 2유형
❌ AI유형 부착 시 별도
KICE 수능·6/9월 모의평가 (suneung.re.kr)
🔴 C
KOGL 미부착
❌ 영리 차단
시·도교육청 학력평가 (3·4·7·10월)
🔴 C
교육청 + KICE ©
❌ 영리 차단
EBSi 수능 강의·해설
🔴 D
EBS 독점
❌ 완전 차단
EBS 수능특강·완성·올림포스
🔴 D
EBS + 집필진 ©
❌ 완전 차단
검·인정 교과서 (천재·미래엔 등)
🔴 D
출판사 ©
❌ 완전 차단
공공데이터포털 (data.go.kr)
🟢 A~A-
공공누리 1유형
✅ 통계 메타데이터만
AI Hub 수학 (71718·71716·71859·479·71518)
🟢 A-
영리·비영리 활용 가능 명시
✅ 가능
AI Hub 외부기관 데이터 (KETI 등)
🔴 C
비상업 R&D만
❌ 영리 차단
KOFAC STEAM 자료
🟡 C
대부분 KOGL 2유형
❌ AI유형만
국립중앙도서관 디지털컬렉션
🟡 B-C
자료별 상이
⚠️ 개별 확인
5.2 카테고리 2 — 한국 사설 경시·올림피아드
사이트 / 데이터
등급
라이선스
B2C 활용
KMO·KJMO 대한수학회 (kmo.or.kr)
🔴 C
All Rights Reserved
❌ 협상 필수
HME 해법수학학력평가
🔴 D
천재교육 ©
❌ 차단
KMA 한국수학학력평가
🔴 D
비상교육 ©
❌ 차단
KMC 한국수학경시
🔴 D
주최기관 ©
❌ 차단
성대경시
🔴 D
성균관대 ©
❌ 차단
사설 모의고사 (메가스터디·이투스·대성마이맥·종로학원)
🔴 D
사설 ©
❌ 차단
경문사 KMO 풀이집
🔴 D
출판사 독점 라이선스
❌ 차단
5.3 카테고리 3 — 국제 올림피아드·경시
사이트 / 데이터
등급
라이선스
B2C 활용
IMO 공식 (imo-official.org)
🟡 B
© 2006 IMO All Rights Reserved 학술 관행상 자유
⚠️ 출처 + 라이선싱
IMO Foundation 후원·교육 활용
🟡 B
명시 라이선스 없음
⚠️ 직접 협상
MathNet (MIT/KAUST/HUMAIN)
🟡 B
Apache 2.0(컴파일) + 47개국 ©(원본)
⚠️ 평가 셋만
USAMO/AMC/AIME (MAA)
🔴 D
MAA © + 영리 라이선싱 운영
❌ 차단
중국 CMO/CTST
🔴 D
중국수학회 © 엄격
❌ 차단
일본 JMO
🔴 D
일본수학올림피아드재단 ©
❌ 차단
Putnam 대학경시
🟡 B
MAA 일부 공개
⚠️ 대학별 확인
AoPS Wiki / Contest Collections
🟡 B
CC BY-SA 사용자 게시물
⚠️ SA 독성
5.4 카테고리 4 — 국제 AI 학습 데이터셋 (상업 출시 핵심)
데이터셋
등급
라이선스
규모·특징
NuminaMath 1.5
🟢 A
Apache 2.0
90만 경시 + CoT
NuminaMath CoT / TIR
🟢 A
Apache 2.0
86만 + 7만 도구 통합
GSM8K
🟢 A
MIT
8.5K 초등 서술형
MATH (Hendrycks)
🟢 A
MIT
12.5K 경시 + 단계별
PRM800K
🟢 A
MIT
단계별 정답/오답 [핵심]
OpenMathInstruct-1/2 (NVIDIA)
🟢 A-
NVIDIA License
180만+ 합성
MetaMathQA
🟢 A
MIT
39.5만 증강
OlympiadBench
🟢 A
Apache 2.0
8천 (수+물리)
TheoremQA
🟢 A
CC BY 4.0
800 대학 정리
miniF2F / PutnamBench
🟢 A
MIT / Apache
형식수학 벤치마크
MathPile
🔴 C
CC BY-NC-SA
95억 토큰 — 평가만
OpenWebMath
🟡 B
CC BY-SA
SA 독성 — 사실 추출
5.5 카테고리 5 — 형식수학·검산 엔진
라이브러리
등급
라이선스
용도
Lean Mathlib
🟢 A
Apache 2.0
약 200만 라인, 풀이 검산
Isabelle AFP
🟢 A
BSD/LGPL
440만 라인 정리
Coq/Rocq mathcomp
🟢 A
CeCILL-B (BSD 호환)
15만 라인
Metamath set.mm
🟢 A+
CC0 (Public Domain)
ZFC 4만+ 정리
Mizar MML
🟡 B-C
조건부 무료
조건 확인 필요
5.6 카테고리 6 — 국제 교육 표준·교과서
자원
등급
라이선스
국가/기관
UK National Curriculum
🟢 A-
OGL v3.0
영국 gov.uk
Australian Curriculum (ACARA)
🟢 A
CC BY 4.0
호주
NZ Curriculum (TKI)
🟢 A
CC BY 4.0
뉴질랜드
Common Core State Standards
🟢 A+
Public Domain 유사
미국 NGA/CCSSO
Eduscol / Programmes
🟢 A
Etalab (CC BY 호환)
프랑스 BOEN
일본 학습지도요령 본문
🟢 A+
법령류 면제
일본 MEXT
일본 검정교과서 7개사
🔴 D
출판사 ©
학교 채택 구조
싱가포르 MOE 강의계획서
🟡 C
정부 사용약관
직접 활용 어려움
핀란드 OPS
🟢 A
공공 라이선스
EDUFI
중국 인민교육출판사 교과서
🔴 D
출판사 ©
중국 국정
NCERT 교과서 (인도)
🔴 D
NCERT © 무료≠자유
함정 사례
Illustrative Mathematics 초판 (2019-21)
🟢 A
CC BY 4.0
v.360 신판은 NC
OpenStax
🟢 A
CC BY 4.0
미국 Rice대
PhET 시뮬레이션
🟢 A
CC BY 4.0
콜로라도대 [권장]
Khan Academy
🔴 C
CC BY-NC-SA
NC+SA 이중 독성
NRICH (Cambridge)
🔴 E
추출 자체 금지
DB권 §93
Wolfram MathWorld
🔴 D
Wolfram 독점
추출 금지
Project Euler
🔴 D
풀이 공개 금지
약관 제한
Brilliant.org
🔴 D
Brilliant 독점
구독제
Mathway / Photomath
🔴 E
추출 금지
경쟁 서비스
5.7 카테고리 7 — 위키·백과·Q&A (SA 바이러스 주의)
자원
등급
라이선스
비고
Wikipedia (수학 포털)
🟡 B
CC BY-SA 4.0
사실만 추출 — 표현 자체 생성
Stack Exchange / MathOverflow
🟡 B
CC BY-SA 4.0
덤프 공개
Encyclopedia of Mathematics
🟡 B
CC BY-SA 4.0
Springer/EMS
ProofWiki
🟡 B
CC BY-SA 4.0
증명 위키
nLab
🟡 B
CC BY-SA
범주론
AoPS Wiki
🟡 B
CC BY-SA
경시 + 풀이
Serlo (독일)
🟡 B
CC BY-SA
독일 OER
DIKSHA (인도)
🟡 B
CC BY-SA
정부 디지털 학습
OEIS (정수열)
🔴 C
CC BY-NC 3.0
NC 라이선스
DLMF (NIST 특수함수)
🟢 A+
US Gov Work
Public Domain
zbMATH Open 메타데이터
🟢 A
Open metadata
60만 색인
arXiv (math)
🟡 B
논문별 상이
대부분 perpetual non-exclusive

6. ETL 통합 + 4-Tier 활용 전략
v1.0의 5단계 ETL 파이프라인을 4-Tier 라이선스 기반 전략으로 확장합니다.
6.1 파이프라인 전체 흐름
MathScope의 ETL은 데이터 소스의 라이선스 등급에 따라 처리 경로가 달라집니다.
[데이터 소스 식별]
       ↓
[Layer 1-5 라이선스 검증] ── ❌ 차단 → 폐기 또는 격리
       ↓ ✅
[Tier 분류]
  ├─ Tier 0: 평가 전용 격리 (격리 컨테이너)
  ├─ Tier 1: 즉시 도입 학습 데이터 (PostgreSQL 적재)
  ├─ Tier 2: 사실/표현 분리 paraphrase (Claude/Qwen3)
  └─ Tier 3: 정식 라이선싱 협상 후 활용
       ↓
[한국 교육과정 매핑] (Qwen3 로컬 + Claude API 검증)
       ↓
[가드레일 적용] (n-gram + 임베딩 유사도)
       ↓
[PostgreSQL 적재 + 라이선스 메타데이터 기록]
6.2 단계별 라이선스 처리
각 단계에서 라이선스를 검증하고 추적하는 어댑터 패턴.
# 데이터 소스별 수집 어댑터 (라이선스 자동 라벨링)
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List

@dataclass
class LicensedRecord:
    """라이선스 메타데이터가 강제 부착된 레코드"""
    problem_text: str
    source_dataset: str
    license_grade: str        # &apos;A+&apos;, &apos;A&apos;, ..., &apos;E&apos;
    license_type: str         # &apos;apache-2.0&apos;, &apos;cc-by-4.0&apos;, &apos;kogl-ai&apos; 등
    commercial_ok: bool
    training_eligible: bool
    sharealike_required: bool
    attribution_text: str     # 출처 표시 문구

class DataSourceAdapter(ABC):
    """라이선스 라벨링 강제 추상 클래스"""
    @abstractmethod
    def fetch(self) -> List[LicensedRecord]: ...

class NuminaMathAdapter(DataSourceAdapter):
    """Apache 2.0 → 영리 활용 안전"""
    def fetch(self) -> List[LicensedRecord]:
        ds = load_dataset(&apos;AI-MO/NuminaMath-1.5&apos;, split=&apos;train&apos;)
        return [LicensedRecord(
            problem_text=r[&apos;problem&apos;],
            source_dataset=&apos;NuminaMath-1.5&apos;,
            license_grade=&apos;A&apos;,
            license_type=&apos;apache-2.0&apos;,
            commercial_ok=True,
            training_eligible=True,
            sharealike_required=False,
            attribution_text=&apos;AI-MO/Numina Math (Apache 2.0)&apos;
        ) for r in ds]

class AIHubKoreaAdapter(DataSourceAdapter):
    """AI Hub 한국 데이터 → 영리 명문 허용"""
    def fetch(self) -> List[LicensedRecord]:
        # AI Hub 71718 다운로드 (별도 인증 필요)
        records = self._load_aihub_dataset(dataSetSn=&apos;71718&apos;)
        return [LicensedRecord(
            problem_text=r[&apos;text&apos;],
            source_dataset=&apos;AIHub-71718&apos;,
            license_grade=&apos;A-&apos;,
            license_type=&apos;aihub-commercial&apos;,
            commercial_ok=True,
            training_eligible=True,
            sharealike_required=False,
            attribution_text=&apos;한국지능정보사회진흥원 사업결과&apos;
        ) for r in records]

class WikipediaAdapter(DataSourceAdapter):
    """CC BY-SA → Tier 2 강제 (paraphrase 필수)"""
    def fetch(self) -> List[LicensedRecord]:
        # SA 자료는 자동으로 paraphrase 큐로 이동
        return self._fetch_with_sa_flag()

SA·NC 자료 자동 격리
# SA·NC 자료를 학습 파이프라인에서 자동 분리
def quarantine_sa_nc(records: List[LicensedRecord]):
    """등급별로 자동 격리"""
    safe = []          # Tier 1 학습 데이터
    paraphrase = []    # Tier 2 paraphrase 큐
    eval_only = []     # Tier 0 평가 전용
    rejected = []      # 사용 불가

    for r in records:
        if not r.commercial_ok:
            rejected.append(r)
        elif r.sharealike_required:
            paraphrase.append(r)  # SA → 사실/표현 분리
        elif r.license_grade in (&apos;A+&apos;, &apos;A&apos;, &apos;A-&apos;):
            safe.append(r)
        else:
            eval_only.append(r)

    return safe, paraphrase, eval_only, rejected
6.3 [신규] 4-Tier 활용 전략
MathScope 데이터 활용의 4계층 분류. 각 Tier는 명확한 법적 근거와 운영 인프라를 갖습니다.
Tier 0 — 평가 전용 격리 환경 (즉시 시행)
항목
내용
대상
MathNet, NRICH 스타일, Wikipedia, Stack Exchange 등 SA·NC·추출금지
환경
Docker 컨테이너 격리 + egress 차단 + tmpfs (영구 저장 금지)
용도
AI 모델의 성능 평가 셋(eval set)만 / 학습·서비스 절대 금지
법적 보호
학술 페어유즈 + 변형적 사용 카테고리 → 가장 강한 보호
우선순위
Week 1 즉시 구축

# Tier 0 격리 환경 — Docker compose 예시
# /home/claude/docker-compose.tier0.yml
version: &apos;3.8&apos;
services:
  eval-only:
    image: mathscope/eval:latest
    container_name: tier0-eval-only
    network_mode: none           # 외부 호출 차단
    tmpfs:
      - /tmp:size=10G            # 영구 저장 금지
    volumes:
      - /data/eval-results:/output:rw  # 평가 결과만 외부 반출
    environment:
      - PURPOSE=evaluation_only
      - NO_LOGGING_OF_RAW_DATA=true
    command: python /app/run_eval.py
Tier 1 — 즉시 도입 학습 데이터 (1주차)
카테고리
데이터셋
백본 (커리큘럼 매핑)
NCIC 성취기준 + UK OGL + ACARA + Common Core
학습 데이터
NuminaMath 1.5 + PRM800K + GSM8K + MATH + OpenMathInstruct-1
한국어 보강
AI Hub 71718·71716·71859·479·71518
시각화
PhET (확률·통계)
검산 엔진
Lean Mathlib + Isabelle AFP + Metamath set.mm
국제 비교
Eduscol + NZ TKI + 일본 학습지도요령
Tier 2 — 사실/표현 분리 + 자체 paraphrase (2-4주차)
SA 자료의 ShareAlike 의무를 우회하는 핵심 패턴. "사실(facts)은 저작권 보호 대상 아님"이라는 법리(Feist v. Rural 1991, 한국 대법원 2000다61664)에 근거합니다.
# Tier 2 - 사실 추출 → 표현 자체 생성
from anthropic import Anthropic
from pydantic import BaseModel

class MathematicalFact(BaseModel):
    """수학적 본질만 추출 - 원본 표현 완전 분리"""
    domain: str                  # &apos;geometry&apos;, &apos;algebra&apos; 등
    subtopic: str                # &apos;circle_inscribed_angles&apos;
    given_conditions: list[str]  # 추상화된 조건
    unknown_quantity: str        # 구해야 할 양
    mathematical_structure: dict # 추상 구조
    difficulty_tier: int         # 1-7

def extract_facts_only(problem_text: str, client: Anthropic):
    """수학적 사실만 추출 (표현 분리)"""
    response = client.messages.create(
        model=&apos;claude-opus-4-7&apos;,
        max_tokens=2000,
        system=&apos;수학 콘텐츠 분석가. 수학적 구조와 사실만 추출. &apos;
               &apos;원본 표현·문장 구조·예시 시나리오는 모두 폐기.&apos;,
        messages=[{
            &apos;role&apos;: &apos;user&apos;,
            &apos;content&apos;: f&apos;다음 문제에서 수학적 사실만 JSON으로:\n{problem_text}&apos;
        }]
    )
    return MathematicalFact.model_validate_json(response.content[0].text)

def regenerate_korean_problem(fact: MathematicalFact, client: Anthropic):
    """추출된 사실로 한국 학생용 새 문제 생성"""
    response = client.messages.create(
        model=&apos;claude-opus-4-7&apos;,
        max_tokens=1000,
        system=&apos;한국 중·고등학생용 수학 문제 작성자. &apos;
               &apos;주어진 수학 구조로 완전히 새로운 한국어 문제 작성.&apos;,
        messages=[{
            &apos;role&apos;: &apos;user&apos;,
            &apos;content&apos;: f&apos;수학 구조:\n{fact.model_dump_json()}\n&apos;
                       f&apos;이 구조의 새 한국어 문제 작성.&apos;
        }]
    )
    return response.content[0].text

# 출력 가드레일 (Tier 2 산출물 검증)
def verify_no_overlap(generated, original):
    """8-gram 일치율 > 70% 시 재생성"""
    overlap = ngram_overlap(generated, original, n=8)
    if overlap > 0.7:
        return False  # 재생성 필요
    return True
Tier 3 — 정식 라이선싱 협상 (3-12개월)
규모 확장 시 협상이 필요한 자원들.
기관
접근 채널
협상 카드
대한수학회 KMO 사업단
kmo@kms.or.kr
비영리 R&D 명목, 공동 연구
KICE 한국교육과정평가원
kice.re.kr 정보공개청구
공공누리 부착 시민 청원 + 라이선스 협의
IMO Foundation
shaden@mit.edu → Sultan Albarakati(KAUST)
한국 IMO 후원 활동 연계
EBS 콘텐츠사업부
ebs.co.kr 기업/제휴
AI 수학 튜터 R&D용 라이선스
MAA (미국)
AMC 라이선싱 부서 직접
한국 영재 발굴 협력

비용 추정:
연간 라이선스: 5천만 원 ~ 2억 원 (사용자 수 기반)
일회성 협상 비용 + 변호사 검토: 추가 2-5천만 원
TIPS 매칭 시 "공식 파트너십" 가점 효과: 정성 평가 ★★★★★
6.4 비용 추정 — 전체 ETL
단계
비용 항목
월 추정
수집
AI Hub 다운로드 (무료) + HF 데이터셋 (무료)
0
분류 (로컬)
Qwen3-32B Ollama 추론 (Phaiakes9 전기료)
5만원
검증 (Claude)
Opus 4.7 API (어려운 케이스만)
30~50만원
paraphrase (Claude)
Tier 2 산출물 생성
20~30만원
가드레일
임베딩 + n-gram (로컬)
1만원
PostgreSQL
Phaiakes9 운영 (자체 호스팅)
2만원
총계
초기 데이터셋 구축 1회분
약 60~90만원

7. [신규] 위험 시나리오 4가지 정량 분석
B2C 상업 출시 후 발생 가능한 4가지 시나리오와 정량 손해 추정. TIPS 실사 시 변호사 의견서에 직접 활용 가능한 형식으로 정리했습니다.
7.1 시나리오 A — EBS Cease & Desist (확률 ★★★★★)
항목
내용
발생 조건
EBSi 강의·해설을 학습 데이터로 사용 후 베타 출시 → 사용자 5천 명 돌파 → EBS 모니터링 감지
진행
1) EBS → 회사 즉시 중단 요구서 발송 / 2) 30일 내 모든 EBS 파생 콘텐츠 제거 + 학습된 모델 격리 / 3) 응답 불충분 시 한국 법원 민사 + 형사 고소
민사 손해
§125의2 적용 - 영리·고의 시 1건당 최대 5,000만원. 실무상 EBS 콘텐츠 수십~수백 건 인정 → 수억~수십억원
형사 손해
§136(1) - 5년 이하 징역 또는 5천만원 이하 벌금. §140 비친고죄 → 합의 불가능
사업 손해
TIPS·VC 자금 회수, 임원 형사책임, 서비스 정지
7.2 시나리오 B — KICE/시·도교육청 합동 손해배상 (확률 ★★★★)
항목
내용
발생 조건
수능·모의평가·학력평가 기출을 변형 없이 그대로 서비스 → 평가원 또는 교육청 비교 분석
법적 근거
§32 단서 (영리 시험문제 활용 금지) + §93 (데이터베이스권) + §136 (형사처벌) + 2024년 8월 대법원 판결
민사 추정
평가원 KOGL 미부착 전 문항 잠재 손해 — 위자료 + 합리적 사용료
형사 추정
고의·영리·상습 → 비친고죄 직권 기소 → 실형 가능성 ↑
추가 위험
"평가원이 시비 걸면 모두 진다"는 업계 관행 — 가시성 높은 AI 학습이 가장 먼저 제재 대상
7.3 시나리오 C — 대한수학회 KMO 라이선싱 분쟁 (확률 ★★★)
항목
내용
발생 조건
KMO 기출을 학습/서비스 콘텐츠로 활용 → 사용자가 유사 문제 발견
법적 근거
kmo.or.kr "Copyright ⓒ 대한수학회 All Rights Reserved" 명시 + §32 단서
협상 가능성
KMO는 학회 비영리 사업이므로 EBS·천재교육보다 협상 여지 큼
권장 접근
"한국 수학 영재 교육 AI 향상 R&D" 명목으로 협업 제안 — 데이터셋 출처에 KMO 명기 + 공동 연구 제안
연락처
kmo@kms.or.kr
7.4 시나리오 D — MathNet 활용 후 MAA 또는 47개국 권리자 항의 (확률 ★★)
항목
내용
발생 조건
MathNet 데이터를 그대로 학습 → AMC/AIME/USAMO 문제 변형이 서비스에 노출
법적 근거
MAA 공식 정책 + 베른협약 내국민대우 → 한국 법원에서 한국법으로 보호
책임 구조
MIT는 DMCA Safe Harbor로 보호받음 → 영리 다운스트림 사용자(MathScope)에 책임 집중
권장
MathNet은 Tier 0 평가 셋만 활용 / 학습·서비스 사용 금지 / IMO 공식 본선만 별도 추출(~8% 비중)
7.5 시나리오 정량 비교 매트릭스

가이드 작성
활용 방식
형사 위험
민사 위험
A안 (어리석은 모험)
❌
그대로 사용
중
1-5억
B안 (최선의 보호)
✅
Tier 0 평가만
0
0
C안 (권장 패턴)
✅
Tier 2 paraphrase
매우 낮음
거의 없음
D안 (자살 행위)
✅
그대로 강행
매우 높음
수십~수백억

결론
가이드 v2.0을 작성한 이상, A안과 D안은 모두 위험.
가이드를 "무기"가 아닌 "방패"로 만들려면 → B안 또는 C안 + 변호사 의견서 패키지.

8. 법적 리스크 관리 + 선의 입증
8.1 TIPS 신청 시 IP 자료 템플릿
v1.0의 진술서 템플릿에 v2.0 신규 사항 반영.
# MathScope IP 안정성 진술서 (TIPS 신청용 v2)

## 1. 학습 데이터 라이선스 구성
- 영리 활용 가능: 95% 이상 (NuminaMath, PRM800K, AI Hub 등)
- 격리 평가용 (Tier 0): 5% 미만 (MathNet 등)
- 사실/표현 분리 (Tier 2): 별도 가드레일 적용
- SA·NC 자료 직접 사용: 0%
- 공공누리 AI유형 우선 활용

## 2. 라이선스 추적 시스템
- PostgreSQL dataset_licenses 테이블 운영
- 5-Layer 검증 자동화
- 분기별 IP 검토 회의

## 3. 출처 표시 의무 이행
- 앱 내 "데이터 출처" 페이지
- 모델 응답 시 출처 메타데이터 첨부
- AI Hub: "한국지능정보사회진흥원 사업결과" 명시

## 4. EU AI Act 컴플라이언스
- 학습 데이터 라이선스 메타데이터 영구 보존
- 고위험 시스템 분류 시 즉시 대응 가능한 아키텍처

## 5. 한국 AI 기본법 대응 (2026)
- 데이터셋 메타데이터 컬럼: license_grade, source_url,
  license_verified_at, ai_type_attached
- 학습 출력 가드레일 (n-gram + 임베딩)

## 6. 외부 IP 변호사 검토 완료
- 1차 의견서: [날짜], [법무법인명]
- 결론: "적법한 영리 활용 범위 확인"
8.2 변호사 검토 체크리스트
외부 IP 법무법인 선정 가이드:
법무법인
특징
추정 비용
대륜
IP 전문, 저작권 침해 다수 경험
1차 의견서 500-1,000만원
광장
대형 로펌 IP팀, EdTech 경험
1,500-3,000만원
김앤장
최대 로펌 IP, 국제 라이선싱
2,000-5,000만원
인평
저작권 특화, 신생 EdTech 친화
500-1,500만원

의뢰 시 첨부 자료:
본 가이드 v2.0 전체
ETL 파이프라인 아키텍처 다이어그램
Tier 0-3 활용 정책 문서
PostgreSQL dataset_licenses 스키마 + 초기 데이터
출처 표시 화면 시안 (앱 UI 캡처)
선의 입증 패키지 (Day 1-7 산출물)
8.3 보험과 리스크 헤지
IP 분쟁 시 리스크를 분산하는 방어 수단.
E&O (Errors & Omissions) 보험 — 콘텐츠 라이선스 분쟁 커버
IP 침해 책임보험 — 손해배상 시 일부 보전
법무 자문 연간 계약 — 월 200-500만원 고정 비용으로 즉시 대응
8.4 [신규] Attorney-Client Privilege 활용
가이드 v2.0 작성 사실 자체가 Red Flag Knowledge 증거가 될 수 있는 역설을 해소하는 핵심 전략.
일반 회사 문서 vs 변호사 의견서
구분
일반 회사 문서
변호사 의견서
디스커버리 시
강제 제출
Attorney-Client Privilege 보호
원고 변호사 사용
그대로 사용 가능
자발적 공개 전까지 사용 불가
법원 효과
Red Flag 입증 증거
선의 입증 + 법리 착오 항변
MathScope 적용
위험
안전
실행 방법 (5단계)
외부 IP 변호사 선임 (TIPS 신청 3개월 전)
변호사가 가이드 v2.0 검토 후 자문 의견서 발행
가이드 v2.0 자체는 변호사 의견서의 별첨자료로 첨부
회사 내부 문서로는 "변호사 자문 결과 정책 v1.0" 형태로 재작성
원본 가이드는 변호사 사무소에 보관 (attorney work product)
가장 중요한 한 가지
가이드 v2.0을 "삭제"하거나 "없던 일"로 만드는 것이 가장 위험합니다.
디지털 흔적 완전 삭제 불가 (git history, backup, AI assistant logs)
발견 시 "은폐 시도" → 형사처벌 가중 + 양형 ↑↑
한국 형법상 증거인멸 별도 처벌 가능
→ 변호사 의견서의 별첨자료로 격상하는 것이 정답
8.5 [신규] 선의 입증 패키지
양형위원회 권고 양형 요소를 충족시키는 6개 핵심 자료. 침해 분쟁 시 합의·감경의 결정적 근거.
순번
자료
법적 효과
1
가이드 v2.0 (위험 인지 + 정확한 분석)
주의의무 이행 입증
2
변호사 자문 의견서 (법리 검토 + 권고)
법리 착오 항변
3
Tier 0-3 활용 정책 문서
선의 입증
4
격리 환경 인프라 증빙 (Docker, 네트워크 정책)
물리적 분리 입증
5
라이선싱 협상 시도 기록 (발송 메일)
성실 협상 노력
6
직원 교육 자료 + 서명 (저작권 준수)
조직 문화 입증

법원 효과 (양형위원회 권고):
"법리 착오" 항변 강력
"미필적 고의" 부정 가능
양형 50-70% 감경 가능
합의 협상 시 권리자도 선의 인정 가능성 ↑

9. PostgreSQL 운영 스키마 v2
v1.0 스키마에 5-Layer 추적 + 공공누리 AI유형 + 위험 점수 자동 평가 추가.
9.1 전체 스키마
-- ============================================
-- MathScope dataset_licenses v2 (2026-05-27)
-- 5-Layer 라이선스 추적 + AI유형 + 위험 자동 평가
-- ============================================

-- 1. 데이터셋 컴파일 레이어 (Layer 1)
CREATE TABLE dataset_layer (
    dataset_id              SERIAL PRIMARY KEY,
    dataset_name            VARCHAR(200) NOT NULL,
    compiler                VARCHAR(200),     -- &apos;MIT CSAIL / KAUST&apos;
    compilation_license     VARCHAR(50),      -- &apos;apache-2.0&apos;, &apos;kogl-ai&apos;
    compilation_grade       CHAR(2),          -- &apos;A+&apos;, &apos;A&apos;, &apos;A-&apos;, &apos;B&apos;, &apos;C&apos;, &apos;D&apos;, &apos;E&apos;
    has_takedown_policy     BOOLEAN,          -- takedown 운영 = 위험 신호
    inner_content_cleared   BOOLEAN,          -- 원본 사전 클리어 여부
    ai_type_attached        BOOLEAN,          -- 공공누리 AI유형 (2026 신규)
    source_url              VARCHAR(500),
    risk_score              SMALLINT,         -- 0-100
    license_verified_at     TIMESTAMP,
    notes                   TEXT,
    created_at              TIMESTAMP DEFAULT NOW()
);

-- 2. 개별 문제 원본 추적 (Layer 2-5)
CREATE TABLE problem_provenance (
    problem_id              BIGSERIAL PRIMARY KEY,
    dataset_id              INT REFERENCES dataset_layer(dataset_id),
    source_country          CHAR(2),          -- &apos;KR&apos;, &apos;US&apos;, &apos;CN&apos;
    source_organization     VARCHAR(200),     -- &apos;대한수학회&apos;, &apos;MAA&apos;
    source_competition      VARCHAR(100),     -- &apos;KMO&apos;, &apos;AMC10&apos;, &apos;IMO&apos;
    source_year             INT,
    source_round            VARCHAR(50),      -- &apos;final&apos;, &apos;shortlist&apos;, &apos;tst&apos;
    -- 5-Layer 검증
    layer1_compilation_pass BOOLEAN,
    layer2_original_pass    BOOLEAN,
    layer3_solution_pass    BOOLEAN,
    layer4_kr_exam_law_pass BOOLEAN,
    layer5_berne_pass       BOOLEAN,
    -- 종합 판정 (자동 계산)
    all_layers_pass         BOOLEAN GENERATED ALWAYS AS (
        layer1_compilation_pass AND layer2_original_pass AND
        layer3_solution_pass AND layer4_kr_exam_law_pass AND
        layer5_berne_pass
    ) STORED,
    -- 활용 등급
    usage_tier              SMALLINT,         -- 0=eval, 1=safe, 2=paraphrase, 3=licensed
    created_at              TIMESTAMP DEFAULT NOW()
);

-- 3. 라이선스 변경 이력
CREATE TABLE license_history (
    id                      BIGSERIAL PRIMARY KEY,
    dataset_id              INT REFERENCES dataset_layer(dataset_id),
    detected_at             TIMESTAMP DEFAULT NOW(),
    previous_hash           CHAR(64),
    current_hash            CHAR(64),
    change_summary          TEXT,
    alert_sent              BOOLEAN DEFAULT FALSE
);

-- 4. 위험 자동 평가 뷰
CREATE VIEW v_risk_assessment AS
SELECT
    d.dataset_name,
    d.compilation_grade,
    d.has_takedown_policy,
    d.inner_content_cleared,
    d.ai_type_attached,
    d.risk_score,
    COUNT(p.problem_id) AS total_problems,
    SUM(CASE WHEN p.all_layers_pass THEN 1 ELSE 0 END) AS safe_problems,
    ROUND(100.0 * SUM(CASE WHEN p.all_layers_pass THEN 1 ELSE 0 END)
          / NULLIF(COUNT(p.problem_id), 0), 2) AS safe_ratio_pct,
    CASE
        WHEN d.risk_score >= 80 THEN &apos;🔴 고위험: 즉시 격리&apos;
        WHEN d.risk_score >= 50 THEN &apos;🟡 중위험: Tier 2 처리&apos;
        WHEN d.risk_score >= 20 THEN &apos;🟢 저위험: 통상 활용&apos;
        ELSE &apos;✅ 안전: 정식 활용 가능&apos;
    END AS risk_label
FROM dataset_layer d
LEFT JOIN problem_provenance p ON d.dataset_id = p.dataset_id
GROUP BY d.dataset_id;
9.2 초기 데이터 입력
-- 안전 자원 (Tier 1)
INSERT INTO dataset_layer (dataset_name, compiler, compilation_license,
    compilation_grade, has_takedown_policy, inner_content_cleared,
    ai_type_attached, source_url, risk_score) VALUES
(&apos;NuminaMath-1.5&apos;, &apos;AI-MO&apos;, &apos;apache-2.0&apos;, &apos;A&apos;, false, true, false,
 &apos;https://huggingface.co/datasets/AI-MO/NuminaMath-1.5&apos;, 10),
(&apos;PRM800K&apos;, &apos;OpenAI&apos;, &apos;mit&apos;, &apos;A&apos;, false, true, false,
 &apos;https://github.com/openai/prm800k&apos;, 5),
(&apos;AIHub-71718&apos;, &apos;한국지능정보사회진흥원&apos;, &apos;aihub-commercial&apos;, &apos;A-&apos;,
 false, true, false, &apos;https://aihub.or.kr&apos;, 15),
(&apos;NCIC 성취기준&apos;, &apos;교육부&apos;, &apos;sovereign-immunity&apos;, &apos;A+&apos;,
 false, true, false, &apos;https://ncic.re.kr&apos;, 0),

-- 위험 자원 (Tier 0 격리)
(&apos;MathNet&apos;, &apos;MIT CSAIL/KAUST/HUMAIN&apos;, &apos;apache-2.0&apos;, &apos;A&apos;,
 true, false, false, &apos;https://mathnet.csail.mit.edu&apos;, 85),

-- 영리 차단 자원 (적재 거부 - 참조용으로만 기록)
(&apos;EBS 수능특강&apos;, &apos;EBS&apos;, &apos;ebs-proprietary&apos;, &apos;D&apos;,
 false, true, false, &apos;https://ebsi.co.kr&apos;, 100),
(&apos;KMO 대한수학회&apos;, &apos;대한수학회&apos;, &apos;all-rights-reserved&apos;, &apos;C&apos;,
 false, true, false, &apos;https://kmo.or.kr&apos;, 90);
9.3 운영 쿼리 예시
-- 1. 안전 자원만 사용 가능한 문제 ID 추출
SELECT p.problem_id, d.dataset_name
FROM problem_provenance p
JOIN dataset_layer d ON p.dataset_id = d.dataset_id
WHERE p.all_layers_pass = TRUE
  AND p.usage_tier IN (1, 3)  -- safe or licensed
ORDER BY d.compilation_grade;

-- 2. 위험 점수 80+ 데이터셋 검색 (즉시 격리 필요)
SELECT * FROM v_risk_assessment WHERE risk_score >= 80;

-- 3. 공공누리 AI유형 부착 자료만 조회
SELECT dataset_name, source_url
FROM dataset_layer WHERE ai_type_attached = TRUE;

-- 4. EU AI Act 컴플라이언스 보고서 자동 생성
SELECT
    d.dataset_name,
    d.compilation_license,
    d.license_verified_at,
    COUNT(p.problem_id) AS problems_used
FROM dataset_layer d
JOIN problem_provenance p ON d.dataset_id = p.dataset_id
WHERE p.usage_tier IN (1, 2, 3)  -- 평가용 제외
GROUP BY d.dataset_id
ORDER BY problems_used DESC;

10. 모니터링·갱신 체계
10.1 라이선스 변경 자동 감지
월 1회 cron으로 라이선스 페이지의 해시값 변경을 감지하는 자동화 스크립트.
# 라이선스 변경 자동 감지 (월 1회 cron)
import hashlib, requests
from datetime import datetime
import psycopg2

MONITORED_URLS = {
    &apos;NuminaMath&apos;: &apos;https://huggingface.co/datasets/AI-MO/NuminaMath-1.5&apos;,
    &apos;MathNet&apos;: &apos;https://mathnet.csail.mit.edu&apos;,
    &apos;AIHub&apos;: &apos;https://aihub.or.kr/intrcn/guid/usagepolicy.do&apos;,
    &apos;KOGL&apos;: &apos;https://www.kogl.or.kr/info/license.do&apos;,
    &apos;IMO&apos;: &apos;https://www.imo-official.org&apos;,
    &apos;KMO&apos;: &apos;https://www.kmo.or.kr&apos;,
    &apos;KICE&apos;: &apos;https://www.kice.re.kr/sub/info.do?m=0703&apos;,
}

def check_license_changes():
    conn = psycopg2.connect(dsn=&apos;postgresql://localhost/mathscope&apos;)
    cursor = conn.cursor()
    alerts = []

    for name, url in MONITORED_URLS.items():
        try:
            r = requests.get(url, timeout=30)
            current_hash = hashlib.sha256(r.text.encode()).hexdigest()

            cursor.execute(&apos;&apos;&apos;
                SELECT current_hash FROM license_history
                WHERE dataset_id = (SELECT dataset_id FROM dataset_layer
                                    WHERE dataset_name = %s)
                ORDER BY detected_at DESC LIMIT 1
            &apos;&apos;&apos;, (name,))
            row = cursor.fetchone()
            previous_hash = row[0] if row else None

            if previous_hash and previous_hash != current_hash:
                alerts.append(f&apos;⚠️ {name} 라이선스 변경 감지&apos;)
                # 즉시 Slack/이메일 알림
                send_alert(name, url, previous_hash, current_hash)

            cursor.execute(&apos;&apos;&apos;
                INSERT INTO license_history
                (dataset_id, previous_hash, current_hash, detected_at)
                VALUES (
                    (SELECT dataset_id FROM dataset_layer WHERE dataset_name = %s),
                    %s, %s, NOW())
            &apos;&apos;&apos;, (name, previous_hash, current_hash))
        except Exception as e:
            print(f&apos;{name} 확인 실패: {e}&apos;)

    conn.commit()
    return alerts
10.2 분기별 IP 검토 회의
회의 어젠다:
지난 분기 라이선스 변경 사항 (license_history 테이블 리뷰)
신규 도입 데이터셋 등급 분류 (Layer 1-5 검증)
공공누리 AI유형 신규 부착 자료 조사
Tier 0-3 분포 변화 (안전 비율 추세)
라이선싱 협상 진행 상황 (KMO, KICE, EBS, IMO Foundation)
외부 변호사 의견서 갱신 필요성
EU AI Act / 한국 AI 기본법 시행 상황 모니터링
10.3 신규 데이터셋 도입 절차 (10단계)
후보 데이터셋 발견 → README/약관 1차 검토
라이선스 등급 임시 판정 (Layer 1)
원본 저작권 추적 (Layer 2-3)
한국법 §32 단서 적용 가능성 (Layer 4)
베른협약 적용 (Layer 5)
위험 점수 계산 → Tier 분류
외부 변호사 의견 청취 (위험 점수 50+ 시)
PostgreSQL dataset_layer 적재
초기 100개 샘플로 가드레일 테스트
정식 도입 또는 격리 결정

11. 즉시 실행 액션 (Week 1)
Day 1-2: 데이터셋 라이선스 메타데이터 인프라
PostgreSQL dataset_layer + problem_provenance 테이블 생성
Tier 1 데이터셋 14개에 대해 license_url, license_verified_at 기록
공공누리 AI유형 부착 여부 별도 컬럼(ai_type_attached) 기록
v_risk_assessment 뷰 작동 검증
Day 3-4: 격리 환경 구축 증빙
Docker compose 파일 + git commit 기록 (Tier 0 격리 증빙)
네트워크 정책 캡처 (egress 차단)
사용 정책 문서 작성 + 직원 1회 30분 교육 + 서명
Phaiakes9에 컨테이너 배포 후 운영 로그 확보
Day 5: 라이선싱 협상 채널 오픈
대한수학회 KMO 사업단(kmo@kms.or.kr) 협업 제안 메일 발송
한국교육과정평가원 정보공개청구 시스템 등록
EBS 콘텐츠사업부 라이선싱 문의
IMO Foundation 경로(shaden@mit.edu) 협력 제안
모든 발송·회신 기록을 "선의 입증 패키지 v0.1" 폴더에 보관
Day 6-7: 외부 IP 변호사 1차 의견서
한국 IP 전문 법무법인 3~5곳 견적 의뢰 (대륜, 광장, 김앤장, 인평)
1차 의견서 비용: 500-1,000만 원 (2주 소요 예상)
가이드 v2.0을 변호사 의견서의 별첨자료로 정리 → Attorney-Client Privilege 보호
TIPS 신청서 IP 섹션 1차 초안 작성

부록 A — 약어·용어 정리
약어
정식 명칭
설명
NCIC
National Curriculum Information Center
국가교육과정정보센터
KICE
Korea Institute for Curriculum & Evaluation
한국교육과정평가원
EBS
Educational Broadcasting System
한국교육방송공사
KOGL
Korea Open Government License
공공누리
KMO
Korean Mathematical Olympiad
한국수학올림피아드
IMO
International Mathematical Olympiad
국제수학올림피아드
MAA
Mathematical Association of America
미국수학협회
AMC
American Mathematics Competitions
미국수학경시
AIME
American Invitational Mathematics Examination
AMC 후속 시험
USAMO
USA Mathematical Olympiad
미국 수학 올림피아드
CC BY
Creative Commons Attribution
출처 표시 허용
CC BY-SA
CC BY Share-Alike
동일 조건 재배포
CC BY-NC
CC BY Non-Commercial
비영리 한정
DMCA
Digital Millennium Copyright Act
미국 디지털 저작권법
OSP
Online Service Provider
온라인 서비스 제공자
TDM
Text and Data Mining
텍스트·데이터 마이닝
E&O
Errors & Omissions Insurance
전문직 책임보험
TIPS
Tech Incubator Program for Startup
민간 주도 기술창업 프로그램
부록 B — 핵심 URL 모음
법령·제도:
공공누리 KOGL: https://www.kogl.or.kr/info/license.do
AI Hub 이용정책: https://aihub.or.kr/intrcn/guid/usagepolicy.do
한국교육과정평가원 저작권: https://www.kice.re.kr/sub/info.do?m=0703
교육부 공공누리 안내: https://www.moe.go.kr
문체부 생성형 AI 공정이용 안내서 (2026-02-26): mcst.go.kr
문체부 저작권국: https://www.copyright.or.kr

국제 표준:
IMO 공식: https://www.imo-official.org/
MathNet: https://mathnet.csail.mit.edu
UK National Curriculum (OGL): https://www.gov.uk/government/collections/national-curriculum
Common Core: https://www.thecorestandards.org/
ACARA (Australia): https://www.australiancurriculum.edu.au/

데이터셋:
NuminaMath: https://huggingface.co/datasets/AI-MO/NuminaMath-1.5
PRM800K: https://github.com/openai/prm800k
GSM8K: https://github.com/openai/grade-school-math
MATH: https://github.com/hendrycks/math
Hugging Face Hub: https://huggingface.co/datasets

형식수학:
Lean Mathlib: https://leanprover-community.github.io/
Isabelle AFP: https://www.isa-afp.org/
Metamath: https://us.metamath.org/
부록 C — 관계 기관 연락처
기관
연락처
용도
대한수학회 KMO 사업단
kmo@kms.or.kr
KMO 비영리 R&D 협력 제안
한국교육과정평가원 (KICE)
kice.re.kr 정보공개청구
수능·모의평가 KOGL 부착 요청
EBS 콘텐츠사업부
ebs.co.kr 기업/제휴 문의
수능특강·연계 교재 라이선싱
MathNet (MIT)
shaden@mit.edu
IMO Foundation 경로 + MathNet 협력
공공누리 (KOGL)
1670-0052
AI유형 부착 자료 검색 지원
AI Hub
aihub.or.kr 문의하기
데이터셋별 상업 사용 확인
문화체육관광부 저작권국
mcst.go.kr
공정이용 가이드라인 문의
한국저작권위원회
copyright.or.kr
저작권 등록·분쟁 조정
IMO Foundation
info@imo-official.org
국제수학올림피아드 라이선싱
MAA AMC 라이선싱
amcinfo@maa.org
AMC/AIME/USAMO 라이선싱
부록 D — 변경 이력 상세
v2.0 (2026-05-27) → v1.0 대비 변경 요약
섹션
v1.0
v2.0 변경 사항
§1.2 한국법
3개 조항
8개 조항 (§32, §93, §125-2, §136, §140 추가)
§1.5 AI 동향
EU AI Act 중심
공공누리 AI유형, 문체부 안내서, AI 기본법 추가
§1.6 5-Layer
없음
신설
§1.7 DMCA 비대칭
없음
신설
§1.8 2024 대법원
없음
신설
§3.5 MathNet
없음
신설 (5-Layer 케이스 스터디)
§3.6 AI Hub
없음
신설 (한국 수학 데이터셋)
§3.7 공공누리 AI유형
없음
신설
§4.1 한국
추상적 설명
4중 구조(교육부/KICE/EBS/시도교육청) + 사설 영역 + KMO
§4.5 미국 MAA
없음
신설
§5 전체 매트릭스
없음
신설 (7개 카테고리 70+ 자원)
§6.3 4-Tier 전략
없음
신설 (Tier 0-3)
§7 위험 시나리오
없음
신설 (4개 시나리오 정량 분석)
§8.4 Attorney-Client
없음
신설
§8.5 선의 입증 패키지
없음
신설
§9 PostgreSQL
단일 테이블
5-Layer 추적 + AI유형 + 위험 자동 평가 뷰
부록 C 연락처
없음
신설 (10개 기관)
법령 인용 갱신 일자
한국 저작권법: 2026년 5월 기준
EU AI Act: 2024년 발효, 2026년 단계 적용
한국 AI 기본법: 2026년 시행
공공누리 AI유형: 2026-01-28 신설
문체부 생성형 AI 공정이용 안내서: 2026-02-26 발간
실시간 약관 확인 일자: 2026-05-27

면책 조항
본 가이드는 MathScope/WhyMath 프로젝트의 자체 운영 참조 문서이며, 법률 자문이 아닙니다. 실제 영리 활용 전에는 반드시 외부 IP 변호사의 정식 의견서를 별도로 확보하시기 바랍니다. 본 가이드의 등급 분류와 위험 추정은 2026-05-27 기준 공개 자료를 바탕으로 한 작성자의 분석이며, 법원의 최종 판단을 대체하지 않습니다.

작성: Kiki (강원특별자치도 공공보건의료지원단 / MathScope 프로젝트)
자문: Claude Opus 4.7 (Anthropic) — Tier 0-3 분류 체계 공동 설계
문서 보관: 변호사 의견서 별첨자료 (Attorney-Client Privilege)
