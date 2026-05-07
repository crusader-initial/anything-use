"""
Host-side MCP server. Bridges MCP `tool/call` requests over stdio to agentd
running inside the docker container at 127.0.0.1:9222.

Started by claude-code / codex via the registration in scripts/install-*.sh.

Requires: pip install mcp httpx
"""

from __future__ import annotations

import base64
import os
import sys

import httpx
from mcp.server.fastmcp import FastMCP, Image

AGENTD_URL = os.environ.get("AGENTD_URL", "http://127.0.0.1:9222")
TIMEOUT = float(os.environ.get("AGENTD_TIMEOUT", "60"))

mcp = FastMCP("anything-use/computer")
_client = httpx.Client(base_url=AGENTD_URL, timeout=TIMEOUT)


def _check_alive() -> str | None:
    """Return None if agentd is reachable, else a human-readable error."""
    try:
        r = _client.get("/healthz")
        if r.status_code == 200:
            return None
        return f"agentd /healthz returned {r.status_code}: {r.text[:200]}"
    except httpx.HTTPError as e:
        return (
            f"agentd at {AGENTD_URL} is not reachable: {e}\n"
            "Start the container: docker compose -f servers/computer/docker-compose.yml up -d"
        )


def _post(path: str, json: dict | None = None) -> dict:
    err = _check_alive()
    if err:
        raise RuntimeError(err)
    r = _client.post(path, json=json or {})
    r.raise_for_status()
    return r.json()


# --- tools -----------------------------------------------------------------


@mcp.tool()
def computer_health() -> str:
    """Return whether agentd inside the container is reachable, and the screen size."""
    err = _check_alive()
    if err:
        return f"DOWN — {err}"
    size = _client.get("/size").json()
    return f"OK — display={size['width']}x{size['height']} agentd={AGENTD_URL}"


@mcp.tool()
def computer_screen_size() -> dict:
    """Return the desktop's pixel dimensions: {width, height}."""
    err = _check_alive()
    if err:
        raise RuntimeError(err)
    return _client.get("/size").json()


@mcp.tool()
def computer_screenshot() -> Image:
    """Capture the current desktop and return it as a PNG."""
    data = _post("/screenshot")
    png = base64.b64decode(data["png_b64"])
    return Image(data=png, format="png")


@mcp.tool()
def computer_click(x: int, y: int, button: str = "left", count: int = 1) -> str:
    """
    Move the cursor to (x, y) and click. Coordinates are in screen pixels,
    origin top-left. button is "left" | "middle" | "right". count=2 for double-click.
    """
    _post("/click", {"x": x, "y": y, "button": button, "count": count})
    return f"clicked {button} x{count} at ({x},{y})"


@mcp.tool()
def computer_move(x: int, y: int) -> str:
    """Move the cursor to (x, y) without clicking."""
    _post("/move", {"x": x, "y": y})
    return f"moved to ({x},{y})"


@mcp.tool()
def computer_drag(x1: int, y1: int, x2: int, y2: int, duration_ms: int = 300) -> str:
    """Press at (x1,y1), drag to (x2,y2) over duration_ms, then release."""
    _post(
        "/drag",
        {"x1": x1, "y1": y1, "x2": x2, "y2": y2, "duration_ms": duration_ms},
    )
    return f"dragged ({x1},{y1}) -> ({x2},{y2}) in {duration_ms}ms"


@mcp.tool()
def computer_type(text: str, delay_ms: int = 12) -> str:
    """
    Type text into whatever is focused. delay_ms is the per-keystroke delay.
    Supports unicode (the container has UTF-8 locale).
    """
    _post("/type", {"text": text, "delay_ms": delay_ms})
    return f"typed {len(text)} chars"


@mcp.tool()
def computer_key(combo: str) -> str:
    """
    Press a key or chord using xdotool keysym notation.
    Examples: "Return", "Tab", "Escape", "ctrl+l", "ctrl+shift+t", "Page_Down".
    """
    _post("/key", {"combo": combo})
    return f"pressed {combo}"


@mcp.tool()
def computer_scroll(x: int, y: int, direction: str, amount: int = 3) -> str:
    """
    Scroll at (x, y). direction is "up" | "down" | "left" | "right".
    amount is the number of wheel clicks.
    """
    _post("/scroll", {"x": x, "y": y, "direction": direction, "amount": amount})
    return f"scrolled {direction} x{amount} at ({x},{y})"


@mcp.tool()
def computer_bash(cmd: str, timeout_sec: int = 30) -> dict:
    """
    Run a bash command inside the container. Returns {stdout, stderr, exit}.
    Use for installing packages, file ops, anything that doesn't need a GUI.
    """
    return _post("/bash", {"cmd": cmd, "timeout_sec": timeout_sec})


@mcp.tool()
def computer_open_url(url: str) -> str:
    """Open a URL in the container's Firefox."""
    _post("/open_url", {"url": url})
    return f"opened {url} in firefox-esr"


if __name__ == "__main__":
    # FastMCP defaults to stdio when run directly.
    try:
        mcp.run()
    except KeyboardInterrupt:
        sys.exit(0)
