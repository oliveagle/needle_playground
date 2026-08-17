"""Pre-stage Needle's engine and dependencies so the sandbox can run offline.

Usage:
    python scripts/bootstrap.py            # installs cactus-needle + native dylib
    python scripts/bootstrap.py --verify   # just check what is installed

We do *not* call pip at runtime; this script is for first-time setup only.
"""
from __future__ import annotations

import argparse
import os
import platform
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VENDOR = ROOT / "vendor"
BIN = ROOT / "bin" / "macos-arm64"
ENGINE_VERSION = "2.0.1"
HF_REPO = "Cactus-Compute/needle2"


def _py(tag: str) -> str:
    return f"cactus_needle-{ENGINE_VERSION}-py3-none-{tag}.whl"


def tag_for(plat: str, arch: str) -> str:
    if plat == "darwin":
        return f"macosx_11_0_{arch}"
    if plat == "win32":
        return "win_arm64" if arch == "arm64" else "win_amd64"
    arch = "aarch64" if arch == "arm64" else "x86_64"
    return f"manylinux2014_{arch}"


def ensure_wheel(plat: str, arch: str) -> Path:
    name = _py(tag_for(plat, arch))
    dest = VENDOR / name
    if dest.exists():
        return dest
    url = f"https://huggingface.co/{HF_REPO}/resolve/main/python/{name}"
    VENDOR.mkdir(parents=True, exist_ok=True)
    print(f"fetching {url} ...")
    subprocess.run(["curl", "-sLo", str(dest), url], check=True)
    if dest.stat().st_size < 100_000:
        raise SystemExit(f"download of {name} looks too small, aborting")
    return dest


def extract_dylib(wheel: Path) -> Path:
    if platform.system() == "Windows":
        lib_name = "libneedle.dll"
    elif platform.system() == "Darwin":
        lib_name = "libneedle.dylib"
    else:
        lib_name = "libneedle.so"
    out_dir = BIN / "lib"
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / lib_name
    if out.exists():
        return out
    with zipfile.ZipFile(wheel) as z:
        with z.open(f"needle/{lib_name}") as src, open(out, "wb") as dst:
            dst.write(src.read())
    return out


def install_packages() -> None:
    subprocess.run(
        ["pip", "install",
         "cactus-needle==2.0.2",
         "huggingface_hub", "httpx", "tqdm"],
        check=True,
    )


def verify() -> None:
    import needle  # noqa: F401
    import huggingface_hub  # noqa: F401
    print(f"needle at: {needle.__file__}")
    print(f"hf_hub at: {huggingface_hub.__file__}")


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--verify", action="store_true", help="only check imports")
    args = p.parse_args()

    if args.verify:
        verify()
        return

    if not (VENDOR / "cactus_needle-2.0.2-py3-none-any.whl").exists():
        subprocess.run(
            ["pip", "download", "cactus-needle==2.0.2",
             "--no-deps", "--dest", str(VENDOR)], check=True
        )
    plat, arch = platform.system().lower(), platform.machine().lower()
    wheel = ensure_wheel(plat, arch)
    extract_dylib(wheel)
    install_packages()
    verify()
    print("done")


if __name__ == "__main__":
    main()
