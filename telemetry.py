"""
Anvil Telemetry — Anonymous usage tracking for open-source improvement.

Logs:
  WHO:   anonymous UUID (generated once, no PII)
  WHERE: country from timezone, OS, Python version
  WHAT:  problem category (auto-classified), step durations, total spend
  FAIL:  error type, step where it failed, stack trace (no user data)

Does NOT log:
  - Problem statements, context, or audience
  - Research content, articles, or snippets
  - Final documents, synthesis, or hypotheses
  - Any file contents from user's machine

Opt out: set ANVIL_TELEMETRY=off in environment
"""

import json
import os
import time
import uuid
import platform
import traceback
from pathlib import Path
from datetime import datetime, timezone

TELEMETRY_DIR = Path.home() / ".anvil" / "telemetry"
DEVICE_ID_FILE = Path.home() / ".anvil" / "device_id"

def _is_enabled():
    return os.environ.get("ANVIL_TELEMETRY", "on").lower() != "off"

def _get_device_id():
    """Get or create a persistent anonymous device ID."""
    DEVICE_ID_FILE.parent.mkdir(parents=True, exist_ok=True)
    if DEVICE_ID_FILE.exists():
        return DEVICE_ID_FILE.read_text().strip()
    did = str(uuid.uuid4())
    DEVICE_ID_FILE.write_text(did)
    return did

def _classify_problem(topic):
    """Auto-classify problem into a category (no actual topic stored)."""
    topic_lower = topic.lower() if topic else ""
    categories = [
        (["refin", "crude", "oil", "petro", "lng", "energy", "hormuz", "opec"], "energy"),
        (["saas", "software", "cloud", "arr", "nrr", "subscription"], "saas"),
        (["ai", "machine learning", "llm", "gpt", "model", "artificial intelligence"], "ai"),
        (["consult", "mckinsey", "bcg", "bain", "mbb", "advisory"], "consulting"),
        (["pharma", "drug", "clinical", "fda", "biotech"], "pharma"),
        (["bank", "financ", "invest", "credit", "lending"], "finance"),
        (["retail", "consumer", "brand", "ecommerce", "d2c"], "retail"),
        (["manufact", "supply chain", "logistics", "warehouse"], "manufacturing"),
        (["govern", "policy", "regulation", "public sector"], "government"),
        (["health", "hospital", "patient", "medical"], "healthcare"),
    ]
    for keywords, category in categories:
        if any(k in topic_lower for k in keywords):
            return category
    return "other"

def _get_locale():
    """Get rough geographic info from timezone, no IP lookup."""
    try:
        tz = datetime.now(timezone.utc).astimezone().tzinfo
        tz_name = str(tz) if tz else "unknown"
    except Exception:
        tz_name = "unknown"
    return {
        "timezone": tz_name,
        "os": platform.system(),
        "python": platform.python_version(),
    }

def log_run_start(topic, audience):
    """Log when a run starts."""
    if not _is_enabled():
        return
    TELEMETRY_DIR.mkdir(parents=True, exist_ok=True)
    event = {
        "event": "run_start",
        "device_id": _get_device_id(),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "category": _classify_problem(topic),
        "topic_length": len(topic) if topic else 0,
        "has_audience": bool(audience),
        "locale": _get_locale(),
    }
    _append(event)

def log_step_complete(step_num, step_name, duration_s, spend_usd):
    """Log when a step completes."""
    if not _is_enabled():
        return
    event = {
        "event": "step_complete",
        "device_id": _get_device_id(),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "step": step_num,
        "step_name": step_name,
        "duration_s": round(duration_s, 1),
        "spend_usd": round(spend_usd, 4) if spend_usd else None,
    }
    _append(event)

def log_run_complete(total_duration_s, total_spend, num_buckets, num_hypotheses):
    """Log when a full run completes."""
    if not _is_enabled():
        return
    event = {
        "event": "run_complete",
        "device_id": _get_device_id(),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "total_duration_s": round(total_duration_s, 1),
        "total_spend_usd": round(total_spend, 4) if total_spend else None,
        "num_buckets": num_buckets,
        "num_hypotheses": num_hypotheses,
    }
    _append(event)

def log_error(step_num, error_type, error_msg):
    """Log when an error occurs. Only error type and generic message, no user data."""
    if not _is_enabled():
        return
    # Sanitize error message — remove any paths or user-specific content
    safe_msg = error_msg[:200] if error_msg else ""
    # Remove file paths
    import re
    safe_msg = re.sub(r'[A-Z]:\\[^\s]+', '<path>', safe_msg)
    safe_msg = re.sub(r'/[^\s]+', '<path>', safe_msg)

    event = {
        "event": "error",
        "device_id": _get_device_id(),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "step": step_num,
        "error_type": error_type,
        "error_msg": safe_msg,
        "locale": _get_locale(),
    }
    _append(event)

def _append(event):
    """Append event to daily log file."""
    try:
        TELEMETRY_DIR.mkdir(parents=True, exist_ok=True)
        today = datetime.now().strftime("%Y-%m-%d")
        log_file = TELEMETRY_DIR / f"{today}.jsonl"
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(event, ensure_ascii=False) + "\n")
    except Exception:
        pass  # Telemetry should never break the pipeline


def get_summary():
    """Get a summary of telemetry data for display."""
    if not TELEMETRY_DIR.exists():
        return "No telemetry data yet."

    total_runs = 0
    total_errors = 0
    categories = {}
    total_spend = 0

    for f in sorted(TELEMETRY_DIR.glob("*.jsonl")):
        for line in f.read_text(encoding="utf-8").strip().split("\n"):
            if not line:
                continue
            try:
                e = json.loads(line)
                if e["event"] == "run_start":
                    total_runs += 1
                    cat = e.get("category", "other")
                    categories[cat] = categories.get(cat, 0) + 1
                elif e["event"] == "error":
                    total_errors += 1
                elif e["event"] == "run_complete":
                    total_spend += e.get("total_spend_usd", 0) or 0
            except Exception:
                pass

    lines = [
        f"Total runs: {total_runs}",
        f"Total errors: {total_errors}",
        f"Total spend: ${total_spend:.2f}",
        f"Categories: {json.dumps(categories)}",
    ]
    return "\n".join(lines)
