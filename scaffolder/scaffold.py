"""CLI entrypoint for tf-scaffold-ai."""
from __future__ import annotations

import argparse
import os
import sys

from scaffolder.validator import validate
from scaffolder.prompt import build_messages
from scaffolder.llm import call_llm
from scaffolder.parser import parse_response
from scaffolder.writer import write_scaffold, format_summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Generate a Terraform scaffold from a natural-language description"
    )
    parser.add_argument(
        "--description",
        required=True,
        help="Plain-language description of the desired cloud architecture",
    )
    parser.add_argument(
        "--cloud",
        default="aws",
        choices=["aws", "azure", "gcp", "multi"],
        help="Target cloud provider (default: aws)",
    )
    parser.add_argument(
        "--output",
        default="out/scaffold",
        help="Directory to write the generated scaffold (default: out/scaffold)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate and build the prompt but do not call the LLM or write files",
    )
    args = parser.parse_args(argv)

    # ---- Validate input ----
    result = validate(args.description, args.cloud)

    for warning in result.warnings:
        print(f"WARNING: {warning}", file=sys.stderr)

    if not result.ok:
        for error in result.errors:
            print(f"ERROR: {error}", file=sys.stderr)
        print(
            "\nPlease revise your description and try again.",
            file=sys.stderr,
        )
        return 1

    if args.dry_run:
        print("Validation passed. Dry-run — LLM not called.")
        return 0

    # ---- Call LLM ----
    messages = build_messages(args.description, args.cloud)
    print(f"Generating scaffold for {args.cloud}…", file=sys.stderr)
    llm_text = call_llm(messages)

    # ---- Parse + write ----
    files = parse_response(llm_text)
    written = write_scaffold(files, args.output)

    print(f"Scaffold written to {args.output} ({len(written)} files).", file=sys.stderr)

    summary = format_summary(files, args.cloud, args.output)

    # Post to GitHub Actions workflow summary if available
    step_summary = os.environ.get("GITHUB_STEP_SUMMARY", "")
    if step_summary:
        with open(step_summary, "a") as f:
            f.write(summary + "\n")
    else:
        print(summary)

    return 0


if __name__ == "__main__":
    sys.exit(main())
