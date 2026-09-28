"""
agent/common.py — the shared foundation both flows run on.

The deck says "both flows share the same agent; Flow 2 just adds a way to read
what changed and rank it." This module IS that shared agent: the Anthropic
client, the Reason -> Act -> Observe loop with a live token/cost meter, and the
generic tools every flow needs (run pytest on the selected subset, read a file,
patch a file, list a dir). Each flow adds its own data tools + system prompt.
"""

import os
import sys
import json
import time
import subprocess
from datetime import datetime
from pathlib import Path

# ---- paths (project root = parent of this package) ----------------------------
ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
SRC = ROOT / "src"
TESTS = ROOT / "tests"
STATE = ROOT / "._agent_state"
STATE.mkdir(exist_ok=True)

# UTF-8 console on Windows
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


# ---- terminal colours ---------------------------------------------------------
class C:
    RESET = "\033[0m"; BOLD = "\033[1m"; CYAN = "\033[36m"; YELLOW = "\033[33m"
    GREEN = "\033[32m"; RED = "\033[31m"; GREY = "\033[90m"; MAGENTA = "\033[35m"


def _supports_color():
    if os.name == "nt":
        os.system("")
    return sys.stdout.isatty()


if not _supports_color():
    for _n in dir(C):
        if not _n.startswith("_"):
            setattr(C, _n, "")


# ---- .env loader --------------------------------------------------------------
def load_dotenv(path=None):
    path = path or (ROOT / ".env")
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


# ---- the selection threshold --------------------------------------------------
#: THE one place to change the cut-off. A component is selected when its risk
#: (Flow 1) or impact (Flow 2) reaches this number; everything below it is
#: skipped with a logged reason.
#:
#: Lower it  -> more components qualify -> more tests run -> fewer misses, less saving.
#: Raise it  -> fewer tests run -> bigger saving, more risk of missing something.
#:
#: Override for one run without editing this file:
#:     Windows : set RISK_THRESHOLD=3.0 && python run_poc.py --showcase
#:     bash    : RISK_THRESHOLD=3.0 python run_poc.py --showcase
#: or put RISK_THRESHOLD=3.0 in .env
#:
#: The schedule profiles in agent/schedules.py deliberately override this per
#: cadence (PR 2.0, daily 3.0, sprint 4.0, quarterly 2.0) — a pre-merge check
#: should be twitchier than a sprint sweep.
def _read_threshold(default=5.0):
    load_dotenv()                       # so RISK_THRESHOLD in .env is honoured
    raw = os.environ.get("RISK_THRESHOLD", "").strip()
    if not raw:
        return default
    try:
        return float(raw)
    except ValueError:
        print(f"{C.YELLOW}RISK_THRESHOLD={raw!r} is not a number — "
              f"falling back to {default}{C.RESET}")
        return default


THRESHOLD = _read_threshold()


# ---- date parsing (shared by both flows) --------------------------------------
def parse_date(s):
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%d-%m-%Y", "%m/%d/%Y", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(str(s).strip()[:19], fmt)
        except (ValueError, AttributeError):
            continue
    return datetime.now()


# ---- Anthropic client (lazy: dry runs never need a key) -----------------------
MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-5")
PRICE_IN_PER_MTOK = 2.00
PRICE_OUT_PER_MTOK = 10.00

_client = None


def get_client():
    """Create the Anthropic client on first use. Exits with a friendly message
    if no key is set — but only when a flow actually needs the LLM."""
    global _client
    if _client is not None:
        return _client
    load_dotenv()
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        sys.exit(
            f"{C.RED}ERROR: ANTHROPIC_API_KEY not set.{C.RESET}\n"
            "Set it, e.g.:  $env:ANTHROPIC_API_KEY = \"sk-ant-...\"  (PowerShell)\n"
            "                export ANTHROPIC_API_KEY=sk-ant-...       (mac/linux)\n"
            "Or create a .env file at the project root with:  ANTHROPIC_API_KEY=sk-ant-...\n"
            "No key yet? Run  python dry_run.py  to see the deterministic pipeline."
        )
    from anthropic import Anthropic
    _client = Anthropic(api_key=api_key)
    return _client


# ---- generic tools shared by both flows ---------------------------------------
def run_pytest(paths=""):
    """Run pytest on space-separated paths; empty = the selected subset written
    by the flow's select_* tool. Source under test is src/swaglabs.py."""
    if not paths:
        sel = STATE / "selected.json"
        targets = json.loads(sel.read_text()) if sel.exists() else ["tests"]
    else:
        targets = paths.split()
    if not targets:
        return "No tests selected (all covered components were low risk / unchanged)."
    full = [str(ROOT / t) for t in targets]
    proc = subprocess.run(
        ["python", "-m", "pytest", *full, "-q", "--no-header"],
        capture_output=True, text=True, timeout=180, cwd=str(ROOT),
    )
    return (proc.stdout + proc.stderr)[-3000:] or "no output"


def efficiency_line(selected, total):
    """One-line efficiency summary: how much of the suite was avoided (Phase 1 · T2)."""
    ran = len(selected); avoided = max(0, total - ran)
    pct = round(avoided / total * 100) if total else 0
    return f"Efficiency: ran {ran} of {total} tests — avoided {avoided} ({pct}% of the suite skipped)."


def read_file(path):
    p = ROOT / path
    return p.read_text() if p.exists() else f"ERROR: {path} not found"


def write_file(path, content):
    p = ROOT / path
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content)
    return f"wrote {len(content)} chars to {path}"


def list_dir(path="."):
    p = ROOT / path
    if not p.exists():
        return f"ERROR: {path} not found"
    return "\n".join(sorted(f.name for f in p.iterdir())) or "(empty)"


GENERIC_TOOLS = [
    {"name": "run_pytest", "description": "Run pytest on space-separated paths; empty = the selected subset. Source path is src/swaglabs.py.", "input_schema": {"type": "object", "properties": {"paths": {"type": "string"}}}},
    {"name": "read_file", "description": "Read a file, e.g. 'src/swaglabs.py' to inspect source before fixing.", "input_schema": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}},
    {"name": "write_file", "description": "Overwrite a file, e.g. to patch the bug in src/swaglabs.py. Do not weaken tests.", "input_schema": {"type": "object", "properties": {"path": {"type": "string"}, "content": {"type": "string"}}, "required": ["path", "content"]}},
    {"name": "list_dir", "description": "List a directory, e.g. 'src' or 'tests'.", "input_schema": {"type": "object", "properties": {"path": {"type": "string"}}}},
]

GENERIC_IMPL = {
    "run_pytest": run_pytest, "read_file": read_file,
    "write_file": write_file, "list_dir": list_dir,
}


# ---- the Reason -> Act -> Observe loop ----------------------------------------
def _create(system, tools, messages, max_attempts=5):
    from anthropic import APIStatusError, RateLimitError
    client = get_client()
    for attempt in range(1, max_attempts + 1):
        try:
            return client.messages.create(model=MODEL, max_tokens=8000,
                                           system=system, tools=tools, messages=messages)
        except (RateLimitError, APIStatusError) as e:
            status = getattr(e, "status_code", None)
            if not (isinstance(e, RateLimitError) or status in (408, 429, 500, 502, 503, 504, 529)) or attempt == max_attempts:
                raise
            delay = 2 ** attempt
            print(f"{C.GREY}[rate-limit] sleeping {delay:.1f}s (attempt {attempt}/{max_attempts}){C.RESET}")
            time.sleep(delay)


def _color(output):
    low = output.lower()
    if "passed" in low and "failed" not in low and "error" not in low:
        return C.GREEN
    if "failed" in low or "error" in low or output.startswith("ERROR"):
        return C.RED
    if "high" in low or "blocker" in low or "critical" in low:
        return C.YELLOW
    return C.RESET


def run_agent(task, tools, tool_impl, system, max_steps=16):
    """Drive the agent: Reason -> Act -> Observe until it stops (or hits max_steps)."""
    messages = [{"role": "user", "content": task}]
    tin = tout = 0
    for step in range(1, max_steps + 1):
        print(f"\n{C.MAGENTA}{'='*64}\n STEP {step}\n{'='*64}{C.RESET}")
        t0 = time.time()
        resp = _create(system, tools, messages)
        el = time.time() - t0
        tin += resp.usage.input_tokens
        tout += resp.usage.output_tokens
        cost = tin / 1e6 * PRICE_IN_PER_MTOK + tout / 1e6 * PRICE_OUT_PER_MTOK
        print(f"{C.GREY}[meter]  {el:4.1f}s  |  +{resp.usage.input_tokens} in / +{resp.usage.output_tokens} out  |  total ${cost:.4f}{C.RESET}")
        for b in resp.content:
            if b.type == "text" and b.text.strip():
                print(f"{C.CYAN}[reason] {b.text.strip()}{C.RESET}")
        calls = [b for b in resp.content if b.type == "tool_use"]
        if not calls:
            print(f"\n{C.GREEN}{C.BOLD}✓ Agent finished.{C.RESET} {C.GREY}({step} steps, ${cost:.4f} total){C.RESET}")
            return
        messages.append({"role": "assistant", "content": resp.content})
        results = []
        for call in calls:
            print(f"{C.YELLOW}[act]    {call.name}({json.dumps(call.input)[:120]}){C.RESET}")
            try:
                out = tool_impl[call.name](**call.input)
            except Exception as e:  # noqa: BLE001
                out = f"ERROR: {e}"
            print(f"{_color(out)}[observe] {out[:400].replace(chr(10), chr(10)+'         ')}{C.RESET}")
            results.append({"type": "tool_result", "tool_use_id": call.id, "content": out})
        messages.append({"role": "user", "content": results})
    print(f"\n{C.RED}⚠ Hit max steps ({max_steps}) without finishing.{C.RESET}")
