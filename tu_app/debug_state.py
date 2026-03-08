# tu_app/debug_state.py
"""
Thread-safe debug state capture for the Kairos debug dashboard.
Uses Django's cache framework (LocMemCache by default) so it works
safely across gunicorn workers — each worker keeps its own copy,
which is fine for a diagnostic dashboard.

Usage:
    from tu_app.debug_state import capture_prompt_flow, get_last_prompt_flow, push_log

    capture_prompt_flow({...})
    data = get_last_prompt_flow()
    push_log("INFO", "Something happened")
    logs = get_logs()
"""
import threading
from datetime import datetime

_lock = threading.Lock()

# ── In-process storage (one per gunicorn worker) ──────────────────────────
_last_prompt_flow: dict = {}
_logs: list = []          # ring-buffer, max 200 entries


def capture_prompt_flow(data: dict) -> None:
    """Store the latest prompt-flow snapshot."""
    global _last_prompt_flow
    with _lock:
        _last_prompt_flow = {**data, "captured_at": datetime.now().isoformat()}


def get_last_prompt_flow() -> dict:
    """Return the latest prompt-flow snapshot (or empty dict)."""
    with _lock:
        return dict(_last_prompt_flow)


MAX_LOGS = 200


def push_log(level: str, message: str, extra: str = "") -> None:
    """Append a log entry to the ring buffer."""
    global _logs
    entry = {
        "timestamp": datetime.now().isoformat(),
        "level": level,
        "message": message,
        "extra": extra,
    }
    with _lock:
        _logs.append(entry)
        if len(_logs) > MAX_LOGS:
            _logs = _logs[-MAX_LOGS:]


def get_logs(limit: int = 100) -> list:
    """Return the most recent *limit* log entries (newest first)."""
    with _lock:
        return list(reversed(_logs[-limit:]))
