# Flow JSON schema

A flow file drives one voice session. Filename: `{mode}_{topic}_{difficulty}.json`.

## Top-level fields

| Field | Type | Required | Notes |
|---|---|---|---|
| `mode` | string | ✅ | one of the modes below — controls the host's behaviour |
| `topic` | string | ✅ | short slug, e.g. `rag`, `pandas-basics` |
| `difficulty` | string | ✅ | `easy` \| `medium` \| `hard` |
| `duration_min` | number | ✅ | target session length in minutes |
| `language` | string | ✅ | ISO 639-1 code — `en` (default), `uk`, `es`, `fr`, `de`, `it`, `pt`, `pl`. Sets STT/TTS language and the language the host speaks. |
| `interviewer_persona` | string | ✅ | short persona label, e.g. `friendly_tutor`, `hiring_manager_winwin` |
| `opening` | string | ✅ | spoken verbatim at start |
| `questions` | array | ✅ | ordered list, 4–8 items (see below) |
| `wrap_up` | string | ✅ | spoken verbatim after the last question |

## Question object

| Field | Type | Required | Notes |
|---|---|---|---|
| `id` | string | ✅ | `q1`, `q2`, … |
| `text` | string | ✅ | the question, as spoken |
| `follow_ups` | string[] | ✅ | 1–3 probes if the answer is thin |
| `time_budget_sec` | number | ✅ | soft guide, usually 120–240 |
| `evaluation_criteria` | string[] | optional | what a good answer covers (interview mode) |
| `red_flags` | string[] | optional | signs of a weak / wrong answer |
| `strong_markers` | string[] | optional | signs of an excellent answer |
| `correction_template` | string | **required for `tutor`** | the correct answer, so the tutor can give explicit feedback; paraphrased naturally at runtime, not read verbatim |

## Modes and their rules

Modes are **language-neutral** — the session language is set by the `language`
field, not baked into the mode. These map to `MODE_RULES` in `build_prompt.py`.

- **`tech`** — technical interview. Interviewer, not teacher. No grading
  mid-session, only neutral markers (Got it / OK / Next). No hints.
- **`tutor`** — demanding-but-kind tutor. After every answer: state
  correct/partial/wrong in one sentence, then explain in own words from
  `correction_template` (2–4 sentences), then move on. "I don't know" → go
  straight to the explanation. Give a brief honest summary before wrap-up.
- **`eli5`** — gentle explainer for non-technical people. Simple language,
  everyday analogies, no jargon. Questions check understanding, not exam.
- **`conversation`** — casual fluency practice in the session `language`. Don't
  correct grammar mid-flow; keep it going with follow-ups.
- **`language-tutor`** — language lessons in the session `language`. Focus on
  grammar / pronunciation / fillers; short correction after each answer.

## Navigation (all modes)

The agent always lets the user ask to go deeper on the current node or return to
a previous one — that's built into the generated prompt, not the flow file. You
don't need to encode navigation in the JSON.
