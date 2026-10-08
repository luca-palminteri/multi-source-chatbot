"""Run the actual terminal CLI with fixed read-only synthetic demo prompts."""
import json
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]


def main():
    runtime = ROOT / "runtime"
    runtime.mkdir(exist_ok=True)
    transcript = runtime / "chat-verified.log"
    messages = ["Hey, what can I ask?", "What is our lunar travel reimbursement policy?",
                "/new", "Which team handles VPN access, and what does the access policy require?", "/exit"]
    started = time.monotonic()
    with transcript.open("w", encoding="utf-8") as output:
        process = subprocess.run([sys.executable, "-u", "-m", "assistant.cli", "chat", "--debug"],
                                 input="\n".join(messages) + "\n", text=True, encoding="utf-8",
                                 stdout=output, stderr=subprocess.STDOUT, cwd=ROOT,
                                 env={**os.environ, "PYTHONUTF8": "1"}, timeout=360)
    text = transcript.read_text(encoding="utf-8")
    checks = {"exit_code_zero": process.returncode == 0,
              "three_answers": text.count("Assistant:") == 3,
              "no_execution_failures": "Failure type:" not in text and "Chat connection failed" not in text,
              "new_conversation": "Starting a fresh conversation" in text and text.count("Conversation:") == 2,
              "vpn_answer": all(term in text.lower() for term in ("it operations", "manager approval", "mfa"))}
    report = {"passed": all(checks.values()), "checks": checks,
              "elapsed_seconds": round(time.monotonic() - started, 1), "exit_code": process.returncode,
              "prompts": messages, "transcript": str(transcript)}
    (runtime / "terminal-verification.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2), flush=True)
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
