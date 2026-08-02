---
name: voice-agent-flow
description: |
  Generate a structured flow JSON for the terminal voice-agent — a tutoring
  session, an ELI5 explainer, an English-practice conversation, or a mock
  interview. Use when the user wants to create a new lesson/tutor/practice
  scenario, a set of questions on a topic, or a "flow" for a voice bot. Produces
  a valid {mode}_{topic}_{difficulty}.json that build_prompt.py turns into the
  agent's system prompt.
license: MIT
metadata:
  version: "0.1.0"
---

# Flow generator

Create a **flow JSON** that drives the voice-agent (see the `voice-agent`
skill). A flow is a structured scenario: an opening line, an ordered list of
questions with follow-ups and timing, and a wrap-up. `build_prompt.py` reads it
and assembles the agent's system prompt.

## Steps

1. **Settle the axes** with the user (ask only what's missing):
   - **mode** — the interaction style (see the table below).
   - **topic** — subject, as a short slug (e.g. `rag`, `pandas-basics`,
     `biological-neurons`).
   - **difficulty** — `easy` / `medium` / `hard`.
   - **language** — ISO code for the session; **default `en`**. Only ask if the
     user wants something other than English (`uk`, `es`, `fr`, …).
2. **Read `reference/schema.md`** for the full field spec and per-mode rules,
   and `reference/example.json` for a filled-in example.
3. **Generate** 4–8 questions appropriate to the topic and difficulty. Each
   question needs `follow_ups`, a `time_budget_sec`, and — for evaluative modes
   — `evaluation_criteria` / `red_flags` / `strong_markers`. For **tutor**
   every question MUST include a `correction_template` (the correct answer, so
   the tutor can give feedback).
4. **Name the file** `{mode}_{topic}_{difficulty}.json` and write it into the
   agent's `flows/` directory (e.g. `voice/flows/`). Ask the user to confirm the
   destination if unclear.
5. **Tell the user how to run it** (pass the flow's language via `--lang`):
   `uv run python bot_cli.py --flow {mode}_{topic}_{difficulty} --lang en`

## Modes

Modes are **language-neutral** — set the language via the `language` field, not
the mode name.

| mode | Style | Feedback during session? | Needs `correction_template`? |
|---|---|---|---|
| `tech` | Technical interview | No — neutral markers only | No |
| `tutor` | Demanding-but-kind tutor | Yes — explicit per answer | **Yes (required)** |
| `eli5` | Gentle explainer for non-technical people | Encouraging, soft | Optional |
| `conversation` | Casual fluency practice in the session language | No grammar correction | No |
| `language-tutor` | Language lessons (grammar/pronunciation) | Yes — short correction | Optional |

## Rules

- `text` / `opening` / `wrap_up` are written in the session `language` (default
  English). Well-known technical terms stay in English even in other languages.
- `opening` and `wrap_up` are spoken **verbatim** by the agent — write them as
  natural speech, not stage directions.
- Keep questions genuinely answerable by voice — no "write code" prompts;
  favour "explain", "compare", "when would you", "walk me through".
- `time_budget_sec` is a soft guide (typically 120–240s per question).
- Difficulty shapes depth, not just count: `hard` questions probe trade-offs and
  edge cases; `easy` checks core understanding.
- Do NOT invent facts for `correction_template` — base corrections on
  established knowledge; if unsure about a fact, keep the correction general or
  flag it to the user.

## Lifecycle

Flows are disposable. After a session a flow is "used" — regenerate a fresh one
for the same topic rather than reusing. Old flows can be archived under
`flows/archive/` (keep, don't delete).
