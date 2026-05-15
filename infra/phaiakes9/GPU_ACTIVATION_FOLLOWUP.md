# Phaiakes9 — GPU 활성화 후속 가이드

> **컨텍스트**: 2026-05-15 1차 셋업에서 *CPU 추론 baseline* 측정 완료 후, *Radeon 8060S(Strix Halo gfx1151) Vulkan 미인식* 진단. 다음 세션에서 GPU 활성화 시 점검할 *우선순위 체크리스트*.
>
> **출처**: 사용자(Kiki) 제공 RDNA 3.5 UMA·드라이버 정합성 분석 (2026-05-15).
>
> **관련 결정 로그**: `MEMORY.md` "2026-05-15: Phaiakes9 1차 셋업 완료 — CPU baseline 확보, GPU 후속 분리".

---

## 1. 현재 상태 (2026-05-15 16:13 KST)

| 항목 | 상태 |
|---|---|
| Ollama 0.24.0 + qwen2-math:7b (Q4_K_M, 4.4 GB) | ✅ 작동 (CPU 추론) |
| 헬스체크 3단계 (HTTP·모델·generate) | ✅ 통과 |
| CPU baseline (12.62 tok/s @ concurrent 1) | ✅ 확보 |
| Vulkan GPU 인식 | ❌ 실패 |

**GPU 미인식 증거**:
- Ollama 로그: `total_vram="0 B"`, `inference compute id=cpu library=cpu`
- `vulkaninfo --summary`: `deviceName = llvmpipe (LLVM 20.1.2, 256 bits)` *(GPU 0개, CPU 폴백만)*
- `/dev/dxg` 존재 (Windows GPU가 WSL에 노출됨), `/dev/dri` 없음 (Linux native GPU 노드 부재)
- Mesa 25.2.8 패키지에 *DZN(DirectX-to-Vulkan) ICD 미포함* — RADV가 DXG 인식 불가

---

## 2. 가능 원인 (사용자 분석)

**`total_vram=0`은 하드웨어 결함이 아니라 RDNA 3.5 기반 UMA 메모리 구조와 드라이버·펌웨어 간 정합성 문제**일 가능성이 매우 높음. 단순 폴백이 아닌 *명확한 체크리스트* 존재:

### 2.1 BIOS UMA Frame Buffer 설정 (최우선)

Strix Halo는 시스템 메모리를 공유하는 구조. BIOS 디폴트 'Auto' 설정 시 OS·라이브러리(ROCm·PyTorch·Vulkan)가 VRAM을 0으로 인식하는 경우가 흔함.

**조치**:
- BIOS 진입 → `Advanced` → `Graphics Configuration` → `UMA Frame Buffer Size`
- `Auto` → **`Fixed`**로 변경
- 권장 값:
  - **최소 16 GB** (기본 동작)
  - **48~64 GB** (시스템 RAM 128GB의 절반, LLM 구동 권장)

**효과**: 고정 할당 시 OS 커널이 *Dedicated VRAM*으로 명확히 인식 → `total_vram` 정상 출력 → Ollama·ROCm·Vulkan 모두 GPU 활용 가능.

### 2.2 Linux 커널·펌웨어·ROCm 버전 요구사항

Strix Halo (gfx1151)는 최신 아키텍처이므로 특정 버전 이상의 소프트웨어 스택 필수.

| 항목 | 최소 요구 버전 | 비고 |
|---|---|---|
| Linux Kernel | **6.18.4+** | AMD KFD 드라이버의 메모리 큐 제한 수정 포함 |
| Linux Firmware | **20260110+** | 2025년 말 일부 불안정 빌드(20251125) 회피 필수 |
| ROCm | **7.2.0+** | gfx1151 공식 지원 및 전용 최적화 가이드 |

**Tip**: Ubuntu 24.04 HWE 커널 사용 시 **`6.17.0-19.19+`** 빌드 확인.

### 2.3 WSL2 환경 — librocdxg 이슈

Native Windows에서 GPU 인식되는데 WSL2만 0 또는 시스템 RAM 용량으로 표시되는 경우 → *`librocdxg` 라이브러리가 BIOS UMA 설정을 못 읽는 버그*.

**조치**:
1. Windows측 **AMD Adrenalin 드라이버 26.x+** 설치
2. `.wslconfig` 메모리 한계 상향:
   ```ini
   [wsl2]
   memory=110GB
   processors=32
   ```
   파일 위치: `C:\Users\kiki\.wslconfig`
3. PowerShell에서 `wsl --shutdown` → WSL 재진입

---

## 3. 다음 세션 작업 흐름

### 옵션 A: BIOS·드라이버 조치 후 WSL Vulkan 재시도 (권장, 1-2시간)

```bash
# 사전 조치 (Windows / BIOS):
# - BIOS: UMA Frame Buffer = Fixed 48 GB
# - Windows: AMD Adrenalin 26.x+ 설치
# - %UserProfile%\.wslconfig 메모리 110 GB
# - PowerShell: wsl --shutdown

# WSL 재진입 후:
vulkaninfo --summary 2>&1 | tail -30
# 기대: deviceName = AMD Radeon Graphics (RADV GFX1151)
ls -la /dev/dri 2>&1
# 기대: render128 등 노드 생성됨

# Ollama Vulkan 활성화 (systemd override)
sudo mkdir -p /etc/systemd/system/ollama.service.d
sudo tee /etc/systemd/system/ollama.service.d/vulkan.conf > /dev/null <<'EOF'
[Service]
Environment="OLLAMA_VULKAN=1"
EOF
sudo systemctl daemon-reload
sudo systemctl restart ollama
sudo journalctl -u ollama -n 30 --no-pager
# 기대: inference compute id=vulkan, total_vram="48 GiB"

# 재벤치
WHYMATH_BENCH_MODEL=qwen2-math:7b WHYMATH_BENCH_CONCURRENCY=1,4 WHYMATH_BENCH_NUM_PREDICT=128 bash infra/phaiakes9/benchmark/run_bench.sh
# 기대: tok/s 5-12x 향상 (60-150 tok/s), p50 < 2000ms 게이트 통과
```

### 옵션 B: Ollama Windows native + WSL 클라이언트 (대안, 2-3시간)

Windows측에 Ollama를 직접 설치하면 DirectML/Vulkan으로 Strix Halo 자동 활용. WSL은 *클라이언트*만.

```bash
# Windows:
# https://ollama.com/download/windows 설치 → 자동 GPU 인식

# WSL 측에서 Windows IP 확인
ip route | grep default | awk '{print $3}'   # 예: 172.28.0.1

# WSL Ollama 정지
sudo systemctl stop ollama
sudo systemctl disable ollama

# 모든 명령에 Windows Ollama 사용
WHYMATH_OLLAMA_HOST=http://<windows-ip>:11434 bash infra/phaiakes9/healthcheck.sh
```

### 옵션 C: ROCm WSL 셋업 (고급, 3-4시간)

AMD 공식 ROCm 7.2.0+ WSL 패키지로 GPU compute 직접 제어. `HSA_OVERRIDE_GFX_VERSION` 우회 시도.

```bash
# 사전 진단
sudo dmesg | grep amdgpu
# 초기화 오류 코드 확인
```

---

## 4. 활성화 시 기대 성능

Strix Halo Radeon 8060S 잠재력 (사용자 분석):

| 지표 | 사양 |
|---|---|
| 연산 유닛 | **40 CU** (모바일 RTX 4070급) |
| 메모리 대역폭 | LPDDR5X-8000 기반 Unified Memory |
| 통합 메모리 | 128 GB (CPU·GPU 공유) |
| AI 추론 잠재력 | Qwen 3.5 72B 단일 칩 로컬 구동 가능 |

**WhyMath SLA 영향 예측**:
- 7B 모델: 60-150 tok/s 가능 (CPU 12.6 tok/s의 *5-12x*)
- 32B 모델: 20-50 tok/s 가능 (현재 미시도)
- 72B 모델: 단일 칩 로컬 구동 가능
- **p50 < 2초 게이트 통과 가능성 매우 큼**

---

## 5. 진단 명령 (1차 셋업 결과 재현용)

```bash
# Vulkan 상태
vulkaninfo --summary 2>&1 | tail -30
ls -la /dev/dxg /dev/dri 2>&1

# Ollama GPU 인식 로그
sudo journalctl -u ollama -n 30 | grep -E "inference compute|total_vram|GPU|Vulkan"

# AMD GPU 커널 메시지 (gfx1151 초기화 오류 확인)
sudo dmesg | grep -i amdgpu

# Vulkan ICD 등록 상태
ls /usr/share/vulkan/icd.d/ /etc/vulkan/icd.d/

# Mesa·Vulkan 버전
dpkg -l mesa-vulkan-drivers vulkan-tools

# 벤치 CPU baseline (비교 기준)
WHYMATH_BENCH_MODEL=qwen2-math:7b WHYMATH_BENCH_CONCURRENCY=1,4 WHYMATH_BENCH_NUM_PREDICT=128 bash infra/phaiakes9/benchmark/run_bench.sh
```

---

## 6. 참고 자료

- 사용자(Kiki) 제공 Strix Halo 활성화 가이드 (2026-05-15)
- AMD ROCm gfx1151 공식 지원 문서 (ROCm 7.2.0+ 릴리스 노트)
- Mesa RADV DZN 통합 진행 상황: https://gitlab.freedesktop.org/mesa/mesa
- Ollama WSL GPU 지원 관련 이슈: https://github.com/ollama/ollama/issues

---

**작성**: 2026-05-15, Phaiakes9 1차 셋업 마무리 시점  
**작성자**: Claude L5 backend-engineer agent (Kiki 가이드 정리)  
**다음 세션 출발점**: 본 문서 §3 옵션 A·B·C 중 선택
