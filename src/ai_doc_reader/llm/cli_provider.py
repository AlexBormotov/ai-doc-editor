"""Subscription CLIs (`claude`, `codex`, `agy`) in headless mode (spec.md 4.5).

Each call runs in an empty temporary directory with tools disabled or read-only, so text from a
document cannot make the agent act on the machine. In Docker the call goes to the host through
the CLI bridge (`scripts/cli_bridge.py`) instead of a local subprocess.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from pathlib import Path

import httpx

from ai_doc_reader.llm.base import LLMError, LLMProvider

CLIS = ("claude", "codex", "agy")


def run_cli(cli: str, model: str, system: str, user: str, timeout: float) -> str:
    """Run one headless CLI call on this machine and return the reply text."""
    if cli not in CLIS:
        raise LLMError(f"unknown CLI {cli!r}")
    exe = shutil.which(cli)
    if exe is None:
        raise LLMError(f"{cli} is not installed or not on PATH")
    with tempfile.TemporaryDirectory(prefix=f"adr-{cli}-") as tmp:
        stdin = None
        if cli == "claude":
            cmd = [
                exe,
                "-p",
                "--output-format",
                "json",
                "--tools",
                "",
                "--no-session-persistence",
                "--strict-mcp-config",
                "--system-prompt",
                system,
            ]
            stdin = user
        elif cli == "codex":
            last = Path(tmp) / "last.txt"
            cmd = [
                exe,
                "exec",
                "--sandbox",
                "read-only",
                "--skip-git-repo-check",
                "--ephemeral",
                "-C",
                tmp,
                "-o",
                str(last),
                "-",
            ]
            stdin = f"{system}\n\n{user}"
        else:  # agy
            cmd = [
                exe,
                "-p",
                f"{system}\n\n{user}",
                "--output-format",
                "json",
                "--sandbox",
                "--mode",
                "plan",
            ]
        if model and cli == "codex":
            cmd[-1:-1] = ["-m", model]  # before the trailing "-" (prompt on stdin)
        elif model:
            cmd += ["--model", model]
        try:
            proc = subprocess.run(
                cmd,
                input=stdin,
                capture_output=True,
                text=True,
                encoding="utf-8",
                timeout=timeout,
                cwd=tmp,
            )
        except subprocess.TimeoutExpired as e:
            raise LLMError(f"{cli} timed out after {timeout:.0f}s") from e
        if proc.returncode != 0:
            raise LLMError(f"{cli} exited {proc.returncode}: {(proc.stderr or proc.stdout)[-500:]}")
        if cli == "codex":
            return last.read_text(encoding="utf-8") if last.exists() else proc.stdout
        data = json.loads(proc.stdout)
        if cli == "claude":
            if data.get("is_error"):
                raise LLMError(f"claude: {data.get('result')}")
            return data.get("result", "")
        if data.get("status") != "SUCCESS":
            raise LLMError(f"agy: status {data.get('status')}")
        return data.get("response", "")


class CliProvider(LLMProvider):
    def __init__(
        self, cli: str, model: str, timeout: float, bridge_url: str = "", bridge_token: str = ""
    ):
        super().__init__(model)
        self.cli = cli
        self.key = f"cli:{cli}"
        self.timeout = timeout
        self.bridge_url = bridge_url.rstrip("/")
        self.bridge_token = bridge_token

    def complete_text(self, system: str, user: str, schema: dict) -> str:
        if not self.bridge_url:
            return run_cli(self.cli, self.model, system, user, self.timeout)
        try:
            resp = httpx.post(
                f"{self.bridge_url}/run",
                json={"cli": self.cli, "model": self.model, "system": system, "user": user},
                headers={"Authorization": f"Bearer {self.bridge_token}"},
                timeout=self.timeout + 30,
            )
        except httpx.HTTPError as e:
            raise LLMError(f"CLI bridge unreachable: {e}") from e
        if resp.status_code != 200:
            raise LLMError(f"CLI bridge {resp.status_code}: {resp.text[:300]}")
        return resp.json()["text"]
