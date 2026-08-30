#!/usr/bin/env python3
"""intent.md CLI — create, validate, decide, publish, report.

Backs `/deep intent`. All artifact logic lives in scripts/lib/intent.py and all
git logic in scripts/lib/vcs.py; this is argument parsing and JSON output.

Subcommands:
  new       --title T [--author A] [--source human|agent] [--out DIR]
  validate  <path>
  decide    <path> --status accepted|rejected|superseded --by WHO [--reason R]
  publish   <path> --repo DIR [--into docs/intent] [--commit]
  report    <dir> [--repo DIR]

Exit codes:
  0 — ok
  1 — validation failed / decision refused
  2 — usage or I/O error
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lib import vcs
from lib.intent import (
    Intent,
    IntentError,
    default_template,
    new_intent_id,
    parse,
    render,
    set_decision,
    utc_now,
    validate,
)

DEFAULT_PUBLISH_DIR = "docs/intent"
MIN_SAMPLES_FOR_RATE = 10


def _fail(message: str, code: int = 2) -> None:
    print(json.dumps({"ok": False, "error": message}, indent=2))
    raise SystemExit(code)


def _read(path: Path) -> str:
    try:
        return path.read_text()
    except OSError as exc:
        _fail(str(exc))
        raise  # unreachable, keeps type checkers happy


def cmd_new(args: argparse.Namespace) -> int:
    created = utc_now()
    author = vcs.resolve_author(Path.cwd(), explicit=args.author)
    text = default_template(
        title=args.title, author=author, source=args.source, created=created
    )
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{new_intent_id(args.title, created)}.md"
    if path.exists() and not args.force:
        _fail(f"{path} already exists; pass --force to overwrite", 1)
    path.write_text(text)
    print(
        json.dumps(
            {
                "ok": True,
                "path": str(path),
                "id": new_intent_id(args.title, created),
                "author": author,
                "status": "draft",
                "next": "Fill every section, grill it, then set status: proposed",
            },
            indent=2,
        )
    )
    return 0


def cmd_validate(args: argparse.Namespace) -> int:
    result = validate(_read(Path(args.path)))
    print(json.dumps({"path": args.path, **result.to_dict()}, indent=2))
    return 0 if result.passed else 1


def cmd_decide(args: argparse.Namespace) -> int:
    path = Path(args.path)
    try:
        intent = parse(_read(path))
        decided = set_decision(
            intent, status=args.status, decided_by=args.by, reason=args.reason or ""
        )
    except IntentError as exc:
        _fail(str(exc), 1)
        raise
    path.write_text(render(decided))
    print(
        json.dumps(
            {
                "ok": True,
                "id": decided.id,
                "status": decided.status,
                "decided_by": decided.decided_by,
                "decided_at": decided.decided_at,
            },
            indent=2,
        )
    )
    return 0


def cmd_publish(args: argparse.Namespace) -> int:
    source = Path(args.path)
    text = _read(source)

    result = validate(text)
    if not result.passed:
        _fail(f"refusing to publish an invalid intent: {'; '.join(result.errors)}", 1)

    repo = Path(args.repo)
    if not vcs.is_repo(repo):
        _fail(f"{repo} is not a git work tree")

    target_dir = repo / (args.into or DEFAULT_PUBLISH_DIR)
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / source.name
    target.write_text(text)

    payload: dict = {"ok": True, "published": str(target), "committed": False}

    if args.commit:
        intent = parse(text)
        message = f"docs(intent): {intent.title}\n\nIntent {intent.id} ({intent.status}), raised by {intent.author}."
        commit = vcs.commit_file(target, message, repo)
        payload["committed"] = commit.ok
        if not commit.ok:
            # The file is on disk either way; a failed commit is not data loss.
            payload["commit_error"] = commit.error

    print(json.dumps(payload, indent=2))
    return 0


def _load_intents(directory: Path) -> list[Intent]:
    intents: list[Intent] = []
    for path in sorted(directory.glob("*.md")):
        try:
            intents.append(parse(path.read_text()))
        except (OSError, IntentError):
            continue
    return intents


def cmd_report(args: argparse.Namespace) -> int:
    directory = Path(args.dir)
    if not directory.is_dir():
        _fail(f"{directory} is not a directory")

    intents = _load_intents(directory)
    by_status: dict[str, int] = {}
    for intent in intents:
        by_status[intent.status] = by_status.get(intent.status, 0) + 1

    decided = by_status.get("accepted", 0) + by_status.get("rejected", 0)
    payload: dict = {
        "total": len(intents),
        "by_status": by_status,
        "decided": decided,
    }

    # A survival rate over four intents is noise wearing a percentage sign.
    if decided >= MIN_SAMPLES_FOR_RATE:
        payload["survival_rate"] = round(by_status.get("accepted", 0) / decided, 3)
    else:
        payload["survival_rate"] = None
        payload["survival_rate_note"] = (
            f"withheld: {decided} decided intents, need {MIN_SAMPLES_FOR_RATE}"
        )

    if args.repo:
        repo = Path(args.repo)
        lags = []
        for intent in intents:
            published = repo / (args.into or DEFAULT_PUBLISH_DIR) / f"{intent.id}.md"
            committed = vcs.file_commit_time(published, repo)
            if committed:
                lags.append({"id": intent.id, "created": intent.created, "committed": committed})
        payload["capture_to_commit"] = lags

    print(json.dumps(payload, indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    p_new = sub.add_parser("new")
    p_new.add_argument("--title", required=True)
    p_new.add_argument("--author", default=None)
    p_new.add_argument("--source", default="human", choices=["human", "agent"])
    p_new.add_argument("--out", default=".")
    p_new.add_argument("--force", action="store_true")
    p_new.set_defaults(func=cmd_new)

    p_validate = sub.add_parser("validate")
    p_validate.add_argument("path")
    p_validate.set_defaults(func=cmd_validate)

    p_decide = sub.add_parser("decide")
    p_decide.add_argument("path")
    p_decide.add_argument(
        "--status", required=True, choices=["accepted", "rejected", "superseded"]
    )
    p_decide.add_argument("--by", required=True, help="who decided; attestation, not authentication")
    p_decide.add_argument("--reason", default="")
    p_decide.set_defaults(func=cmd_decide)

    p_publish = sub.add_parser("publish")
    p_publish.add_argument("path")
    p_publish.add_argument("--repo", required=True)
    p_publish.add_argument("--into", default=DEFAULT_PUBLISH_DIR)
    p_publish.add_argument("--commit", action="store_true")
    p_publish.set_defaults(func=cmd_publish)

    p_report = sub.add_parser("report")
    p_report.add_argument("dir")
    p_report.add_argument("--repo", default=None)
    p_report.add_argument("--into", default=DEFAULT_PUBLISH_DIR)
    p_report.set_defaults(func=cmd_report)

    return parser


def main() -> int:
    args = build_parser().parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
