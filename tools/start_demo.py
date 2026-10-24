#!/usr/bin/env python3
"""Start CareRoute and its local Ollama runtime, without cloud credentials."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
import webbrowser

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def request_json(url):
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with opener.open(url, timeout=2) as response:
        return json.load(response)


def find_ollama():
    candidates = [os.environ.get("OLLAMA_EXE"), ROOT / "var/local-ai/ollama/ollama.exe",
                  ROOT / "var/local-ai/ollama/ollama"]
    # Prefer the paired portable runtime/cache before a separate system install.
    for parent in (ROOT, ROOT.parent, ROOT.parent.parent):
        candidates.extend([parent / "work/ollama/ollama.exe", parent / "work/ollama/ollama",
                           parent / ".local/ollama/ollama.exe"])
    candidates.append(shutil.which("ollama"))
    # A new Windows installation may not reach this terminal's PATH until restart.
    for variable, relative in (("LOCALAPPDATA", "Programs/Ollama/ollama.exe"),
                               ("PROGRAMFILES", "Ollama/ollama.exe")):
        if os.environ.get(variable):
            candidates.append(Path(os.environ[variable]) / relative)
    return next((Path(p).resolve() for p in candidates if p and Path(p).is_file()), None)


def ollama_environment(executable):
    env = os.environ.copy()
    env["OLLAMA_HOST"] = env.get("CLINIC_OLLAMA_URL", "127.0.0.1:11434")
    cache_root = executable.parent.parent
    portable = (cache_root.name in {"work", "local-ai", ".local"}
                or (cache_root / "models").is_dir())
    if portable:
        env.setdefault("OLLAMA_MODELS", str(cache_root / "models"))
        env.setdefault("OLLAMA_VULKAN", "1")
    env["OLLAMA_KEEP_ALIVE"] = "30m"
    env["OLLAMA_NO_CLOUD"] = "1"
    env["OLLAMA_NUM_PARALLEL"] = "1"
    return env


def use_existing_server(port, no_browser):
    """Discover a running app before bind: Windows SO_REUSEADDR is not exclusive."""
    if port == 0:
        return False
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=1):
            pass
    except OSError:
        return False
    address = f"http://127.0.0.1:{port}"
    try:
        health = request_json(address + "/api/health")
    except (OSError, ValueError):
        raise SystemExit(f"Port {port} is occupied. Try --port {port + 1 if port < 65535 else 8081}.")
    if not isinstance(health, dict) or health.get("synthetic_only") is not True or health.get("status") != "ok":
        raise SystemExit(f"Another app is using port {port}. Try --port 8081.")
    print(f"CareRoute is already running at {address}", flush=True)
    if not no_browser:
        webbrowser.open(address)
    return True


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument("--db", default=str(ROOT / "var/demo.sqlite3"))
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()
    if not 0 <= args.port <= 65535:
        parser.error("--port must be between 0 and 65535")
    if use_existing_server(args.port, args.no_browser):
        return
    from clinic.assessors import local_status
    from clinic.server import make_server

    status = local_status()
    if status["status"] == "offline":
        executable = find_ollama()
        if executable:
            log_dir = ROOT / "var"
            log_dir.mkdir(exist_ok=True)
            log_path = log_dir / "ollama.log"
            process = None
            try:
                with log_path.open("ab") as log:
                    process = subprocess.Popen([str(executable), "serve"], cwd=executable.parent,
                        env=ollama_environment(executable), stdout=log, stderr=subprocess.STDOUT,
                        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            except OSError as error:
                print(f"Local AI could not start: {error}. CareRoute will continue with staff review.", flush=True)
            if process is not None:
                print("Starting local AI runtime...", flush=True)
                for _ in range(30):
                    time.sleep(1)
                    status = local_status()
                    if status["status"] != "offline":
                        break
                    if process.poll() is not None:
                        print(f"The local runtime exited. Check {log_path}", flush=True)
                        break
    print(f"AI: {status['message']}", flush=True)
    if not status["available"]:
        print("To install local AI, run: powershell -ExecutionPolicy Bypass -File tools/install_local_ai.ps1", flush=True)
        print("The app will still preserve requests for staff review while AI is unavailable.", flush=True)
    address = f"http://127.0.0.1:{args.port}"
    try:
        server = make_server(args.port, args.db)
    except OSError as error:
        if use_existing_server(args.port, args.no_browser):
            return
        raise SystemExit(f"CareRoute could not listen on port {args.port}: {error}")
    address = f"http://127.0.0.1:{server.server_port}"
    print(f"CareRoute: {address}\nStaff login: reviewer / demo-reviewer\nPress Ctrl+C to stop CareRoute.", flush=True)
    if not args.no_browser:
        webbrowser.open(address)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
