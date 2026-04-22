"""Parse LLM response into a dict of {relative_path: file_content}."""
from __future__ import annotations

import re

# Matches:  FILE: path/to/file.tf\n<content>\n---
_FILE_BLOCK = re.compile(
    r"FILE:\s*(?P<path>[^\n]+)\n(?P<content>.*?)(?=\nFILE:|\Z)",
    re.DOTALL,
)

# Strip trailing separator produced by the prompt format
_SEPARATOR = re.compile(r"\n---\s*$")


def parse_response(llm_text: str) -> dict[str, str]:
    """Return ``{relative_path: content}`` for every FILE block in *llm_text*.

    If the response contains no FILE blocks (e.g. the model wrapped everything
    in a single code fence) a best-effort fallback writes everything to
    ``main.tf``.
    """
    files: dict[str, str] = {}

    for match in _FILE_BLOCK.finditer(llm_text):
        path = match.group("path").strip()
        content = _SEPARATOR.sub("", match.group("content")).strip()
        if path and content:
            files[path] = content + "\n"

    if not files:
        # Fallback: strip any surrounding code fences and write as main.tf
        cleaned = re.sub(r"^```[a-z]*\n?", "", llm_text.strip(), flags=re.IGNORECASE)
        cleaned = re.sub(r"\n?```$", "", cleaned)
        files["main.tf"] = cleaned.strip() + "\n"

    return files
