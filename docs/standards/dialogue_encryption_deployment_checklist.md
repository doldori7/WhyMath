# 대화 암호화 배포 체크리스트 (SEC-01)

> **성격**: 미성년자 대화·손글씨 데이터의 at-rest 암호화가 **배포 환경에서 실제로 켜져 있는지**를
> 확인하는 절차. CLAUDE.md 절대 금기("미성년자 채팅 데이터를 평문으로 저장 금지")의 운영 시행이다.
>
> **한 줄**: 키가 없으면 코드가 조용히 평문으로 쓰던 구간이 있었다. 이제 프로덕션에서는 거부하고,
> 이 문서가 그 거부를 우회하지 않고 *제대로 켜는* 절차를 고정한다.

---

## 0. 무엇이 암호화되는가

`dialogue_turn`의 세 축이 **같은 키**(`WHYMATH_DIALOGUE_CONTENT_ENCRYPTION_KEY`)로 AES-256-GCM
봉투 암호화된다:

| 컬럼 | 내용 | 암호화 컬럼 |
|---|---|---|
| `content` | 미성년 채팅 본문 | `content_encrypted` · `content_nonce` |
| `image_uri` | 손글씨 풀이 이미지 URI | `image_uri_encrypted` · `image_uri_nonce` |
| `image_analysis` | Qwen3-VL 분석(JSONB) | `image_analysis_encrypted` · `image_analysis_nonce` |

**키를 하나로 둔 이유**: 같은 테이블·같은 요청·같은 데이터 주체라 키를 쪼개도 폭발 반경이 실질적으로
줄지 않는 반면, 키가 늘면 "미설정 → 평문 폴백" 함정이 하나 더 생긴다.

암호화 행에서는 **평문 컬럼이 NULL**이고, 기존/비활성 행은 평문을 유지한다(dual-read 폴백).
마스터 키는 DB 밖(env)에 있어 **DB dump 단독으로는 복호 불가**하다.

기존 평문 행 전환은 백필 CLI가 담당하며 **세 축을 함께** 처리한다:
```powershell
# 실행 시스템: Windows PowerShell (Phaiakes9 = Kiki의 작업 PC 그 자체)
cd C:\Users\kiki\Desktop\__AI\WhyMath\src\backend
python -m whymath_backend.privacy.dialogue_content_backfill
```
본문만 전환하면 `{"reencrypted": N}` 출력이 "평문 전환 완료"로 읽히는데 이미지 평문은 남는다 —
**부분 처리를 완전 처리로 위장**하지 않도록 세 축을 한 배치에서 같이 전환한다. 전환 여부는
출력 숫자가 아니라 §3 쿼리로 확인한다(간접 신호 금지).

---

## 1. 기계 게이트 — 프로덕션 fail-closed (자동)

`api/_crypto.py::require_dialogue_content_cipher`가 **프로덕션 추정 환경에서 키가 없으면
`RuntimeError`** 를 낸다. 대화 쓰기·읽기·GDPR export 세 경로가 모두 이 빌더를 쓴다.

- **프로덕션 판별**: 실 OAuth provider(kakao/naver) 구성 여부 — 새 env 축을 만들지 않고 기존
  "prod 추정" 신호를 재사용한다(`api/demo_auth.py::register_demo_provider` 선례). 프로덕션에는 항상
  실 provider가 있고 개발·CI에는 없다.
- **개발·CI는 영향 없음** — provider 미구성이므로 평문 폴백이 그대로 허용된다.

### 1-2. 스키마 버전 가드 (SEC-03 — 키 게이트가 못 막던 구멍)

**키 게이트는 마이그레이션 미적용을 막지 못한다.** SEC-02 실측(2026-07-27)이 그 조합을 실물로
확인했다 — 대상 DB가 `f3a4b5c6d7e8`(2026-06-30)에 머물러 `content_encrypted` 컬럼 자체가
없었다. 키만 설정되고 스키마가 뒤처지면 암호화 write가 런타임에 터지거나 배포 순서에 따라
조용히 어긋난다.

`db/schema_version.py::verify_schema_version`이 **기동 시**(`app.py` lifespan) DB
`alembic_version`을 코드 기대 head와 대조한다:

| 상태 | 프로덕션 | 개발·CI |
|---|---|---|
| 일치 | 통과(무음) | 통과(무음) |
| **뒤처짐**(코드가 아는 이전 리비전·미적용) | **기동 거부** | 경고 후 계속 |
| 앞섬(코드가 모르는 리비전) | 경고 후 계속 | 경고 후 계속 |
| 확인 불가(DB 미도달 등) | **기동 거부**(예외 타입명 로그) | 경고 후 계속 |

**앞섬을 막지 않는 이유**: 코드만 되돌리고 DB는 앞선 상태로 두는 것이 정상 롤백이다. 엄격
동일성 가드는 그 정상 상태에서 부팅을 거부해 **가드 자체가 장애 원인**이 된다.

따라서 §2 체크리스트에 **`alembic upgrade head`가 키 설정보다 선행**해야 한다.

체크리스트는 사람이 기억해야 작동하지만 이 게이트들은 잊어도 작동한다. 아래 §2는 그 게이트를
*통과시키는* 절차이지, 게이트를 대체하는 절차가 아니다.

---

## 2. 배포 전 확인 (환경별 1회 + 키 회전 시)

- [ ] **`alembic upgrade head`를 먼저 적용했다** — 암호화 컬럼이 없는 DB에 키만 설정하면
      기동이 거부된다(§1-2 가드). 순서는 *마이그레이션 → 키 → 기동*이다.
- [ ] `WHYMATH_DIALOGUE_CONTENT_ENCRYPTION_KEY`가 설정돼 있다(base64 32바이트 = AES-256).
- [ ] 키가 **코드·저장소에 없다** — env/시크릿 매니저로만 주입(CLAUDE.md 하드코딩 금지).
- [ ] 키 백업이 있다 — **키를 잃으면 기존 암호화 행은 영구 복호 불가**다(마이그레이션 다운그레이드로도
      복구되지 않는다).
- [ ] **프리플라이트 CLI가 PASS(exit 0)** — 아래 §2.1. 위 두 줄(왕복·저장 표현)을 한 명령이
      함께 판정한다.
- [ ] (키 회전 시) 구 키를 `WHYMATH_DIALOGUE_CONTENT_DECRYPTION_FALLBACK_KEYS`에 남겼다 —
      빠뜨리면 기존 행이 복호 불가(lockout)가 된다.

### 키 생성
```powershell
# 실행 시스템: Windows PowerShell (Phaiakes9 = Kiki의 작업 PC 그 자체)
cd C:\Users\kiki\Desktop\__AI\WhyMath
python -c "import base64,os;print(base64.b64encode(os.urandom(32)).decode())"
```
출력된 문자열 전체가 키다. **생략 문자(`…`)가 섞이지 않았는지** 확인하고 그대로 설정한다
(2026-07-16 자리표시자 키 사고 재발 방지).

---

## 2.1 프리플라이트 — "왕복 성공"을 암호화의 증거로 착각하지 않는 단일 명령

**왜 왕복만으로는 안 되는가**: 키가 없으면 코드는 *평문 폴백*으로 동작하고 왕복은 **그대로
성공한다**. 왕복만 확인하면 "성공"을 보면서 미성년 평문을 흘린다. 그래서 이 CLI는 왕복과
**저장 표현**(암호문/평문 증가분)을 함께 보고, 평문이 늘면 exit 1을 낸다.

### 모드 — 무엇이 증명되는지가 다르다

| 모드 | 증명하는 것 | 증명하지 *못하는* 것 |
|---|---|---|
| `direct`(기본) | 키 구성·스키마·암복호 경로 | **서버 프로세스가 같은 키를 보는지** |
| `--via-api` | *기동 중인 서버*가 실제로 암호화하는지 | — |

배포 검증은 **반드시 `--via-api`** 로 한다. CLI에만 키가 있고 서버엔 없는 "절반만 성립"이
실제로 일어나며(2026-07-16 교훈), `direct`는 그 경우 PASS를 낸다.

### 실행 (창 ① — 서버가 이미 떠 있는 상태에서 *별도* 창)

```powershell
# 실행 시스템: Windows PowerShell (Phaiakes9 = Kiki의 작업 PC 그 자체)
# 선행 조건: 마이그레이션 적용 완료 + 키 설정 + 서버 기동 중(서버 창은 건드리지 않는다)
cd C:\Users\kiki\Desktop\__AI\WhyMath\src\backend
python -m whymath_backend.ops.dialogue_encryption_preflight --via-api `
  --api-url http://127.0.0.1:8000 --token 여기에_실제_로그인_토큰_전체
```

**토큰은 실제 로그인으로 얻는다.** 프로덕션에서는 데모 인증이 **거부**된다 — 실 OAuth
provider가 구성돼 있으면 `api/demo_auth.py::register_demo_provider`가 가짜 provider 등록을
막는다(이중 방어). 따라서 카카오/네이버로 실제 로그인한 세션의 access token을 쓴다.

서버가 아직 없는 환경에서 키·스키마만 먼저 보려면 인자 없이 실행한다(`direct` 모드):

```powershell
# 실행 시스템: Windows PowerShell
cd C:\Users\kiki\Desktop\__AI\WhyMath\src\backend
python -m whymath_backend.ops.dialogue_encryption_preflight
```

### 판정

```
  판정          : PASS     → exit 0. 다음 단계로.
  판정          : FAIL     → exit 1. 출력의 ✗ 줄이 고칠 대상을 지목한다.
```

`--via-api`에서 "평문 저장이 늘었습니다 — 키가 **서버 프로세스**에 붙지 않았습니다"가 나오면
CLI 창의 키가 아니라 **서버를 띄운 창/서비스의 env**를 고치고 서버를 재시작해야 한다.

프로브가 만든 대화 행은 검사 후 자동 삭제된다. 삭제가 실패하면 그 사실과 `dialogue_id`를
출력에 남긴다(조용히 넘어가지 않는다).

---

## 3. 실측 쿼리 — 누적 상태 확인·기록용

§2.1 프리플라이트가 *증가분*으로 판정한다면, 이 쿼리는 **테이블의 누적 상태**를 본다 —
SEC-02 실측 기록(§4)에 남길 수치가 이것이다. 프리플라이트가 내부에서 쓰는 술어와 동일하다.

설정 여부만 보면 오타·미반영을 놓친다. **실제 행**을 본다:

```sql
-- 신규 행이 암호화됐는가: encrypted_rows > 0 이고 plaintext_rows 가 늘지 않아야 한다
SELECT
  count(*) FILTER (WHERE content_encrypted IS NOT NULL)          AS content_encrypted_rows,
  count(*) FILTER (WHERE content IS NOT NULL)                    AS content_plaintext_rows,
  count(*) FILTER (WHERE image_uri_encrypted IS NOT NULL)        AS image_uri_encrypted_rows,
  count(*) FILTER (WHERE image_uri IS NOT NULL)                  AS image_uri_plaintext_rows,
  count(*) FILTER (WHERE image_analysis_encrypted IS NOT NULL)   AS analysis_encrypted_rows,
  -- SEC-04: `IS NOT NULL`만 쓰면 **JSONB 스칼라 null**("분석 없음" 행)이 평문으로 계수돼
  -- "암호화 안 됨" 거짓경보가 난다. 실제 값이 있는 행만 센다.
  count(*) FILTER (WHERE jsonb_typeof(image_analysis) NOT IN ('null'))
                                                                 AS analysis_plaintext_rows
FROM dialogue_turn;
```

> `jsonb_typeof(NULL)`은 SQL NULL을 돌려주고 `NOT IN`은 NULL에서 참이 되지 않으므로, SQL NULL
> 행과 JSONB `null` 행이 함께 제외된다 — 둘 다 "분석 없음"이라 평문 데이터가 아니다.

**판정**: 암호화 도입 *이후* 생성된 행은 평문 카운트가 늘지 않아야 한다. 평문 카운트가 계속 는다면
키가 실제로는 안 붙은 것이다(설정값 오타·프로세스 미재시작·다른 env 파일 로드 등).

---

## 4. 남은 것 — 프로덕션 실측은 아직 수행되지 않았다

SEC-01의 acceptance는 "프로덕션 `dialogue_content_encryption_key` 설정 실측 포함"을 요구하지만,
**그 실측은 Kiki 머신(Phaiakes9)에서만 가능하다** — 이 세션의 컨테이너에는 프로덕션 DB·env가 없다.
따라서 이 문서는 절차를 고정할 뿐이며, **실측이 끝났다고 주장하지 않는다.**

수행 절차는 `docs/runbooks/` 대신 이 문서 §2 → **§2.1(프리플라이트 `--via-api` PASS)** → §3
순서로 쓴다. 실측 결과(§3 쿼리 출력)를 확보하면 이 절 아래에 날짜·수치와 함께 기록한다.

추적: **`SEC-02-prod-dialogue-key-measurement`**(owner=kiki) — 구두 인계로 흘리지 않도록
백로그에 등재했다. 이 절에 수치가 기록되는 시점이 그 태스크의 done 조건이다.

> **미실측 상태 표기(2026-07-26)**: 프로덕션 키 설정 여부 **미확인**. 기계 게이트(§1)가 프로덕션
> 추정 환경에서 키 부재를 막고 있으므로 *조용한 평문 저장*은 차단되나, "키가 실제로 설정돼 있고
> 행이 암호화되고 있다"는 **양성 증거는 아직 없다**. 없음을 없다고 적는다.

> **실측 시도(2026-07-27 · Kiki Phaiakes9 `whymath-pg`)**: **프로덕션 환경 부재 확인 → 실측 불가**.
> `docker exec whymath-pg psql` 로 §2·§3 절차를 실행한 결과:
> - **키 미설정** — `WHYMATH_DIALOGUE_CONTENT_ENCRYPTION_KEY` User env 길이 0.
> - **암호화 마이그레이션 미적용** — `whymath-pg` alembic head=`f3a4b5c6d7e8`(2026-06-30)로, repo
>   head `a9b8c7d6e5f4`(2026-07-26)보다 뒤. 본문 암호화(`c3d4e5f0a1b2`·2026-07-05)·이미지 봉투
>   (`a2b3c4d5e6f1`·2026-07-26)가 모두 그 이후라, `dialogue_turn`에 `content_encrypted` 컬럼이
>   없고 평문 `content`만 존재.
> - **`dialogue_turn` 0행** — 저장된 대화 없음 = **평문 미성년 데이터 노출 0**(측정 대상 자체 부재).
>
> 결론: 이 머신은 실 프로덕션이 아니라 *암호화 도입 전 개발 DB*다. SEC-02(양성 증거=암호화 행>0)는
> **실 프로덕션(마이그레이션 적용 + 키 설정 + 실 트래픽) 성립 시점까지 pending 유지**(done 아님).
> 현 시점 조용한 평문 저장 위험은 없다(0행). done 조건은 여전히 이 절에 *암호화 수치*가 기록될 때다.

---

## 5. 관련

- 프리미티브·헬퍼: `src/backend/whymath_backend/api/_crypto.py`
- 컬럼 정의: `src/backend/whymath_backend/db/models/dialogue.py`
- 백필 CLI: `src/backend/whymath_backend/privacy/dialogue_content_backfill.py`
- 마이그레이션: `alembic/versions/20260726_0100_a2b3c4d5e6f1_dialogue_image_envelope.py`
- 회귀 동결: `tests/backend/api/test_dialogue_image_encryption.py`(fail-closed 변별력 포함) ·
  `tests/backend/api/test_dialogue_content_encryption_integration.py`(실 PG 왕복·백필 세 축)
