# KICE 연구보고서 PDF 히스토리 제거 런북 (LIC-07)

> **판정 기준: main `76f415db` (2026-09-06 실측)** — 이 문서의 모든 "있다/없다" 판정은 이 커밋
> 기준이다. 판정에는 시점이 붙어야 하고, 해시 없는 판정은 며칠 뒤 조용히 거짓이 된다
> (CLAUDE.md 2026-09-06 "미머지 존재를 충족으로 단정 금지").

이 작업은 **Kiki가 직접 실행한다**. 세션이 실행하지 않은 이유는 두 가지다 — ① 히스토리 재작성은
되돌리기 어렵고 ② 이 세션에서 `git filter-repo` 실행이 **권한 분류기에 의해 거부**됐다. 거부는
장애물이 아니라 판정이므로 우회하지 않고 소유자에게 실행 명령으로 넘긴다(CLAUDE.md
"거부(deny)의 우회 금지" 처리 순서 ②).

---

## 1. 과제 명칭

git 히스토리에 잔존하는 **KICE 평가기준 개발 연구 보고서 원본 PDF 2건** 제거 — 브랜치 2개 재작성.

## 2. 목적

저작권 위험 자료를 저장소 배포 경로에서 없앤다.

두 PDF는 **고시가 아니라 KICE가 발간한 연구보고서**다. PDF 판권장을 직접 추출해 확인했다:

> **실측 결과 — `(고등학교)…평가기준 개발 연구(수학과).pdf` p2**
> `연구보고 CRC 2017-5-6 | 발행일 2017년 11월 28일 | 발행처 한국교육과정평가원 |`
> `I S B N 979-11-5788-529-9 94370 | ※ 본 자료 내용의 무단 복제를 금함`
>
> **실측 결과 — `2015 개정 … 초중학교 수학과 평가기준 개발 연구.pdf` p2**
> `연구보고 CRC 2016-2-6 | 발행일 2016년 11월 30일 | 발행처 한국교육과정평가원 |`
> `I S B N 979-11-5788-347-9 94370 | ※ 본 자료 내용의 무단 복제를 금함`

`docs/data/licensing_safety.md`의 **'NCIC 구분'**이 이 부류를 이미 분류해 두었다 — 성취기준
*코드·고시 본문*은 저작권법 §7 보호대상 아님(무제한)이지만, NCIC **해설서·연구보고서**는
공공누리 2유형(**영리 차단·C등급**)이다. WhyMath는 상업 서비스이므로 후자는 잔존시키지 않는다.

**제거 대상이 아닌 것 (혼동 금지)**:
- `data/ncic/raw/curriculum_math_2022.pdf` — p1이 `교육부 고시 제2022-33호 [별책 8] 수학과 교육과정`.
  **고시**라 저작권법 §7 제1호(고시·공고·훈령)상 보호받지 못하는 저작물이다. 그대로 둔다.
- `한국_중고_수학앱_사업계획서.pdf` / `.docx`, `WhyMath_harness.zip`, `files.zip` — 자체 저작물.
- 작업 트리의 코퍼스 전량 — 2026-09-06 전수 실사 결과 저작권 저촉 **0건**.

## 3. 구체적 절차

### 3.1 사전 실측 — 무엇이 어디에 있는가

| 항목 | 값 |
|---|---|
| blob ① | `35cb705abfef4f7fbee7b2e6b77d68a6c25f272d` · 4,824,216 B · 고등 CRC 2017-5-6 |
| blob ② | `7e1d471e69b2d4135310cd53c4eca98d1b32b5a1` · 5,906,090 B · 초중 CRC 2016-2-6 |
| 도입 커밋 | `388f7921` "kice pdf 반입" (2026-08-08) |
| 제거 커밋 | `98a34695` "data(CUR-03): KICE … 구조 메타데이터 반입" (2026-08-08) |

**도달 가능한 ref (unshallow 후 전수 실측)**:

| ref | blob 보유 | 일반 `git clone`이 가져오는가 |
|---|---|---|
| `refs/heads/main` | **0건** | — |
| `refs/heads/claude/human-bottleneck-tasks-6dszy0` | 2건 | **예** |
| `refs/heads/merge/human-bottleneck-6dszy0` | 2건 | **예** |
| `refs/pull/739/head` (닫힌 PR #739) | 2건 | 아니오(명시 fetch 필요) |

> **핵심 — main은 깨끗하다.** 처음에는 shallow 클론이라 판정이 불가능했고(SessionStart 훅도
> "ahead 수치·포팅 근거를 신뢰할 수 없다"고 경고했다), `git fetch --unshallow` 후에야 확정됐다:
> `git merge-base --is-ancestor 388f7921 origin/main` → **false**. 따라서 **main 히스토리 재작성도,
> 전 협업자 재clone도, 열린 PR 전건 재기반도 필요 없다.** 재작성 대상은 정체된 브랜치 2개뿐이다.

### 3.2 브랜치를 지우지 않고 **재작성**하는 이유

`claude/human-bottleneck-tasks-6dszy0`은 main에 없는 커밋 **21건**을 담고 있고, 그중
**3개 태스크의 구현이 main에 착지하지 않았다**(내용 기준 실측):

| 태스크 | main 상태 | 산출물 실측 |
|---|---|---|
| CUR-03 | done | 코퍼스 `achievement_criteria_v1` main에 있음 ✔ |
| MISC-04 | done | `db/models/misconception_relation.py` main에 있음 ✔ |
| S3-32 · REC-02 | done | 회수 완료 ✔ |
| **MISC-01** | **todo** | `coach.py`의 `visualize_misconception` 배선 매치 **0** ✘ |
| **MISC-03** | **todo** | `coach.py`의 유사 미응답 문항 서빙 매치 **0** ✘ |
| **PB-02** | **todo** | `ci.yml`의 커버리지 재생성-diff 매치 **0** ✘ |

브랜치를 **삭제**하면 이 3건이 소실된다 — 이 저장소가 이미 4번 겪은 "미병합 고립"의 5회차가 된다.
**재작성**은 PDF blob만 들어내고 21커밋을 전부 보존한다.

**비용(정직한 고지)**: 재작성은 21커밋의 SHA를 전부 바꾼다. 백로그 notes가 인용하는 옛 SHA
(예: REC-02 notes의 `d554ddad`)는 더 이상 해석되지 않는다. 작업 소실은 없고 부기 참조만 끊긴다.

### 3.3 실행 (예상 소요 5~10분 · 네트워크 상태에 따라 변동)

각 단계마다 **그 단계의 산출물 자체**를 확인하는 자가검증이 붙어 있다. 간접 신호(명령이 조용히
끝났다 등)를 성공 근거로 삼지 않는다.

**단계 1 — 도구 설치 + 미러 클론 (새 작업 폴더, 저장소 클론과 분리)**

```powershell
# 실행 시스템: Windows PowerShell (Phaiakes9 = 이 PC 자체 · 별도 접속 불요)
cd C:\Users\kiki\Desktop\__AI
python -m pip install git-filter-repo
Remove-Item -Recurse -Force .\wm-purge -ErrorAction SilentlyContinue
git clone --mirror https://github.com/doldori7/WhyMath.git wm-purge
cd .\wm-purge
git filter-repo --version
```

자가검증: `git filter-repo --version`이 버전 문자열을 출력해야 한다. `명령을 찾을 수 없습니다`가
나오면 `python -m pip install --user git-filter-repo` 후 `python -m git_filter_repo --version`으로
확인하고, 이후 단계의 `git filter-repo`를 `python -m git_filter_repo`로 바꿔 쓴다.

**단계 2 — 재작성 전 상태 실측 (이 숫자가 뒤 단계의 대조군이다)**

커밋 수를 **셸 변수에 담는다**. 뒤 단계가 이 값을 인자로 쓰므로 자리표시자를 두지 않는다
(CLAUDE.md 2026-08-31 "앞 단계 출력이 뒤 단계 인자가 되는 블록은 변수로 잇는다").

```powershell
cd C:\Users\kiki\Desktop\__AI\wm-purge
$Blobs = "^(35cb705abfef4f7fbee7b2e6b77d68a6c25f272d|7e1d471e69b2d4135310cd53c4eca98d1b32b5a1) "
"35cb705abfef4f7fbee7b2e6b77d68a6c25f272d`n7e1d471e69b2d4135310cd53c4eca98d1b32b5a1" | Set-Content -Encoding ascii ..\strip_blobs.txt
$A = "refs/heads/claude/human-bottleneck-tasks-6dszy0"
$M = "refs/heads/merge/human-bottleneck-6dszy0"
$PreA = [int](git rev-list --count "refs/heads/main..$A")
$PreM = [int](git rev-list --count "refs/heads/main..$M")
foreach ($r in @("refs/heads/main", $A, $M)) {
  $n = (git rev-list --objects $r | Select-String -Pattern $Blobs).Count
  Write-Host "$r -> blob $n 건"
}
Write-Host "재작성 전 커밋 수: A=$PreA  M=$PreM"
```

성공 기준: **main 0건 · 나머지 두 브랜치 각 2건**, `PreA`/`PreM`은 각각 **21**(2026-09-06 실측).
main이 0이 아니면 **여기서 멈추고 세션에 알린다** — 3.1 판정이 뒤집힌 것이므로 절차를 다시 짠다.

> ⚠ `$PreA`·`$PreM`은 이 창의 변수다. 창을 닫거나 새 창을 열면 단계 4의 대조가 성립하지 않는다.
> 단계 2~4는 **같은 창에서 연속으로** 실행한다.

**단계 3 — 재작성 (두 브랜치만 · blob ID 지정)**

경로가 아니라 **blob ID**로 지정한다. 파일명이 한글이라 경로 지정은 인코딩에서 어긋날 수 있는데,
blob ID는 그 위험이 없다.

```powershell
cd C:\Users\kiki\Desktop\__AI\wm-purge
git filter-repo --force --partial --refs refs/heads/claude/human-bottleneck-tasks-6dszy0 refs/heads/merge/human-bottleneck-6dszy0 --strip-blobs-with-ids ..\strip_blobs.txt
```

**단계 4 — 재작성 후 자가검증 (변별력 있는 검사)**

```powershell
cd C:\Users\kiki\Desktop\__AI\wm-purge
$PostA = [int](git rev-list --count "refs/heads/main..$A")
$PostM = [int](git rev-list --count "refs/heads/main..$M")
$BlobA = (git rev-list --objects $A | Select-String -Pattern $Blobs).Count
$BlobM = (git rev-list --objects $M | Select-String -Pattern $Blobs).Count
$Coach = (git show "${A}:src/backend/whymath_backend/api/coach.py" | Select-String -Pattern "visualize_misconception").Count
$Ci    = (git show "${A}:.github/workflows/ci.yml" | Select-String -Pattern "재생성").Count
Write-Host "blob:    A=$BlobA  M=$BlobM        (둘 다 0이어야 함)"
Write-Host "커밋수:  A=$PostA/$PreA  M=$PostM/$PreM  (각각 이전값 또는 이전값-1)"
Write-Host "내용마커: coach.py=$Coach (6)  ci.yml=$Ci (3)"
```

성공 기준 — **세 축이 모두** 성립해야 한다. 하나만 보면 위장이 된다(blob 0건만 확인하면
"브랜치를 통째로 비워도 통과"한다).

| 축 | 기대값 | 왜 이 값인가 |
|---|---|---|
| blob | `A=0 M=0` | 제거됐다 |
| 커밋 수 | `$PostA`가 `$PreA` 또는 `$PreA - 1` (M도 동일) | `388f7921`은 **PDF 2개만** 담은 커밋이라 blob을 들어내면 빈 커밋이 되고, filter-repo가 기본값(`--prune-empty=auto`)으로 정리한다. 그래서 **1 감소가 정상**이다. `98a34695`는 6파일을 바꾸므로 살아남는다. 2 이상 줄거나 0~1로 떨어졌으면 커밋까지 날아간 것이니 **push 금지** |
| 내용 마커 | `coach.py=6`, `ci.yml=3` | main에 착지하지 않은 MISC-01·PB-02의 구현이 그대로 남아 있는지 직접 본다. 커밋 수만으로는 "커밋은 있는데 내용이 비었다"를 잡지 못한다 |

**단계 5 — force-push (되돌리기 어려운 지점 · 여기까지 자가검증 통과 후에만)**

```powershell
cd C:\Users\kiki\Desktop\__AI\wm-purge
git push --force origin refs/heads/claude/human-bottleneck-tasks-6dszy0:refs/heads/claude/human-bottleneck-tasks-6dszy0
git push --force origin refs/heads/merge/human-bottleneck-6dszy0:refs/heads/merge/human-bottleneck-6dszy0
```

**단계 6 — 최종 확인 (완전히 새 clone에서 · 캐시 오염 배제)**

```powershell
cd C:\Users\kiki\Desktop\__AI
Remove-Item -Recurse -Force .\wm-verify -ErrorAction SilentlyContinue
git clone https://github.com/doldori7/WhyMath.git wm-verify
cd .\wm-verify
$n = (git rev-list --objects --all | Select-String -Pattern "^(35cb705abfef4f7fbee7b2e6b77d68a6c25f272d|7e1d471e69b2d4135310cd53c4eca98d1b32b5a1) ").Count
Write-Host "새 clone의 KICE blob: $n 건 (0이어야 성공)"
```

## 4. 성공 기준

- 단계 4: 두 브랜치 blob **0건** + 커밋 수 `$Pre` 또는 `$Pre - 1` + 내용 마커 `coach.py=6`·`ci.yml=3`
- 단계 6: 새 clone에서 blob **0건**
- 실패 시 대처: 단계 5 전이면 `wm-purge` 폴더를 지우고 단계 1부터 다시 한다(원격 무변경이라
  피해 0). 단계 5 후 문제가 발견되면 GitHub의 브랜치 히스토리에서 이전 헤드로 복구 가능하나,
  그 전에 세션에 상황을 알린다.

## 5. 실행 환경

- **머신**: Phaiakes9 = Kiki의 작업 PC 그 자체. 평소 쓰는 Windows PowerShell이 곧 Phaiakes9이며
  SSH·WSL 진입은 불요하다.
- **작업 디렉터리**: `C:\Users\kiki\Desktop\__AI` (저장소 클론 `…\__AI\WhyMath`와 **분리된**
  임시 폴더 `wm-purge`·`wm-verify`를 쓴다 — 평소 작업 클론을 건드리지 않는다)
- **선행 조건**: GitHub push 권한, 네트워크. Docker·서버 기동 불요.

## 6. 창 구분

**PowerShell 창 하나**에서 단계 1~6을 순서대로 진행한다. 장기 점유 프로세스(서버 등)가 없으므로
창 분리가 필요 없다. 단계 사이에 자가검증 출력을 읽고 판단하는 지점이 있으니 **한 번에 전부
붙여넣지 말고 단계 단위로** 실행한다.

---

## 7. 남는 것 — `refs/pull/739/head` (GitHub 지원 요청 필요)

닫힌 PR **#739**(`merge: claude/human-bottleneck-tasks-6dszy0 (MISC-01, MISC-03, PB-02, REC-02,
S3-32)`)의 서버 측 ref `refs/pull/739/head`가 옛 커밋을 계속 보유한다. 이 ref는 **저장소 소유자도
git으로 지울 수 없다** — force-push로도 사라지지 않는다.

- **일반 `git clone`은 `refs/pull/*`을 가져오지 않는다.** 따라서 위 단계 1~6을 마치면 통상적인
  배포 경로에서는 PDF가 사라진다 — 노출은 "모든 clone"에서 "PR ref를 명시적으로 fetch하는
  사람"으로 줄어든다.
- 완전 제거를 원하면 **GitHub Support에 요청**한다(저장소·PR 번호·blob SHA 2건을 적어
  "remove cached views / stale PR refs" 요청). 이건 웹 폼 작업이라 이 런북 범위 밖이다.
- 그 요청 전까지 남는 잔여 위험은 **알면서 남기는 한계**로 `LIC-07`에 기록돼 있다.

## 8. 재유입 방지 (`LIC-07` acceptance ④ — 별도 작업)

같은 일이 다시 일어나지 않게 하는 가드는 이 런북이 아니라 `LIC-07` ④가 소유한다. 저작권 위험
원본(대용량 PDF·hwp 등)의 커밋을 CI 또는 pre-commit에서 차단하고, **위반 픽스처를 실제로 주입해
red를 실증**한 뒤에만 "보호 있음"으로 친다(CLAUDE.md 2026-09-01 "보호 장치를 실패 주입 없이
'보호 있음'으로 선언 금지").
