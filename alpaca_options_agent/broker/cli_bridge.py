"""
Thin wrapper around Alpaca's official CLI (github.com/alpacahq/cli).

Why the CLI is used here rather than just the Python SDK everywhere: the
CLI is explicitly built "for AI agents, scripts, and automation
pipelines" — no interactive prompts, structured JSON on stdout, retry
logic on 429/5xx, and idempotent submission via --client-order-id. That
makes it a better fit than a long-lived Python process for the parts of
this agent that *should* be dumb, stateless, cron-friendly steps:
account/position status checks used as (a) an independent cross-check
against what the SDK session reports, so a divergence is caught rather
than silently trusted, and (b) the entry point a cron job or CI pipeline
would actually shell out to (see `scripts/run_paper_agent.sh`).

Order construction and multi-leg submission stay on the Python SDK
(`broker/client.py`) because building an N-leg options order from a
strategy decision needs real data structures, not a CLI flag; the CLI
covers the read side and simple equity/single-leg orders.

If the `alpaca` binary isn't installed, every method here raises
`AlpacaCliUnavailable` — callers treat that as "CLI cross-check skipped",
never as a fatal error, since the SDK path is fully self-sufficient.
"""
from __future__ import annotations

import json
import shutil
import subprocess
from typing import Any, Dict, List, Optional

from alpaca_options_agent.config import CONFIG


class AlpacaCliUnavailable(RuntimeError):
    pass


class AlpacaCli:
    def __init__(self, binary: Optional[str] = None, timeout_seconds: int = 20):
        self.binary = binary or CONFIG.cli_path
        self.timeout_seconds = timeout_seconds

    def _resolved_path(self) -> str:
        path = shutil.which(self.binary)
        if not path:
            raise AlpacaCliUnavailable(
                f"'{self.binary}' not found on PATH. Install with "
                "`brew install alpacahq/tap/cli` or "
                "`go install github.com/alpacahq/cli/cmd/alpaca@latest`. "
                "This is optional — the agent runs fully on the Python SDK "
                "without it; the CLI is used only as a cron-friendly status "
                "cross-check and satisfies the hackathon's CLI requirement."
            )
        return path

    def _run(self, args: List[str]) -> Any:
        binary = self._resolved_path()
        try:
            proc = subprocess.run(
                [binary, *args],
                capture_output=True,
                text=True,
                timeout=self.timeout_seconds,
                check=False,
            )
        except subprocess.TimeoutExpired as e:
            raise AlpacaCliUnavailable(f"alpaca CLI timed out: {' '.join(args)}") from e

        if proc.returncode != 0:
            raise AlpacaCliUnavailable(
                f"alpaca CLI exited {proc.returncode} for `{' '.join(args)}`: {proc.stderr.strip()}"
            )
        try:
            return json.loads(proc.stdout)
        except json.JSONDecodeError as e:
            raise AlpacaCliUnavailable(f"alpaca CLI returned non-JSON output: {proc.stdout[:200]}") from e

    def account_get(self) -> Dict:
        return self._run(["account", "get"])

    def positions_list(self) -> List[Dict]:
        result = self._run(["position", "list"])
        return result if isinstance(result, list) else result.get("positions", [])

    def option_contracts(self, underlying: str) -> List[Dict]:
        result = self._run(["option", "contracts", "--underlying-symbol", underlying])
        return result if isinstance(result, list) else result.get("option_contracts", [])

    def is_available(self) -> bool:
        try:
            self._resolved_path()
            return True
        except AlpacaCliUnavailable:
            return False
