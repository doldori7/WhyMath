# Windows 개발 환경 UTF-8 통일 가이드

> **대상**: Windows 11 + VS Code + PowerShell + Python + Git + Flutter/Dart 기반 WhyMath 개발 환경
> **목표**: CP949 인코딩 문제를 원천 차단하고, 터미널·파일·프로세스·Git 전체를 UTF-8로 통일
> **관련**: `CLAUDE.md` 빌드 명령, `scripts/harness/backlog.py`, `tests/backend/*`

---

## 1. 핵심 원칙

```text
CP949 파일을 발견하면
       ↓
경계에서 한 번만 CP949 decode
       ↓
프로젝트 내부에서는 Unicode
       ↓
파일 저장은 UTF-8
```

**애플리케이션 내부에서 CP949를 지원하려고 하지 말 것.** CP949는 외부 호환성 경계에서만 처리한다.

---

## 2. PowerShell/터미널 UTF-8 설정

PowerShell 프로필에 아래 3줄을 추가한다.

```powershell
[Console]::InputEncoding  = [System.Text.UTF8Encoding]::new()
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new()
$OutputEncoding = [System.Text.UTF8Encoding]::new()
```

프로필 편집:

```powershell
notepad $PROFILE
```

Git Bash 터미널은 기본적으로 UTF-8이나, Windows 콘솔(`cmd.exe`)은 `chcp 65001`로 전환해야 한다.

```powershell
chcp 65001
```

> **주의**: Git Bash에서는 `chcp` 명령이 없다. PowerShell/cmd에서만 사용한다.

---

## 3. Python UTF-8 모드 강제

### 3.1 환경 변수

```powershell
setx PYTHONUTF8 1
setx PYTHONIOENCODING utf-8
```

현재 세션에 즉시 적용:

```powershell
$env:PYTHONUTF8="1"
$env:PYTHONIOENCODING="utf-8"
```

### 3.2 파일 입출력

```python
with open("data.json", "r", encoding="utf-8") as f:
    data = f.read()

with open("output.txt", "w", encoding="utf-8", newline="\n") as f:
    f.write(text)
```

### 3.3 JSON/JSONL

```python
import json

with open(path, "r", encoding="utf-8") as f:
    for line in f:
        obj = json.loads(line)

with open(path, "w", encoding="utf-8") as f:
    f.write(json.dumps(obj, ensure_ascii=False) + "\n")
```

`ensure_ascii=False`를 사용하면 한국어가 이스케이프되지 않고 사람이 읽기 쉽게 저장된다.

### 3.4 subprocess

Windows에서 CP949 문제가 반복되는 주요 지점이다.

**나쁜 예:**

```python
result = subprocess.run(command, capture_output=True, text=True)
```

**권장:**

```python
result = subprocess.run(
    command,
    capture_output=True,
    text=True,
    encoding="utf-8",
    errors="replace",
)
```

호출하는 프로그램 자체가 CP949를 출력한다면 UTF-8을 강제하면 안 된다. 이 경우 CP949로 받아서 내부에서 Unicode로 처리한다.

```python
result = subprocess.run(
    command,
    capture_output=True,
    text=True,
    encoding="cp949",
    errors="replace",
)
```

구조:

```text
외부 CP949 프로그램
        ↓
CP949 decode
        ↓
Python Unicode
        ↓
UTF-8 파일/JSON/log
```

---

## 4. VS Code 기본 인코딩 고정

`.vscode/settings.json`:

```json
{
  "files.encoding": "utf8",
  "files.autoGuessEncoding": false,
  "files.eol": "\n"
}
```

상태바에서 파일 인코딩이 `UTF-8`인지 확인한다.

기존 CP949 파일은 VS Code에서 다음 순서로 변환한다.

1. `Reopen with Encoding` → `Korean (EUC-KR)`
2. `Save with Encoding` → `UTF-8`

---

## 5. Git UTF-8 기준

```powershell
git config --global core.quotepath false
git config --global i18n.commitEncoding utf-8
git config --global i18n.logOutputEncoding utf-8
```

확인:

```powershell
git config --global --list
```

`core.quotepath false`는 한국어 파일명이 `\354\225...` 형태로 보이는 문제를 방지한다.

---

## 6. `.editorconfig` 추가

프로젝트 루트 `.editorconfig`:

```ini
root = true

[*]
charset = utf-8
end_of_line = lf
insert_final_newline = true
```

VS Code뿐 아니라 여러 IDE에서 UTF-8 규칙을 공유할 수 있다.

---

## 7. Flutter/Dart UTF-8 유지

Dart 소스 자체는 UTF-8이 기본이다. 문제는 Dart가 호출하는 외부 프로세스 또는 파일에서 발생한다.

```dart
import 'dart:convert';
import 'dart:io';

final file = File('data.json');
final text = await file.readAsString(encoding: utf8);
```

프로세스 결과:

```dart
final result = await Process.run(
  'python',
  ['script.py'],
  stdoutEncoding: utf8,
  stderrEncoding: utf8,
);
```

특히 **Flutter → Python harness** 연동 지점에서 `stdoutEncoding`/`stderrEncoding`을 명시한다.

---

## 8. 파일별 인코딩 표준

| 확장자 | 인코딩 | 비고 |
|---|---|---|
| `.py` | UTF-8 | 항상 `encoding="utf-8"` 명시 |
| `.dart` | UTF-8 | 기본값이 UTF-8이나 외부 프로세스는 명시 |
| `.json` | UTF-8 | `ensure_ascii=False` 권장 |
| `.jsonl` | UTF-8 | 라인 단위 UTF-8 |
| `.md` | UTF-8 | |
| `.yaml` | UTF-8 | |
| `.toml` | UTF-8 | |
| `.log` | UTF-8 | |
| `.csv` | UTF-8 또는 UTF-8-SIG | Excel과 주고받을 때만 BOM 사용 |

CSV 예시(Excel 호환):

```python
with open("result.csv", "w", encoding="utf-8-sig", newline="") as f:
    ...
```

---

## 9. WhyMath 하네스 특이 사항

`scripts/harness/backlog.py`는 한국어 help와 상태 메시지를 출력한다. Windows 기본 콘솔이 CP949이면 `UnicodeEncodeError`가 발생할 수 있다.

**해결**: 실행 전 `PYTHONIOENCODING=utf-8`을 설정한다.

```powershell
$env:PYTHONIOENCODING="utf-8"
python scripts/harness/backlog.py status
```

PowerShell 프로필에 `PYTHONIOENCODING`을 영구 설정하면 매번 입력하지 않아도 된다.

---

## 10. 요약 체크리스트

- [ ] PowerShell 프로필에 Input/Output Encoding UTF-8 설정
- [ ] `PYTHONUTF8=1`, `PYTHONIOENCODING=utf-8` 환경 변수 설정
- [ ] VS Code `settings.json`에 `files.encoding: utf8`, `files.eol: "\n"` 설정
- [ ] `.editorconfig`에 `charset = utf-8`, `end_of_line = lf` 설정
- [ ] Git `core.quotepath false`, `i18n.commitEncoding utf-8` 설정
- [ ] Python 파일 입출력에 `encoding="utf-8"` 명시
- [ ] `subprocess`에 `encoding="utf-8"` 또는 `encoding="cp949"`(외부 프로그램이 CP949일 때) 명시
- [ ] JSON 저장 시 `ensure_ascii=False`
- [ ] CSV는 Excel용으로만 `utf-8-sig` 사용
- [ ] Flutter 외부 프로세스 호출 시 `stdoutEncoding: utf8`, `stderrEncoding: utf8` 명시
