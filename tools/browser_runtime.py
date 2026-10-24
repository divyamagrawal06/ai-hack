"""Use an installed Chromium browser before requiring a Playwright download."""
import os
from pathlib import Path
import shutil


def browser_launch_options():
    candidates = [os.environ.get("CAREROUTE_BROWSER"), shutil.which("chromium"),
                  shutil.which("chromium-browser"), shutil.which("google-chrome")]
    for env in ("PROGRAMFILES", "PROGRAMFILES(X86)", "LOCALAPPDATA"):
        folder = os.environ.get(env)
        if folder:
            candidates.extend([Path(folder) / "Google/Chrome/Application/chrome.exe",
                               Path(folder) / "Microsoft/Edge/Application/msedge.exe"])
    executable = next((str(p) for p in candidates if p and Path(p).is_file()), None)
    options = {"headless": True}
    if executable:
        options["executable_path"] = executable
    return options
