#!/usr/bin/env python3
"""Extract Claude Code session transcripts into readable markdown.

Usage:
    extract-transcripts.py <transcripts-dir> <output-dir>

Arguments:
    transcripts-dir  Path to the .jsonl transcript files
                     (e.g. ~/.claude/projects/-Users-hews-code-hews-myproject/)
    output-dir       Where to write markdown files
                     (e.g. ./history/claude-sessions/)

Features:
    - Extracts user messages and assistant text responses
    - Strips thinking blocks, tool calls, and system metadata
    - One file per session, numbered chronologically
    - Splits large files (>300KB) into parts
    - Progressive: skips sessions already compiled
    - Generates INDEX.md with links to all sessions
"""

import json
import os
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

ET = timezone(timedelta(hours=-4))  # EDT
MAX_FILE_BYTES = 300_000  # ~300KB threshold for splitting


def parse_session(jsonl_path: Path) -> Optional[dict]:
    """Parse a .jsonl transcript file into a structured session dict."""
    messages = []
    slug = None
    session_id = jsonl_path.stem
    timestamps = []

    with open(jsonl_path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue

            # Extract slug
            if not slug and obj.get("slug"):
                slug = obj["slug"]

            # Extract timestamps from any message with a timestamp field
            ts = obj.get("timestamp")
            if ts:
                timestamps.append(ts)

            # User messages
            if obj.get("type") == "user":
                msg = obj.get("message", {})
                content = msg.get("content", "")
                if isinstance(content, list):
                    # Extract text blocks only
                    parts = []
                    for block in content:
                        if isinstance(block, dict) and block.get("type") == "text":
                            parts.append(block["text"])
                        elif isinstance(block, str):
                            parts.append(block)
                    content = "\n".join(parts)
                if isinstance(content, str):
                    content = content.strip()
                    # Strip all XML-style system/meta tags
                    content = re.sub(
                        r"<(?:system-reminder|local-command-caveat|local-command-stdout|"
                        r"ide_opened_file|command-name|command-message|command-args|"
                        r"new-diagnostics|available-deferred-tools)>.*?</(?:system-reminder|"
                        r"local-command-caveat|local-command-stdout|ide_opened_file|"
                        r"command-name|command-message|command-args|new-diagnostics|"
                        r"available-deferred-tools)>\s*",
                        "",
                        content,
                        flags=re.DOTALL,
                    ).strip()
                    # Strip ANSI escape codes
                    content = re.sub(r"\x1b\[[0-9;]*m", "", content)
                    if content:
                        messages.append({"role": "user", "text": content, "timestamp": ts})

            # Assistant messages
            msg = obj.get("message", {})
            if msg.get("role") == "assistant" and obj.get("type") != "user":
                text_parts = []
                for block in msg.get("content", []):
                    if isinstance(block, dict) and block.get("type") == "text":
                        text = block.get("text", "").strip()
                        if text:
                            text_parts.append(text)
                if text_parts:
                    combined = "\n\n".join(text_parts)
                    messages.append({"role": "assistant", "text": combined, "timestamp": ts})

    if not messages:
        return None

    # Determine time range
    if timestamps:
        ts_sorted = sorted(timestamps)
        start_ts = ts_sorted[0]
        end_ts = ts_sorted[-1]
    else:
        start_ts = end_ts = None

    return {
        "session_id": session_id,
        "slug": slug or session_id[:12],
        "start_ts": start_ts,
        "end_ts": end_ts,
        "messages": messages,
        "source_path": str(jsonl_path),
    }


def format_ts_for_filename(iso_ts: str) -> str:
    """Convert ISO timestamp to YYYY-MM-DD-HHmm format in ET."""
    if not iso_ts:
        return "unknown"
    try:
        dt = datetime.fromisoformat(iso_ts.replace("Z", "+00:00")).astimezone(ET)
        return dt.strftime("%Y-%m-%d-%H%M")
    except (ValueError, TypeError):
        return "unknown"


def format_ts_display(iso_ts: str) -> str:
    """Convert ISO timestamp to human-readable ET string."""
    if not iso_ts:
        return "—"
    try:
        dt = datetime.fromisoformat(iso_ts.replace("Z", "+00:00")).astimezone(ET)
        return dt.strftime("%Y-%m-%d %I:%M %p ET")
    except (ValueError, TypeError):
        return "—"


def render_session_markdown(session: dict, part_num: int = 0, total_parts: int = 1) -> str:
    """Render a session (or part of one) as markdown."""
    lines = []

    slug_title = session["slug"].replace("-", " ").title()
    title = f"# {slug_title}"
    if total_parts > 1:
        title += f" (Part {part_num})"
    lines.append(title)
    lines.append("")
    lines.append(f"- **Session ID:** `{session['session_id']}`")
    lines.append(f"- **Started:** {format_ts_display(session['start_ts'])}")
    lines.append(f"- **Ended:** {format_ts_display(session['end_ts'])}")
    if total_parts > 1:
        lines.append(f"- **Part:** {part_num} of {total_parts}")
    lines.append("")
    lines.append("---")
    lines.append("")

    for msg in session["messages"]:
        if msg["role"] == "user":
            lines.append(f"**User:** {msg['text']}")
        else:
            lines.append(f"**Claude:** {msg['text']}")
        lines.append("")

    return "\n".join(lines)


def split_session(session: dict) -> list:
    """Split a session into parts if the rendered markdown would exceed MAX_FILE_BYTES."""
    full_md = render_session_markdown(session)
    if len(full_md.encode("utf-8")) <= MAX_FILE_BYTES:
        return [session]

    # Split by message count, aiming for roughly equal parts
    total_size = len(full_md.encode("utf-8"))
    num_parts = (total_size // MAX_FILE_BYTES) + 1
    msgs = session["messages"]
    chunk_size = max(1, len(msgs) // num_parts)

    parts = []
    for i in range(0, len(msgs), chunk_size):
        chunk = msgs[i : i + chunk_size]
        part = {**session, "messages": chunk}
        parts.append(part)

    return parts


def get_compiled_session_ids(output_dir: Path) -> set:
    """Read INDEX.md to find already-compiled session IDs."""
    index_path = output_dir / "INDEX.md"
    compiled = set()
    if index_path.exists():
        content = index_path.read_text()
        # Extract session IDs from index entries (they're in backticks)
        for match in re.finditer(r"`([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})`", content):
            compiled.add(match.group(1))
    return compiled


def main():
    if len(sys.argv) != 3:
        print(f"Usage: {sys.argv[0]} <transcripts-dir> <output-dir>", file=sys.stderr)
        sys.exit(1)

    transcripts_dir = Path(sys.argv[1])
    output_dir = Path(sys.argv[2])

    if not transcripts_dir.is_dir():
        print(f"Error: {transcripts_dir} is not a directory", file=sys.stderr)
        sys.exit(1)

    output_dir.mkdir(parents=True, exist_ok=True)

    # Find already-compiled sessions
    compiled_ids = get_compiled_session_ids(output_dir)

    # Parse all .jsonl files
    jsonl_files = sorted(transcripts_dir.glob("*.jsonl"))
    if not jsonl_files:
        print("No .jsonl files found.", file=sys.stderr)
        sys.exit(0)

    sessions = []
    skipped = 0
    for f in jsonl_files:
        session_id = f.stem
        if session_id in compiled_ids:
            skipped += 1
            continue
        session = parse_session(f)
        if session:
            sessions.append(session)

    if skipped:
        print(f"   Skipped {skipped} already-compiled sessions.")

    if not sessions:
        print("   No new sessions to compile.")
        sys.exit(0)

    # Sort by start timestamp
    sessions.sort(key=lambda s: s["start_ts"] or "")

    # Determine starting number from existing files
    existing_files = sorted(output_dir.glob("[0-9][0-9]-*.md"))
    if existing_files:
        last_num = int(existing_files[-1].name[:2])
        start_num = last_num + 1
    else:
        start_num = 1

    # Generate files
    written_files = []
    num = start_num

    for session in sessions:
        parts = split_session(session)
        total_parts = len(parts)

        for part_idx, part in enumerate(parts, 1):
            start_fmt = format_ts_for_filename(session["start_ts"])
            end_fmt = format_ts_for_filename(session["end_ts"])
            slug = session["slug"]

            filename = f"{num:02d}-{slug}-{start_fmt}-to-{end_fmt}"
            if total_parts > 1:
                filename += f"-part{part_idx}"
            filename += ".md"

            md = render_session_markdown(part, part_num=part_idx, total_parts=total_parts)
            filepath = output_dir / filename
            filepath.write_text(md)
            written_files.append((filepath.name, session))
            print(f"   Wrote: {filename}")

        num += 1

    # Generate / update INDEX.md
    index_path = output_dir / "INDEX.md"
    all_files = sorted(output_dir.glob("[0-9][0-9]-*.md"))

    index_lines = ["# Claude Code Session Transcripts", ""]

    # Re-read all sessions for index (including previously compiled)
    for f in all_files:
        # Extract info from first few lines
        content = f.read_text()
        title_match = re.search(r"^# (.+)$", content, re.MULTILINE)
        title = title_match.group(1) if title_match else f.stem
        sid_match = re.search(r"\*\*Session ID:\*\* `(.+?)`", content)
        sid = sid_match.group(1) if sid_match else "?"
        started_match = re.search(r"\*\*Started:\*\* (.+)$", content, re.MULTILINE)
        started = started_match.group(1) if started_match else "?"

        index_lines.append(f"1. [{title}]({f.name}) — {started} — `{sid}`")

    index_lines.append("")
    index_path.write_text("\n".join(index_lines))
    print(f"   Updated: INDEX.md ({len(all_files)} sessions)")


if __name__ == "__main__":
    main()
