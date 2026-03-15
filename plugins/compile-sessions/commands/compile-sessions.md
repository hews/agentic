Compile Claude Code session transcripts for the current project into readable markdown files.

## What this does

Runs `extract-transcripts.py` against the Claude Code session transcripts for the current project, outputting clean markdown files (one per session) plus an `INDEX.md`.

- Strips tool calls, thinking blocks, and system metadata — only user messages and assistant text responses are kept
- Skips already-compiled sessions (progressive / idempotent)
- Splits large sessions (>300KB) into numbered parts
- Numbers files chronologically (e.g. `01-slug-date-to-date.md`)

## Steps

1. Determine the transcripts directory for the current project. Claude Code stores transcripts at:
   `~/.claude/projects/<encoded-path>/`
   where `<encoded-path>` is the project's absolute path with `/` replaced by `-` (e.g. `/Users/hews/code/hews/myproject` → `-Users-hews-code-hews-myproject`).

2. Determine the output directory. Default to `./history/claude-sessions/` relative to the project root, unless the user specifies otherwise via `$ARGUMENTS`.

3. Run the script:
   ```
   python3 ~/.claude/plugins/compile-sessions/scripts/extract-transcripts.py \
     <transcripts-dir> \
     <output-dir>
   ```

4. Report how many sessions were written and the path to `INDEX.md`.

## Arguments

Optional: `$ARGUMENTS` may specify a custom output directory. If blank, use `./history/claude-sessions/`.
