"""Install the pinned, official Windows Ollama CPU/Vulkan runtime (~40 MB).

HTTP range requests omit the large CUDA libraries. Each extracted file is checked
against a pinned SHA-256 before it is written. Uses Python stdlib and Windows curl.
The companion PowerShell installer verifies the Ollama Authenticode signature.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import json
from pathlib import Path
import shutil
import struct
import subprocess
import zlib


def install(destination: Path) -> None:
    manifest = json.loads(Path(__file__).with_name("ollama-windows-manifest.json").read_text())
    curl = shutil.which("curl.exe")
    if not curl:
        raise SystemExit("Windows curl.exe is required. Install Ollama from https://ollama.com/download instead.")
    destination = destination.resolve()
    destination.mkdir(parents=True, exist_ok=True)
    cache = destination.parent / "download-parts"
    cache.mkdir(exist_ok=True)
    entries = manifest["entries"]
    jobs = []
    for index, entry in enumerate(entries):
        target = (destination / entry["name"]).resolve()
        if not target.is_relative_to(destination):
            raise ValueError("Unsafe path in runtime manifest")
        if not entry["compressed"]:
            target.mkdir(parents=True, exist_ok=True)
            continue
        if target.exists() and hashlib.sha256(target.read_bytes()).hexdigest() == entry["sha256"]:
            continue
        start = entry["offset"]
        stop = start + 30 + len(entry["name"].encode()) + entry["compressed"] + 64
        for part, offset in enumerate(range(start, stop, 1024 * 1024)):
            jobs.append((index, part, offset, min(offset + 1024 * 1024, stop) - 1))

    def download(job):
        index, part, start, end = job
        file = cache / f"{index}-{part}.bin"
        if not file.exists() or file.stat().st_size != end - start + 1:
            result = subprocess.run(
                [curl, "-L", "--fail", "--retry", "4", "--retry-all-errors", "--max-time", "120",
                 "--silent", "--show-error", "--range", f"{start}-{end}", manifest["url"], "-o", str(file)],
                capture_output=True, text=True,
            )
            if result.returncode or not file.exists() or file.stat().st_size != end - start + 1:
                raise RuntimeError(f"Download failed for runtime part {index}-{part}: {result.stderr}")
        return index

    if jobs:
        print(f"Downloading Ollama {manifest['version']} CPU/Vulkan runtime (about 40 MB)...", flush=True)
        with ThreadPoolExecutor(max_workers=12) as pool:
            for count, future in enumerate(as_completed(pool.submit(download, job) for job in jobs), 1):
                future.result()
                if count % 10 == 0 or count == len(jobs):
                    print(f"Downloaded {count}/{len(jobs)} parts", flush=True)
        for index in sorted({job[0] for job in jobs}):
            entry = entries[index]
            count = sum(job[0] == index for job in jobs)
            payload = b"".join((cache / f"{index}-{part}.bin").read_bytes() for part in range(count))
            if payload[:4] != b"PK\x03\x04":
                raise ValueError("Invalid ZIP entry returned by download server")
            name_length, extra_length = struct.unpack_from("<HH", payload, 26)
            offset = 30 + name_length + extra_length
            compressed = payload[offset:offset + entry["compressed"]]
            raw = zlib.decompress(compressed, -15) if entry["compression"] == 8 else compressed
            if len(raw) != entry["size"] or hashlib.sha256(raw).hexdigest() != entry["sha256"]:
                raise ValueError(f"SHA-256 verification failed: {entry['name']}")
            target = destination / entry["name"]
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(raw)
    print(f"Verified Ollama runtime: {destination / 'ollama.exe'}", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("destination", type=Path)
    install(parser.parse_args().destination)
