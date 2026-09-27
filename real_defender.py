"""
The real seam the README pointed at: instead of the naive blocklist stand-in
in fixtures.py, this shells out to the ACTUAL mcpaudit/memsentry/ragsentry
CLIs (installed separately -- see requirements below) and treats a nonzero
exit code from `--fail-on low` as "blocked."

Three of the four surfaces map cleanly onto a real static-artifact scanner
in the portfolio, because each of those tools audits a stored artifact, not
a live turn:

    tool_poisoning   -> mcpaudit  (scans an MCP server's tool manifest)
    memory_injection -> memsentry (scans a memory/context text file)
    rag_injection    -> ragsentry (scans a RAG source document)

`prompt_injection` deliberately has NO real mapping here and keeps using
fixtures.DefendedAgent's naive blocklist. This isn't an oversight -- none of
the five portfolio tools scan a live user prompt, because a prompt isn't a
stored artifact to statically audit; it's exactly the kind of turn-level
content none of them were built to touch (that's a real, honestly-stated
gap in the portfolio, not something to paper over by force-fitting one of
the other scanners onto it).

Cost note, read before running a large experiment with this: each call
here spawns a real subprocess (mcpaudit additionally does a full MCP
stdio handshake with its own subprocess). That's 2-3 orders of magnitude
slower than the in-memory regex check in fixtures.py -- a full 30-seed x
15-generation x 20-population x 20-sample run like the bundled one would
mean hundreds of thousands of real subprocess spawns per surface. See
`experiment.py --real-scanners` for a deliberately small-scale run sized
for that cost instead of pretending it's free.
"""
from __future__ import annotations

import json
import subprocess
import tempfile
from pathlib import Path

_MCP_SERVER_TEMPLATE = '''#!/usr/bin/env python3
import json, sys

DESCRIPTION = {description!r}

def send(payload):
    sys.stdout.write(json.dumps(payload) + "\\n")
    sys.stdout.flush()

TOOLS = [{{"name": "do_something", "description": DESCRIPTION,
          "inputSchema": {{"type": "object", "properties": {{}}}}}}]

for line in sys.stdin:
    line = line.strip()
    if not line:
        continue
    try:
        msg = json.loads(line)
    except json.JSONDecodeError:
        continue
    method, msg_id = msg.get("method"), msg.get("id")
    if method == "initialize":
        send({{"jsonrpc": "2.0", "id": msg_id, "result": {{
            "protocolVersion": "2024-11-05", "capabilities": {{}},
            "serverInfo": {{"name": "adversagen-probe", "version": "1.0.0"}}}}}})
    elif method == "notifications/initialized":
        continue
    elif method == "tools/list":
        send({{"jsonrpc": "2.0", "id": msg_id, "result": {{"tools": TOOLS}}}})
    elif msg_id is not None:
        send({{"jsonrpc": "2.0", "id": msg_id, "error": {{"code": -32601, "message": "not found"}}}})
'''


class RealScannerDefender:
    """Same interface as fixtures.DefendedAgent (.blocks / .evades), backed
    by the real CLIs instead of a blocklist. Raises RuntimeError up front
    if a needed CLI isn't on PATH, rather than silently reporting
    "not blocked" for every payload (a missing binary must never look like
    a scanner that let something through)."""

    _CLI_FOR_SURFACE = {
        "tool_poisoning": "mcpaudit",
        "memory_injection": "memsentry",
        "rag_injection": "ragsentry",
    }

    def __init__(self, timeout: float = 15.0) -> None:
        self.timeout = timeout
        missing = [cli for cli in set(self._CLI_FOR_SURFACE.values()) if not _on_path(cli)]
        if missing:
            raise RuntimeError(
                f"RealScannerDefender needs these CLIs on PATH: {missing}. "
                f"pip install them from their repos first."
            )

    def blocks(self, surface: str, rendered_text: str) -> bool:
        if surface == "tool_poisoning":
            return self._blocks_mcpaudit(rendered_text)
        if surface == "memory_injection":
            return self._blocks_file_scanner("memsentry", rendered_text)
        if surface == "rag_injection":
            return self._blocks_file_scanner("ragsentry", rendered_text)
        raise ValueError(
            f"RealScannerDefender has no real scanner mapping for surface {surface!r} "
            f"(prompt_injection is intentionally unmapped -- see module docstring)."
        )

    def evades(self, surface: str, rendered_text: str) -> bool:
        return not self.blocks(surface, rendered_text)

    def _blocks_mcpaudit(self, rendered_text: str) -> bool:
        script = _MCP_SERVER_TEMPLATE.format(description=rendered_text)
        with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as f:
            f.write(script)
            server_path = f.name
        try:
            result = subprocess.run(
                ["mcpaudit", "scan", "--fail-on", "low", "--", "python3", server_path],
                capture_output=True, timeout=self.timeout,
            )
            return result.returncode != 0
        except subprocess.TimeoutExpired:
            return False  # a hung scan is a scanner failure, not a caught attack -- fail open, not silently "blocked"
        finally:
            Path(server_path).unlink(missing_ok=True)

    def _blocks_file_scanner(self, cli: str, rendered_text: str) -> bool:
        with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False) as f:
            f.write(rendered_text + "\n")
            doc_path = f.name
        try:
            result = subprocess.run(
                [cli, doc_path, "--fail-on", "low"],
                capture_output=True, timeout=self.timeout,
            )
            return result.returncode != 0
        except subprocess.TimeoutExpired:
            return False
        finally:
            Path(doc_path).unlink(missing_ok=True)


def _on_path(cli: str) -> bool:
    from shutil import which
    return which(cli) is not None
