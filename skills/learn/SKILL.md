---
name: learn
description: Learn from a coding session, current Git changes, specified code, or a programming topic with evidence-based explanations and interactive recall; review saved gaps and concepts. Use for natural-language learning requests as well as explicit learn commands. For current Git changes, run the bounded helper before any repository inspection. Do not interrupt ordinary coding work.
---

# Learn from coding

Help the user understand a selected piece of work through a concise explanation, active recall, and a small project-local record. Match the user's language. Use the coding agent's existing tools; do not start a separate model client or service.

## Choose the source

The user may choose `session`, `diff`, `file <path>`, `topic <subject>`, or `review`; natural language is fine. If the source is unclear, ask them to choose. Default to a short explanation followed by a quiz; honor explanation-only and quiz-first requests. `review` uses saved records.

For a `diff` request, immediately run the bounded helper below as the first workspace command. Do not run `git status`, `git diff`, or read project files first. Then load [references/diff.md](references/diff.md) and verify only the returned sample. For `review`, read [references/review.md](references/review.md) before reading project notes. These are the only mode references; `session`, `file`, and `topic` need no reference lookup.

The first project command for `diff` must be `python3 <skill>/scripts/context.py diff-bundle`; it returns the summary and bounded sample together. For `review`, first run `python3 <skill>/scripts/context.py review-index --limit 3`; it returns titles only. Do not first read repository diffs or learning notes. If the selected helper is missing or exits unsuccessfully, do not search other skill installations; load that mode's reference and follow its bounded fallback. Do not reread the skill files from disk; the skill is already loaded. Resolve the script beside this skill; project entry paths are `.agents/skills/learn/scripts/context.py` in Codex and `.claude/skills/learn/scripts/context.py` in Claude Code.

For other sources, inspect only the context needed. `session` uses recent relevant conversation to locate work, then verifies it against current code. `file` reads the named file first, then searches only for the called symbols in likely source and test directories; avoid repository-wide searches. `topic` prefers a project example; if none exists, label the explanation as general knowledge. Do not scan unrelated files, generated output, or old history.

## Teach and check understanding

- Explain no more than 2–3 useful points: what the code does, why the mechanism works, and a consequence or tradeoff. Keep it short unless asked for depth.
- Ground each important project claim in a current relative `file:line` pointing at the relevant condition, call, or assertion. Distinguish code facts, general knowledge, and inference. Do not guess author intent.
- Ask 1–3 questions per round, one at a time. Prefer prediction, application, debugging, or design tradeoffs. Decide whether to continue only after grading the current answer. Do not show the answer or a targeted hint first.
- Grade against inspected code or a reliable source, accepting equivalent wording. Check the main result and reasoning; mark answers correct, partial, wrong, or uncertain and explain with evidence. If challenged, recheck and correct the grade when needed.
- In quiz-first mode, ask before teaching. In explanation-only mode, do not ask a question. After the last answer, give a brief takeaway and any remaining gap.
- Treat “stop”, “结束学习”, “退出学习”, or a new unrelated task as the end of this round. Do not grade or save an unanswered question.

## Keep a small learning record

Use `.learning/notes.md`; never replace existing notes with a template. Before a write, check this exact path and inspect only the section or entry being changed. Use a path existence check, section headers, a topic search, or `review-entry`; do not `cat` the whole file. After a successful write, do not read the file back; rely on the write result. In a Git repository, ensure `.learning/` is ignored without duplicating the rule. Do not change source code as part of learning.

Keep `## Gaps` and `## Concepts`. Write one concise record per bullet with a stable ID, date, topic, question or takeaway, corrected answer if relevant, evidence (`file:line` and commit when available, or documentation), and last review date. Use unchecked boxes for active gaps and checked boxes for understood or obsolete gaps; label obsolete gaps `STALE`. Preserve unrelated entries. Update a duplicate in place. Save wrong or materially incomplete answers as gaps and at most 2–3 important, nonduplicate concepts per round. Do not save full lessons or unanswered questions. Briefly tell the user what was saved.

Do not imply background monitoring. A large active diff may merit one brief suggestion to learn from that change; several open gaps may merit one brief suggestion to review older learning. Manual `review` is always available.
