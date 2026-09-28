from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def release_watch_summary(payload: dict[str, Any]) -> dict[str, object]:
    probe = payload.get("second_post_2025_probe", {})
    complete = sorted(str(value) for value in probe.get("complete_2025_entities", []))
    missing = sorted(str(value) for value in probe.get("missing_2025_entities", []))
    total = len(complete) + len(missing)
    all_complete = bool(probe.get("all_entities_have_2025", False))

    if all_complete and missing:
        raise ValueError("APCR 2025 probe cannot be complete with missing entities")
    if all_complete and total == 0:
        raise ValueError("APCR 2025 complete gate requires a non-empty universe")

    return {
        "complete_count": len(complete),
        "total_count": total,
        "complete_entities": complete,
        "missing_entities": missing,
        "all_entities_have_2025": all_complete,
        "gate_status": "OPEN_FOR_D22C7B_REVIEW" if all_complete else "WAITING_FOR_BLS",
    }


def render_markdown(summary: dict[str, object]) -> str:
    missing = summary["missing_entities"]
    missing_text = ", ".join(missing) if missing else "none"
    return (
        "## APCR 2025 second-post release watch\n\n"
        f"- Gate: **{summary['gate_status']}**\n"
        f"- Complete: **{summary['complete_count']}/{summary['total_count']}** frozen entities\n"
        f"- Missing 2025 A01: {missing_text}\n"
        "- Action: D22C7b remains a separate reviewed change; this watch never promotes A automatically.\n"
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Summarize APCR 2025 release gate")
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--summary-output", type=Path)
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    payload = json.loads(args.input.read_text(encoding="utf-8"))
    summary = release_watch_summary(payload)
    markdown = render_markdown(summary)

    print(
        "apcr-2025-watch "
        f"complete={summary['complete_count']}/{summary['total_count']} "
        f"gate={summary['gate_status']}",
        flush=True,
    )
    if summary["all_entities_have_2025"]:
        print(
            "::notice title=APCR 2025 gate open::"
            "All frozen APCR sectors now have 2025 A01. "
            "D22C7b can be reviewed.",
            flush=True,
        )

    if args.summary_output is not None:
        with args.summary_output.open("a", encoding="utf-8") as handle:
            handle.write(markdown)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
