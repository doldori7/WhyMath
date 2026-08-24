#!/usr/bin/env python3
"""OPS-52 복원 — Ollama lib를 ROCm 7.2 standalone 시도 전 내장 DLL 상태로 되돌린다."""

from __future__ import annotations

import json
import os
import pathlib
import shutil
import subprocess
import sys
import time
import urllib.request
import winreg


def log(msg: str) -> None:
    line = f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}"
    print(line, flush=True)


def kill_ollama() -> None:
    names = ["ollama.exe", "ollama app.exe", "llama-server.exe"]
    for name in names:
        subprocess.run(
            ["taskkill", "/F", "/IM", name],
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=30,
        )
    time.sleep(5)


def main() -> int:
    repo_root = pathlib.Path(__file__).resolve().parents[2]
    install_dir = repo_root / "work" / "rocm-7.2.1-standalone"
    backup_dir = install_dir / "ollama-lib-backup"
    ollama_dir = pathlib.Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Ollama"
    ollama_lib = ollama_dir / "lib" / "ollama"
    ollama_app = ollama_dir / "ollama app.exe"

    log("OPS-52 restore Ollama built-in ROCm libs")
    log(f"backup_dir = {backup_dir}")
    log(f"ollama_lib = {ollama_lib}")

    rocm_v7_1 = ollama_lib / "rocm_v7_1"
    if not rocm_v7_1.exists():
        log("[FAIL] built-in rocm_v7_1 dir not found — cannot restore")
        return 1

    log("terminating Ollama processes")
    kill_ollama()

    # 내장 ROCm 7.1 DLL로 복원: amdhip64_7.dll -> amdhip64.dll, libhipblas.dll -> hipblas.dll
    log("restoring built-in ROCm 7.1 DLLs")
    shutil.copy2(rocm_v7_1 / "amdhip64_7.dll", ollama_lib / "amdhip64.dll")
    log("  restored amdhip64.dll from rocm_v7_1/amdhip64_7.dll")
    if (rocm_v7_1 / "libhipblas.dll").exists():
        shutil.copy2(rocm_v7_1 / "libhipblas.dll", ollama_lib / "hipblas.dll")
        log("  restored hipblas.dll from rocm_v7_1/libhipblas.dll")

    # backup_dir이 비어있지 않다면 추가 복원
    if backup_dir.exists():
        for src in backup_dir.rglob("*"):
            if src.is_file():
                rel = src.relative_to(backup_dir)
                dst = ollama_lib / rel
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dst)
                log(f"  restored {rel} from backup")

    # standalone 시도에서 setx로 남긴 HIP_PATH 사용자 환경변수 삭제
    log("removing standalone HIP_PATH user env")
    try:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, "Environment", 0, winreg.KEY_SET_VALUE
        ) as key:
            try:
                winreg.DeleteValue(key, "HIP_PATH")
                log("  deleted HIP_PATH from HKCU\\Environment")
            except FileNotFoundError:
                log("  HIP_PATH not present in HKCU\\Environment")
    except Exception as exc:  # noqa: BLE001
        log(f"[WARN] failed to delete HIP_PATH user env: {exc}")

    log("starting Ollama tray app")
    env = os.environ.copy()
    env.pop("HIP_PATH", None)
    subprocess.Popen([str(ollama_app)], env=env, close_fds=True)

    base = "http://127.0.0.1:11434"
    deadline = time.time() + 90
    version = None
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

    model = "qwen3:30b-a3b"
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

    log("[OK] Ollama built-in ROCm restore complete")
    return 0


if __name__ == "__main__":
    sys.exit(main())
