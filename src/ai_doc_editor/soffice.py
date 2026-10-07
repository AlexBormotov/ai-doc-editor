"""LibreOffice headless wrapper: locate `soffice` and convert files."""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from pathlib import Path

_WINDOWS_DEFAULTS = [
    r"C:\Program Files\LibreOffice\program\soffice.exe",
    r"C:\Program Files (x86)\LibreOffice\program\soffice.exe",
]


class SofficeError(RuntimeError):
    pass


def find_soffice() -> str | None:
    """Return the soffice executable path, or None if LibreOffice is not installed."""
    env = os.environ.get("SOFFICE_PATH")
    if env and Path(env).exists():
        return env
    for name in ("soffice", "libreoffice"):
        found = shutil.which(name)
        if found:
            return found
    for path in _WINDOWS_DEFAULTS:
        if Path(path).exists():
            return path
    return None


def convert(src: Path, target_ext: str, out_dir: Path, timeout: int = 300) -> Path:
    """Convert `src` to `target_ext` ("pdf", "docx", "doc") into `out_dir`; return the new path."""
    exe = find_soffice()
    if exe is None:
        raise SofficeError("LibreOffice (soffice) not found; set SOFFICE_PATH")
    out_dir.mkdir(parents=True, exist_ok=True)
    filters = {"docx": "docx:MS Word 2007 XML", "doc": "doc:MS Word 97", "pdf": "pdf"}
    # A private profile per call avoids the global profile lock between parallel runs.
    with tempfile.TemporaryDirectory(prefix="soffice-profile-") as profile:
        cmd = [
            exe,
            f"-env:UserInstallation={Path(profile).as_uri()}",
            "--headless",
            "--norestore",
            "--convert-to",
            filters[target_ext],
            "--outdir",
            str(out_dir),
            str(src),
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    out = out_dir / f"{src.stem}.{target_ext}"
    if proc.returncode != 0 or not out.exists():
        raise SofficeError(f"soffice failed ({proc.returncode}): {proc.stderr or proc.stdout}")
    return out
