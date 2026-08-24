#!/usr/bin/env python3
"""OPS-52 ROCm 7.2.1 standalone 적용·시험 (Phaiakes9 전용).

사전 조건:
    install_rocm72_standalone.ps1 -Phase DownloadInstall 또는 동등한 curl+pip 설치가 끝난 상태.

동작:
    1. Ollama 프로세스 종료
    2. standalone HIP_PATH 환경변수 설정(사용자 + 현재 프로세스)
    3. amdhip64_7.dll -> amdhip64.dll alias 복사
    4. Ollama lib 디렉터리에도 핵심 DLL 복사(검색 우선순위 우회)
    5. Ollama tray app 재기동
    6. qwen3:30b-a3b로 간단 생성 시험
    7. Ollama 로그에서 ROCm/HIP 키워드 출력
"""

from __future__ import annotations

import json
import os
import pathlib
import shutil
import subprocess
import sys
import time
import urllib.request
from typing import Any


def log(msg: str) -> None:
    line = f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}"
    print(line, flush=True)


def run(
    cmd: list[str], *, check: bool = True, timeout: float | None = 30
) -> subprocess.CompletedProcess[Any]:
    log("RUN: " + " ".join(cmd))
    return subprocess.run(cmd, check=check, timeout=timeout, capture_output=True, text=True)


def kill_ollama() -> None:
    names = ["ollama.exe", "ollama app.exe", "llama-server.exe"]
    for name in names:
        try:
            subprocess.run(
                ["taskkill", "/F", "/IM", name],
                check=False,
                capture_output=True,
                text=True,
                timeout=30,
            )
        except Exception as exc:  # noqa: BLE001
            log(f"taskkill {name} exception: {type(exc).__name__}: {exc}")
    time.sleep(5)


def set_user_env(name: str, value: str) -> None:
    try:
        run(["setx", name, value], timeout=10)
    except subprocess.CalledProcessError as exc:
        log(f"[WARN] setx {name} failed: {exc.stderr}")


def main() -> int:
    repo_root = pathlib.Path(__file__).resolve().parents[2]
    install_dir = repo_root / "work" / "rocm-7.2.1-standalone"
    core_bin = install_dir / "_rocm_sdk_core" / "bin"
    custom_bin = install_dir / "_rocm_sdk_libraries_custom" / "bin"
    ollama_dir = pathlib.Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Ollama"
    ollama_lib = ollama_dir / "lib" / "ollama"
    ollama_app = ollama_dir / "ollama app.exe"

    log("OPS-52 ROCm 7.2.1 standalone activation")
    log(f"install_dir = {install_dir}")
    log(f"ollama_dir  = {ollama_dir}")

    # ── 1. Ollama 종료 ────────────────────────────────────────────────────────
    log("terminating Ollama processes")
    kill_ollama()

    # ── 2. standalone HIP 경로 확인 및 alias ──────────────────────────────────
    hip_src = core_bin / "amdhip64_7.dll"
    if not hip_src.exists():
        log(f"[FAIL] {hip_src} not found")
        return 1
    hip_alias = core_bin / "amdhip64.dll"
    shutil.copy2(hip_src, hip_alias)
    log(f"copied {hip_src.name} -> {hip_alias.name}")

    hip_path = str(core_bin)

    # ── 3. Ollama lib에도 복사(검색 우선순위 우회) ───────────────────────────
    backup_dir = install_dir / "ollama-lib-backup"
    if ollama_lib.exists():
        hip_dlls = list(ollama_lib.rglob("hip*.dll"))
        log(f"built-in hip*.dll count: {len(hip_dlls)}")
        if not backup_dir.exists():
            backup_dir.mkdir(parents=True, exist_ok=True)
            for dll in hip_dlls:
                rel = dll.relative_to(ollama_lib)
                dest = backup_dir / rel
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(dll, dest)
            log(f"backed up Ollama lib: {backup_dir}")
        shutil.copy2(hip_alias, ollama_lib / "amdhip64.dll")
        shutil.copy2(custom_bin / "hipblas.dll", ollama_lib / "hipblas.dll")
        log("copied standalone amdhip64.dll / hipblas.dll into Ollama lib")
    else:
        log(f"[WARN] Ollama lib not found: {ollama_lib}")

    # ── 4. 사용자 환경변수 설정 ────────────────────────────────────────────────
    log("setting HIP_PATH user env")
    set_user_env("HIP_PATH", hip_path)

    # ── 5. Ollama 재기동(현재 프로세스 env 상속) ─────────────────────────────
    if not ollama_app.exists():
        log(f"[FAIL] Ollama tray app not found: {ollama_app}")
        return 1

    env = os.environ.copy()
    env["HIP_PATH"] = hip_path
    env["PATH"] = f"{hip_path};{custom_bin};" + env.get("PATH", "")
    log("starting Ollama tray app")
    subprocess.Popen([str(ollama_app)], env=env, close_fds=True)

    base = "http://127.0.0.1:11434"
    deadline = time.time() + 90
    version: str | None = None
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(base + "/api/version", timeout=5) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                version = data.get("version")
                log(f"server responded — version {version}")
                break
        except Exception:  # noqa: BLE001
            time.sleep(3)
    if version is None:
        log("[FAIL] Ollama server did not respond within 90s")
        return 1

    # ── 6. Ollama 로그에서 ROCm/HIP 키워드 추출 ──────────────────────────────
    log("inspecting Ollama logs for ROCm/HIP keywords")
    log_dir = pathlib.Path(os.environ.get("LOCALAPPDATA", "")) / "Ollama" / "logs"
    if log_dir.exists():
        log_files = sorted(
            log_dir.glob("server*.log"), key=lambda p: p.stat().st_mtime, reverse=True
        )[:3]
        keywords = ["ROCm", "HIP", "hipblas", "amdhip", "gfx", "GPU"]
        for lf in log_files:
            lines = lf.read_text(encoding="utf-8", errors="ignore").splitlines()
            matched = [ln for ln in lines if any(k in ln for k in keywords)]
            for ln in matched[-30:]:
                log(f"  {ln}")
    else:
        log(f"[WARN] Ollama log dir not found: {log_dir}")

    # ── 7. qwen3:30b-a3b 생성 시험 ───────────────────────────────────────────
    model = "qwen3:30b-a3b"
    try:
        with urllib.request.urlopen(base + "/api/tags", timeout=10) as resp:
            tags = json.loads(resp.read().decode("utf-8"))
        installed = {m.get("name") for m in tags.get("models", [])}
    except Exception as exc:  # noqa: BLE001
        log(f"[FAIL] /api/tags failed: {exc}")
        return 1

    if model not in installed:
        log(f"[SKIP] model not installed: {model}")
        return 0

    prompt = "Solve step by step: 2x + 5 = 13, find x. Answer only the value."
    body = json.dumps(
        {
            "model": model,
            "prompt": prompt,
            "stream": False,
            "options": {"num_predict": 64, "temperature": 0},
        }
    ).encode("utf-8")
    req = urllib.request.Request(
        base + "/api/generate",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    start = time.time()
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        elapsed = time.time() - start
        eval_count = data.get("eval_count", 0)
        tps = round(eval_count / elapsed, 2) if elapsed > 0 else 0
        log(f"generation ok: eval_count={eval_count}, elapsed={elapsed:.2f}s, t/s={tps}")
    except Exception as exc:  # noqa: BLE001
        log(f"[FAIL] generation call failed: {exc}")
        return 1

    log("[OK] ROCm 7.2 standalone activation complete")
    return 0


if __name__ == "__main__":
    sys.exit(main())
