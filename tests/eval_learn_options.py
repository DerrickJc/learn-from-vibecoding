"""Rebuild isolated cases and measure real Codex learn calls; stdlib only.

Raw artifacts stay in the supplied output directory, outside the skill bundle.
No automated score represents learning gains or blind pedagogical assessment.
Requires Python 3.11+ and an authenticated Codex CLI. For example:
    python3 tests/eval_learn_options.py --output /tmp/learn-options build
    python3 tests/eval_learn_options.py --output /tmp/learn-options run small-light small-deep
CLI usage is preserved verbatim; resumed usage can include earlier turns and
must not be summed as per-turn costs. Use initial calls for cost comparisons.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import time
import tomllib

ROOT = Path(__file__).resolve().parents[1]
CASES = {
    "small-light": ("small", "$learn diff"),
    "small-deep": ("small", "$learn diff 深度"),
    "workflow-light": ("workflow", "$learn file src/payments/service.py"),
    "workflow-deep": ("workflow", "$learn file src/payments/service.py 深度"),
    "workflow-medium": ("workflow", "$learn file src/payments/service.py 中度"),
    "focus-syntax": ("workflow", "$learn file src/payments/service.py 轻度，聚焦语法规则"),
    "focus-principles": ("workflow", "$learn file src/payments/service.py 轻度，聚焦幂等性原理"),
    "focus-logic": ("workflow", "$learn file src/payments/service.py 轻度，聚焦功能逻辑"),
    "focus-architecture": ("workflow", "$learn file src/payments/service.py 轻度，聚焦整体架构"),
    "review-light": ("review", "$learn review"),
}
CASES = {name: (kind, prompt + "。请用中文讲解和出题。")
         for name, (kind, prompt) in CASES.items()}
WORKFLOW = {
    "src/payments/__init__.py": "",
    "src/payments/models.py": '''from dataclasses import dataclass
from decimal import Decimal


@dataclass
class Order:
    order_id: str
    amount: Decimal
    status: str = "pending"
    receipt: str | None = None
''',
    "src/payments/ports.py": '''from typing import Protocol
from decimal import Decimal
from .models import Order


class Store(Protocol):
    def get(self, order_id: str) -> Order: ...
    def save(self, order: Order) -> None: ...


class Gateway(Protocol):
    def charge(self, order_id: str, amount: Decimal, key: str) -> str: ...
''',
    "src/payments/service.py": '''from .ports import Gateway, Store


class PaymentService:
    def __init__(self, store: Store, gateway: Gateway):
        self.store = store
        self.gateway = gateway

    def pay(self, order_id: str, key: str) -> str | None:
        if not key:
            raise ValueError("idempotency key required")
        order = self.store.get(order_id)
        if order.status == "paid":
            return order.receipt
        if order.status != "pending":
            raise ValueError("order is not payable")
        receipt = self.gateway.charge(order.order_id, order.amount, key)
        order.status = "paid"
        order.receipt = receipt
        self.store.save(order)
        return receipt
''',
    "src/payments/adapters.py": '''from copy import deepcopy
from decimal import Decimal
from .models import Order


class MemoryStore:
    def __init__(self, order: Order):
        self.orders = {order.order_id: deepcopy(order)}
        self.fail_next_save = False

    def get(self, order_id: str) -> Order:
        return deepcopy(self.orders[order_id])

    def save(self, order: Order) -> None:
        if self.fail_next_save:
            self.fail_next_save = False
            raise OSError("database unavailable")
        self.orders[order.order_id] = deepcopy(order)


class FakeGateway:
    def __init__(self):
        self.receipts: dict[str, str] = {}
        self.charges: list[tuple[str, Decimal]] = []

    def charge(self, order_id: str, amount: Decimal, key: str) -> str:
        if key in self.receipts:
            return self.receipts[key]
        self.charges.append((order_id, amount))
        receipt = f"receipt-{len(self.charges)}"
        self.receipts[key] = receipt
        return receipt
''',
    "src/reporting.py": 'def report_title():\n    return "Unrelated reporting module"\n',
    "docs/decisions.md": "# Payment boundary\n\nThe service depends on Store and Gateway protocols so tests can substitute adapters.\nThe database save and external charge are separate operations; no distributed transaction is implemented.\n",
    "tests/test_payments.py": '''import unittest
from decimal import Decimal
from payments.models import Order
from payments.service import PaymentService
from payments.adapters import FakeGateway, MemoryStore


class PaymentTests(unittest.TestCase):
    def setup_service(self):
        store = MemoryStore(Order("A", Decimal("20")))
        gateway = FakeGateway()
        return store, gateway, PaymentService(store, gateway)

    def test_paid_retry_skips_charge(self):
        store, gateway, service = self.setup_service()
        first = service.pay("A", "key-1")
        self.assertEqual(service.pay("A", "key-2"), first)
        self.assertEqual(len(gateway.charges), 1)

    def test_save_failure_then_same_key(self):
        store, gateway, service = self.setup_service()
        store.fail_next_save = True
        with self.assertRaises(OSError):
            service.pay("A", "key-1")
        self.assertEqual(store.get("A").status, "pending")
        service.pay("A", "key-1")
        self.assertEqual(len(gateway.charges), 1)

    def test_save_failure_then_new_key(self):
        store, gateway, service = self.setup_service()
        store.fail_next_save = True
        with self.assertRaises(OSError):
            service.pay("A", "key-1")
        service.pay("A", "key-2")
        self.assertEqual(len(gateway.charges), 2)

    def test_empty_key_even_for_paid_order(self):
        _, _, service = self.setup_service()
        service.pay("A", "key-1")
        with self.assertRaises(ValueError):
            service.pay("A", "")
''',
}


def write_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n")


def build(output: Path) -> None:
    output.mkdir(parents=True, exist_ok=True)
    if any((output / case).exists() for case in CASES):
        raise SystemExit("Choose a fresh output directory; existing artifacts are preserved.")
    skill = ROOT / "skills/learn"
    hashes = {str(p.relative_to(skill)): hashlib.sha256(p.read_bytes()).hexdigest()
              for p in skill.rglob("*") if p.is_file() and "__pycache__" not in p.parts}
    version = subprocess.check_output(["codex", "--version"], text=True).strip()
    config_path = Path(os.environ.get("CODEX_HOME", str(Path.home() / ".codex"))) / "config.toml"
    config = tomllib.loads(config_path.read_text()) if config_path.exists() else {}
    write_json(output / "manifest.json", {"cases": CASES, "skill_sha256": hashes,
               "actual_prompts": {name: prompt for name, (_, prompt) in CASES.items()},
               "codex_version": version, "environment": "inherited Codex user configuration",
               "settings": {k: config.get(k) for k in ("model", "model_provider", "model_reasoning_effort")},
               "note": "one initial run per condition; no blind or human learning assessment"})
    for case, (kind, prompt) in CASES.items():
        repo = output / case
        repo.mkdir()
        files = WORKFLOW if kind != "small" else {
            "src/pricing.py": "def payable(total):\n    return round(total * 0.9, 2) if total >= 100 else total\n",
            "tests/test_pricing.py": "from pricing import payable\n\ndef test_threshold():\n    assert payable(200) == 180\n",
        }
        for name, content in files.items():
            path = repo / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
        (repo / ".gitignore").write_text(".learning/\n__pycache__/\n")
        shutil.copytree(skill, repo / ".agents/skills/learn", ignore=shutil.ignore_patterns("__pycache__"))
        for args in (("init", "-q"), ("add", "."),
                     ("-c", "user.name=Learn Evaluation", "-c", "user.email=eval@example.invalid",
                      "commit", "-qm", "fixture")):
            subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True)
        if kind == "small":
            target = repo / "src/pricing.py"
            target.write_text(target.read_text().replace(">= 100", ">= 200"))
        else:
            env = dict(os.environ, PYTHONPATH=str(repo / "src"))
            subprocess.run(["python3", "-m", "unittest", "discover", "-s", "tests"],
                           cwd=repo, env=env, check=True, capture_output=True)
        if kind == "review":
            notes = repo / ".learning/notes.md"
            notes.parent.mkdir()
            line = WORKFLOW["src/payments/service.py"].splitlines().index("        self.store.save(order)") + 1
            notes.write_text(f"## Gaps\n- [ ] [GAP G-save] Payment retry | 2026-09-28\n"
                "  Question: What happens when save fails after charging and the caller retries?\n"
                "  Correction: The stored order remains pending; reusing the same key avoids a second charge in FakeGateway.\n"
                f"  Source: src/payments/service.py:{line}\n  Last reviewed: never\n\n## Concepts\n")
        (output / f"{case}.prompt.txt").write_text(prompt)
    print(f"Built {len(CASES)} cases and verified independent payment facts in {output}", flush=True)


def run(output: Path, name: str, timeout: int, source: str | None = None, prompt: str | None = None) -> dict:
    if (output / f"{name}.jsonl").exists():
        raise SystemExit(f"Refusing to overwrite run {name}")
    if source:
        previous = json.loads((output / f"{source}.metrics.json").read_text())
        if not previous.get("completed") or not previous.get("thread_id"):
            raise SystemExit("Resume source did not complete")
        repo = Path(previous["repo"])
        cmd = ["codex", "exec", "resume", "--json", previous["thread_id"], "-"]
    else:
        repo = output / name
        cmd = ["codex", "exec", "--json", "--sandbox", "workspace-write", "-C", str(repo), "-"]
        prompt = (output / f"{name}.prompt.txt").read_text()
    (output / f"{name}.prompt.txt").write_text(prompt or "")
    notes = repo / ".learning/notes.md"
    (output / f"{name}.notes-before.md").write_text(notes.read_text() if notes.exists() else "")
    start = time.monotonic()
    timed_out = False
    print(f"Starting {name}", flush=True)
    with (output / f"{name}.jsonl").open("w") as stdout, (output / f"{name}.stderr.txt").open("w") as stderr:
        proc = subprocess.Popen(cmd, cwd=repo, stdin=subprocess.PIPE, stdout=stdout,
                                stderr=stderr, text=True, start_new_session=True)
        try:
            proc.communicate(prompt, timeout=timeout)
        except subprocess.TimeoutExpired:
            timed_out = True
            os.killpg(proc.pid, signal.SIGTERM)
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                os.killpg(proc.pid, signal.SIGKILL)
                proc.wait()
    elapsed = round(time.monotonic() - start, 2)
    events = []
    for line in (output / f"{name}.jsonl").read_text().splitlines():
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            pass
    thread = next((e.get("thread_id") for e in events if e.get("type") == "thread.started"), None)
    if source and not thread:
        thread = previous["thread_id"]
    messages = [e["item"]["text"] for e in events if e.get("type") == "item.completed"
                and e.get("item", {}).get("type") == "agent_message"]
    final = messages[-1] if messages else ""
    completed = next((e for e in reversed(events) if e.get("type") == "turn.completed"), {})
    commands = [e["item"] for e in events if e.get("type") == "item.completed"
                and e.get("item", {}).get("type") == "command_execution"]
    footer = re.search(r"后续题目数量为\s*[：:]?\s*(\d+)", final)
    question_ids = list(dict.fromkeys(re.findall(r"(?m)^\s*(?:#{1,6}\s*)?(?:[-*]\s*)?(?:\*\*)?Q(\d+)\b", final)))
    usage = completed.get("usage", {})
    stderr_text = (output / f"{name}.stderr.txt").read_text()
    stderr_signals = [word for word in ("tls handshake", "timed out", "unrecognized_model", "reconnecting")
                      if word in stderr_text.lower()]
    metrics = {"case": name, "source_run": source, "repo": str(repo), "thread_id": thread,
        "elapsed_seconds": elapsed, "exit_code": proc.returncode, "timed_out": timed_out,
        "completed": bool(completed), "usage": usage,
        "stderr_signals": stderr_signals,
        "noncached_input_estimate": usage.get("input_tokens", 0) - usage.get("cached_input_tokens", 0),
        "question_ids": question_ids, "future_questions": int(footer.group(1)) if footer else None,
        "footer_is_last_line": bool(re.search(r"后续题目数量为\s*\d+[。.]?\s*$", final)),
        "tool_calls": len(commands), "nonzero_tool_calls": sum(bool(x.get("exit_code")) for x in commands),
        "tool_output_chars": sum(len(x.get("aggregated_output", "")) for x in commands),
        "commands": [{"command": x.get("command"), "exit_code": x.get("exit_code")} for x in commands],
        "error_events": [e for e in events if e.get("type") in {"error", "turn.failed"}]}
    (output / f"{name}.final.md").write_text(final)
    (output / f"{name}.notes-after.md").write_text(notes.read_text() if notes.exists() else "")
    write_json(output / f"{name}.metrics.json", metrics)
    print(json.dumps({k: metrics[k] for k in ("case", "completed", "elapsed_seconds", "usage",
        "question_ids", "future_questions", "tool_calls", "nonzero_tool_calls")}, ensure_ascii=False), flush=True)
    return metrics


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    sub = parser.add_subparsers(dest="action", required=True)
    sub.add_parser("build")
    initial = sub.add_parser("run")
    initial.add_argument("cases", choices=tuple(CASES), nargs="+")
    initial.add_argument("--timeout", type=int, default=180)
    resume = sub.add_parser("resume")
    resume.add_argument("--from-run", required=True)
    resume.add_argument("--name", required=True)
    resume.add_argument("--prompt-file", type=Path, required=True)
    resume.add_argument("--timeout", type=int, default=180)
    finish = sub.add_parser("finish-unknown", help="answer each batch with an explicit unknown, without continue requests")
    finish.add_argument("--from-run", required=True)
    finish.add_argument("--name", required=True)
    finish.add_argument("--max-turns", type=int, default=6)
    finish.add_argument("--timeout", type=int, default=180)
    args = parser.parse_args()
    output = args.output.resolve()
    if args.action == "build":
        build(output)
    elif args.action == "resume":
        run(output, args.name, args.timeout, args.from_run, args.prompt_file.read_text())
    elif args.action == "finish-unknown":
        source = args.from_run
        initial = json.loads((output / f"{source}.metrics.json").read_text())
        seen = set(initial["question_ids"])
        for number in range(1, args.max_turns + 1):
            name = f"{args.name}-{number}"
            result = run(output, name, args.timeout, source, "这一组的待回答题我都不知道。")
            if not result["completed"]:
                raise SystemExit("Incomplete model call; no further answers submitted.")
            new_ids = set(result["question_ids"]) - seen
            seen.update(new_ids)
            if not new_ids and result["future_questions"] == 0:
                print(f"Completed scripted round; observed question IDs: {sorted(seen, key=int)}", flush=True)
                break
            if not new_ids:
                raise SystemExit("No new batch despite answering all pending questions; inspect artifacts.")
            source = name
        else:
            raise SystemExit("Turn bound reached; round not claimed complete.")
    else:
        failures = 0
        for case in args.cases:
            result = run(output, case, args.timeout)
            failures = 0 if result["completed"] else failures + 1
            if failures >= 2:
                raise SystemExit("Two consecutive incomplete calls; remaining cases not attempted.")


if __name__ == "__main__":
    main()
