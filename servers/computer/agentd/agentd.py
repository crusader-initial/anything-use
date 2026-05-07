"""
agentd — tiny HTTP sidecar that exposes desktop control inside the container.

Listens on 127.0.0.1:9222 only. Translates REST calls to xdotool / scrot /
bash. The host-side MCP wrapper proxies its tool calls through here.
"""

from __future__ import annotations

import base64
import json
import os
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

DISPLAY = os.environ.get("DISPLAY", ":1")
LOG_PATH = Path(os.environ.get("AGENTD_LOG", "/var/log/agentd.jsonl"))
LOG_PATH.parent.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="agentd", version="0.1.0")


def _x_env() -> dict[str, str]:
    return {"DISPLAY": DISPLAY, "PATH": os.environ["PATH"], "HOME": os.environ.get("HOME", "/root")}


def _xdo(*args: str, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["xdotool", *args],
        env=_x_env(),
        capture_output=True,
        text=True,
        check=check,
    )


def _audit(tool: str, payload: dict, result_summary: str) -> None:
    line = json.dumps(
        {
            "ts": datetime.now(timezone.utc).isoformat(),
            "tool": tool,
            "args": {k: v for k, v in payload.items() if k != "text" or len(str(v)) < 200},
            "result": result_summary[:200],
        },
        ensure_ascii=False,
    )
    with LOG_PATH.open("a") as f:
        f.write(line + "\n")


# --- request models ---------------------------------------------------------


class XY(BaseModel):
    x: int
    y: int


class ClickIn(BaseModel):
    x: int
    y: int
    button: str = "left"  # left | middle | right
    count: int = 1


class DragIn(BaseModel):
    x1: int
    y1: int
    x2: int
    y2: int
    duration_ms: int = 300


class TypeIn(BaseModel):
    text: str
    delay_ms: int = 12


class KeyIn(BaseModel):
    combo: str  # xdotool keysym or chord, e.g. "ctrl+l", "Return", "Tab"


class ScrollIn(BaseModel):
    x: int
    y: int
    direction: str  # up | down | left | right
    amount: int = 3


class BashIn(BaseModel):
    cmd: str
    timeout_sec: int = 30


class UrlIn(BaseModel):
    url: str


# --- routes ----------------------------------------------------------------


@app.get("/healthz")
def healthz():
    try:
        subprocess.run(["xdpyinfo", "-display", DISPLAY], capture_output=True, check=True)
        return {"ok": True, "display": DISPLAY}
    except subprocess.CalledProcessError:
        raise HTTPException(503, "X display not ready")


@app.get("/size")
def size():
    out = subprocess.run(
        ["xdpyinfo", "-display", DISPLAY],
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    for line in out.splitlines():
        if "dimensions:" in line:
            dim = line.split()[1]
            w, h = dim.split("x")
            return {"width": int(w), "height": int(h)}
    raise HTTPException(500, "couldn't parse xdpyinfo dimensions")


@app.post("/screenshot")
def screenshot():
    path = "/tmp/agentd-shot.png"
    subprocess.run(
        ["scrot", "--overwrite", "-o", path],
        env=_x_env(),
        capture_output=True,
        check=True,
    )
    data = Path(path).read_bytes()
    _audit("screenshot", {}, f"{len(data)} bytes")
    return {"png_b64": base64.b64encode(data).decode("ascii")}


@app.post("/click")
def click(b: ClickIn):
    button_map = {"left": 1, "middle": 2, "right": 3}
    if b.button not in button_map:
        raise HTTPException(400, f"unknown button: {b.button}")
    _xdo("mousemove", str(b.x), str(b.y))
    for _ in range(max(1, b.count)):
        _xdo("click", str(button_map[b.button]))
    _audit("click", b.model_dump(), "ok")
    return {"ok": True}


@app.post("/move")
def move(p: XY):
    _xdo("mousemove", str(p.x), str(p.y))
    _audit("move", p.model_dump(), "ok")
    return {"ok": True}


@app.post("/drag")
def drag(d: DragIn):
    _xdo("mousemove", str(d.x1), str(d.y1))
    _xdo("mousedown", "1")
    steps = max(2, d.duration_ms // 20)
    for i in range(1, steps + 1):
        nx = int(d.x1 + (d.x2 - d.x1) * i / steps)
        ny = int(d.y1 + (d.y2 - d.y1) * i / steps)
        _xdo("mousemove", str(nx), str(ny))
        time.sleep(d.duration_ms / 1000 / steps)
    _xdo("mouseup", "1")
    _audit("drag", d.model_dump(), "ok")
    return {"ok": True}


@app.post("/type")
def type_(t: TypeIn):
    # `--` ends arg parsing; without it, text starting with - would be flags.
    _xdo("type", "--delay", str(t.delay_ms), "--", t.text)
    _audit("type", {"len": len(t.text)}, "ok")
    return {"ok": True}


@app.post("/key")
def key(k: KeyIn):
    _xdo("key", "--", k.combo)
    _audit("key", k.model_dump(), "ok")
    return {"ok": True}


@app.post("/scroll")
def scroll(s: ScrollIn):
    direction_button = {"up": 4, "down": 5, "left": 6, "right": 7}
    if s.direction not in direction_button:
        raise HTTPException(400, f"unknown direction: {s.direction}")
    _xdo("mousemove", str(s.x), str(s.y))
    for _ in range(max(1, s.amount)):
        _xdo("click", str(direction_button[s.direction]))
    _audit("scroll", s.model_dump(), "ok")
    return {"ok": True}


@app.post("/bash")
def bash(b: BashIn):
    try:
        r = subprocess.run(
            ["bash", "-lc", b.cmd],
            capture_output=True,
            text=True,
            timeout=b.timeout_sec,
        )
        _audit("bash", {"cmd": b.cmd[:200]}, f"exit={r.returncode}")
        return {"stdout": r.stdout, "stderr": r.stderr, "exit": r.returncode}
    except subprocess.TimeoutExpired as e:
        _audit("bash", {"cmd": b.cmd[:200]}, f"timeout {b.timeout_sec}s")
        return {
            "stdout": (e.stdout or "") if isinstance(e.stdout, str) else "",
            "stderr": ((e.stderr or "") if isinstance(e.stderr, str) else "")
            + f"\n[timeout after {b.timeout_sec}s]",
            "exit": 124,
        }


@app.post("/open_url")
def open_url(u: UrlIn):
    # firefox-esr is preinstalled in the anthropic-quickstarts image.
    subprocess.Popen(
        ["firefox-esr", u.url],
        env=_x_env(),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    _audit("open_url", u.model_dump(), "spawned")
    return {"ok": True}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=9222, log_level="warning")
