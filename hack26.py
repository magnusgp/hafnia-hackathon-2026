"""Hafnia Hackathon 2026: small, dependency-free gateway research client.

Runs ONLY on the hackathon Windows VM. Never prints or persists credentials.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import re
import sys
import time

# Re-export helpers/constants so existing v0.1 callers continue to work.
from scene_contracts.gateway import (
    BASE, DECISIONS, Gateway, GatewayError, extract_decision,
    summary_response_text, format_utc, video_uri,
)

PROMPT_TITLE = "H26 Incident Review v0.1"
EVENT_NAME = "H26 Visually Observed Damage"
RULE_NAME = "H26 Incident Review Positive"


def command_inspect(client: Gateway, args):
    print("System information:")
    print(json.dumps(client.request("GET", "/api/System/Information"), indent=2))
    if args.system_only:
        return
    client.authenticate()
    print("\nModels:")
    print(json.dumps(client.request("GET", "/api/Models"), indent=2))
    print("\nAnalytics action options (inspect event names):")
    print(json.dumps(client.request("GET", "/api/Rules/Actions/TriggerAnalyticsEvent/Options"), indent=2))


def command_install_prompt(client: Gateway, args):
    client.authenticate()
    prompt_text = Path(args.file).read_text(encoding="utf-8").strip()
    existing = client.exact_item("Prompts", "Title", args.title)
    if existing:
        if existing.get("Text", "").strip() != prompt_text:
            raise GatewayError("Prompt title already exists with DIFFERENT text; no changes made")
        print("Existing prompt matches:", existing["Id"])
    elif not args.apply:
        print(f"DRY RUN: would create saved prompt {args.title!r} ({len(prompt_text)} chars). Add --apply to create it.")
    else:
        created = client.request("POST", "/api/Prompts", {"Title": args.title, "Text": prompt_text})
        print("Created prompt:", created.get("Id", "(id unavailable)"))


def command_install_rule(client: Gateway, args):
    client.authenticate()
    prompt = client.exact_item("Prompts", "Title", args.title)
    if prompt is None:
        raise GatewayError(f"Saved prompt {args.title!r} missing: install it first")
    existing = client.exact_item("Rules", "Name", args.rule_name)
    rule = {
        "Name": args.rule_name,
        "Description": "Hackathon 2026 demo only. Positive visual evidence; operator review required.",
        "PromptId": prompt["Id"],
        "Triggers": [{
            "TriggerText": "H26_DAMAGE_EVENT",
            "RuleActionId": "TriggerAnalyticsEvent",
            "RuleActionData": args.event_name,
        }],
    }
    if existing:
        print("Rule already exists. Compare manually; no changes made:", existing.get("Id"))
    elif not args.apply:
        print("DRY RUN (check that event name exists in XProtect before applying):")
        print(json.dumps(rule, indent=2))
    else:
        created = client.request("POST", "/api/Rules", rule)
        print("Created rule:", created.get("Id", "(id unavailable)"))


def command_run(client: Gateway, args):
    client.authenticate()
    prompt = client.exact_item("Prompts", "Title", args.title)
    if prompt is None:
        raise GatewayError(f"No saved prompt titled {args.title!r}; run install-prompt first")
    text = prompt.get("Text")
    if not isinstance(text, str) or not text.strip():
        raise GatewayError("Saved prompt has no text")
    if args.start and args.end:
        start = datetime.fromisoformat(args.start.replace("Z", "+00:00"))
        end = datetime.fromisoformat(args.end.replace("Z", "+00:00"))
        if start.tzinfo is None or end.tzinfo is None:
            raise GatewayError("Start and end must be timezone-aware UTC timestamps")
    elif args.start or args.end:
        raise GatewayError("Specify both --start and --end or neither")
    else:
        now = datetime.now(timezone.utc)
        end = now - timedelta(seconds=args.lag)
        start = end - timedelta(seconds=args.seconds)
    uri = video_uri(args.camera_id, start, end)
    print("Camera:", args.camera_id)
    print("Clip UTC:", format_utc(start), "to", format_utc(end))
    print("Saved prompt:", args.title)
    print("Exactly 1 VLM request will be submitted; do not automatically retry failures.")
    if not args.apply:
        print("DRY RUN: add --apply to submit a real inference request")
        return
    item = client.request("POST", "/api/Summaries", {
        "Prompt": text, "PromptId": prompt["Id"], "VideoUris": [uri]
    })
    request_id = item.get("Id")
    if not request_id:
        raise GatewayError("Submission returned no summary ID")
    print("Request ID:", request_id)
    deadline = time.monotonic() + args.max_wait
    while item.get("Progress") not in {"Completed", "Failed"} and time.monotonic() < deadline:
        time.sleep(3)
        item = client.request("GET", f"/api/Summaries/{request_id}")
        print("Progress:", item.get("Progress"))
    output = Path(args.output_dir)
    output.mkdir(exist_ok=True, parents=True)
    filename = re.sub(r"[^a-zA-Z0-9_-]", "_", request_id) + ".json"
    target = output / filename
    target.write_text(json.dumps(item, indent=2, ensure_ascii=False), encoding="utf-8")
    print("Saved raw result:", target)
    if item.get("Progress") == "Completed":
        response_text = summary_response_text(item)
        print("\nResponse:\n" + response_text)
        print("\nParsed decision:", extract_decision(response_text) or "UNPARSEABLE (do not act)")
    elif item.get("Progress") == "Failed":
        print("Failure stage / reason:", item.get("LastError", "Not provided"))
    else:
        print("Result still running; inspect later using the gateway's History")


def make_parser():
    parser = argparse.ArgumentParser(description="Hafnia Hackathon 2026 gateway proof-of-integration")
    subs = parser.add_subparsers(dest="command", required=True)
    insp = subs.add_parser("inspect", help="Gateway quota, models, available rule actions")
    insp.add_argument("--system-only", action="store_true", help="Read health/quota without logging in")
    install = subs.add_parser("install-prompt", help="Install a named prompt idempotently")
    install.add_argument("--title", default=PROMPT_TITLE)
    install.add_argument("--file", default="prompts/incident_review.txt")
    install.add_argument("--apply", action="store_true", help="Allow configuration write")
    rule = subs.add_parser("install-rule", help="Create a Hafnia keyword-to-analytics-event rule")
    rule.add_argument("--title", default=PROMPT_TITLE)
    rule.add_argument("--rule-name", default=RULE_NAME)
    rule.add_argument("--event-name", default=EVENT_NAME)
    rule.add_argument("--apply", action="store_true", help="Allow configuration write")
    run = subs.add_parser("run", help="Submit a clip to Hafnia VLM")
    run.add_argument("--camera-id", required=True, help="GUID from Get-VmsCamera, NOT the camera name")
    run.add_argument("--title", default=PROMPT_TITLE)
    run.add_argument("--start", help="ISO UTC start (Z), optional")
    run.add_argument("--end", help="ISO UTC end (Z), optional")
    run.add_argument("--seconds", type=int, default=15)
    run.add_argument("--lag", type=int, default=120, help="Seconds before current UTC time")
    run.add_argument("--max-wait", type=int, default=600)
    run.add_argument("--output-dir", default="runs")
    run.add_argument("--apply", action="store_true", help="Spend 1 completed VLM request")
    return parser


def main():
    parser = make_parser()
    args = parser.parse_args()
    if getattr(args, "seconds", 15) <= 0 or getattr(args, "lag", 120) <= 0:
        parser.error("--seconds and --lag must be positive")
    if getattr(args, "max_wait", 600) <= 0:
        parser.error("--max-wait must be positive")
    client = Gateway()
    try:
        {
            "inspect": command_inspect,
            "install-prompt": command_install_prompt,
            "install-rule": command_install_rule,
            "run": command_run,
        }[args.command](client, args)
    except (GatewayError, ValueError, OSError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
