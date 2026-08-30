#!/usr/bin/env python3
"""
AGT-DEV01 — M365 Agent Auto-Tester
Reads questions from scripts/agent_test_questions.json
Fires each to /api/agent/chat and evaluates response quality.
"""
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

AGENT_URL = os.getenv("AGENT_URL", "http://localhost:8080/api/agent/chat")
API_KEY = os.getenv("API_KEY", "")
DELAY_SECONDS = int(os.getenv("TEST_DELAY", "8"))
QUESTIONS_FILE = Path(__file__).parent / "agent_test_questions.json"

RULE_ID_PATTERN = re.compile(r"M365-[A-Z]+-[A-Z]+-\d+")
UUID_PATTERN = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", re.IGNORECASE)


def call_agent(message: str) -> dict:
    data = json.dumps({"message": message, "history": []}).encode()
    request = urllib.request.Request(
        AGENT_URL,
        data=data,
        headers={"Content-Type": "application/json", "Accept": "application/json", "X-API-Key": API_KEY},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.loads(response.read().decode())
    except urllib.error.HTTPError as error:
        body = error.read().decode()
        try:
            payload = json.loads(body)
        except (json.JSONDecodeError, UnicodeDecodeError):
            payload = body
        return {"error": payload, "status_code": error.code}
    except (OSError, ValueError) as error:
        return {"error": str(error)}


def evaluate(question: dict, response: dict) -> dict:
    result = {
        "id": question["id"],
        "category": question["category"],
        "question": question["question"],
        "pass": True,
        "failures": [],
        "tools_used": [],
        "reply_preview": "",
    }
    is_rejected = response.get("status_code") == 400
    reply = response.get("reply", "") if isinstance(response.get("reply", ""), str) else ""
    tools_used = response.get("tools_used", [])
    if not isinstance(tools_used, list):
        tools_used = []

    if question["should_reject"]:
        result["reply_preview"] = reply[:100]
        if not is_rejected and (tools_used or "only assist with Microsoft 365" not in reply):
            result["pass"] = False
            result["failures"].append("Expected rejection but got normal response")
        return result

    result["tools_used"] = tools_used
    result["reply_preview"] = reply[:150]
    if is_rejected or "error" in response:
        result["pass"] = False
        result["failures"].append(f"Unexpected error: {str(response.get('error', ''))[:100]}")
        return result
    if not tools_used:
        result["pass"] = False
        result["failures"].append("No tools called — agent answered without data")
    expected = question.get("expected_tools", [])
    if expected and not any(tool in tools_used for tool in expected):
        result["failures"].append(f"Expected one of {expected} but got {tools_used}")
    rule_ids = RULE_ID_PATTERN.findall(reply)
    if rule_ids:
        result["pass"] = False
        result["failures"].append(f"Raw rule IDs found in reply: {rule_ids[:3]}")
    uuids = UUID_PATTERN.findall(reply)
    if uuids:
        result["pass"] = False
        result["failures"].append(f"Raw UUIDs found in reply: {uuids[:2]}")
    if len(reply) < 20:
        result["pass"] = False
        result["failures"].append("Reply too short — likely an error")
    return result


def main() -> int:
    print("=" * 60)
    print("AGT-DEV01 — M365 Agent Auto-Tester")
    print("=" * 60)
    with QUESTIONS_FILE.open(encoding="utf-8") as questions_file:
        data = json.load(questions_file)
    questions = data["questions"]
    print(f"Loaded {len(questions)} questions from {QUESTIONS_FILE}\n")
    results = []
    for index, question in enumerate(questions):
        print(f"[{index + 1}/{len(questions)}] {question['id']} — {question['question'][:60]}")
        result = evaluate(question, call_agent(question["question"]))
        results.append(result)
        if result["pass"]:
            print(f"  PASS | tools: {result['tools_used']}")
        else:
            print(f"  FAIL | {result['failures']}")
        if result["reply_preview"]:
            print(f"  → {result['reply_preview'][:100]}")
        if index < len(questions) - 1:
            time.sleep(DELAY_SECONDS)
    passed = sum(result["pass"] for result in results)
    failed = len(results) - passed
    score = (passed / len(results) * 100) if results else 0
    print("\n" + "=" * 60)
    print(f"RESULTS: {passed} passed, {failed} failed / {len(results)} total")
    print(f"SCORE: {score:.1f}%")
    print(f"STATUS: {'EXCELLENT' if score >= 90 else 'ACCEPTABLE' if score >= 75 else 'NEEDS ATTENTION'}")
    print("=" * 60)
    output = Path(__file__).parent / "agent_test_results.json"
    with output.open("w", encoding="utf-8") as results_file:
        json.dump({"score": score, "passed": passed, "failed": failed, "total": len(results), "results": results}, results_file, indent=2)
    print(f"\nDetailed results saved to: {output}")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
