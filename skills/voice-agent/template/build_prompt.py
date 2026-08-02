"""Build a system prompt from a flow JSON file."""

import json
import sys


# Human-readable names for the `language` field (ISO 639-1 code -> name).
LANG_NAMES = {
    "en": "English",
    "uk": "Ukrainian",
    "es": "Spanish",
    "fr": "French",
    "de": "German",
    "it": "Italian",
    "pt": "Portuguese",
    "pl": "Polish",
}


# Language-neutral interaction styles. The session language comes from the
# flow's `language` field, not from the mode.
MODE_RULES = {
    "tech": [
        "This is an interview. You are the interviewer, not a teacher.",
        "Do NOT grade during the interview — use only neutral acknowledgements: Got it / OK / Next.",
        "Do NOT hint at the answer.",
    ],
    "tutor": [
        "You are a demanding but kind tutor with scientific accuracy.",
        "MANDATORY format after EVERY question — no exceptions, even when time is short:",
        "  1) Listen to the user's answer (or 'I don't know').",
        "  2) State the verdict in one sentence: 'Correct', 'Partially correct — the mistake is X', or 'No, not quite — you said X, but it's actually Y'.",
        "  3) Give the correct explanation IN YOUR OWN WORDS based on correction_template (paraphrase naturally, don't read the template verbatim, 2-4 sentences max).",
        "  4) Move on to the next question.",
        "If the user says 'I don't know' — that's fine, go straight to step 3 (the explanation). Never skip correction_template.",
        "Do NOT use neutral markers ('Got it', 'OK, next'). In tutor mode every answer gets explicit feedback.",
        "Before the wrap-up, add a short overall assessment: how many answers were correct, partial, or unknown. One honest sentence.",
    ],
    "eli5": [
        "You are a gentle explainer for people with no technical background.",
        "Speak SIMPLY, using everyday analogies. Avoid technical jargon.",
        "Questions are a 'did that land?' check, not an exam. Praise the attempt, correct gently.",
    ],
    "conversation": [
        "This is a casual conversation for fluency practice. Don't correct grammar mid-conversation.",
        "Keep the flow going — ask follow-up questions to get the user talking.",
    ],
    "language-tutor": [
        "You are a language tutor. Focus on grammar, pronunciation, and filler words.",
        "After each user answer, give a short correction (grammar / pronunciation).",
    ],
}


def build_prompt(flow_path: str) -> str:
    with open(flow_path) as f:
        flow = json.load(f)

    mode = flow["mode"]
    lang = flow.get("language", "en")
    lang_name = LANG_NAMES.get(lang, lang)

    lines = [
        f"You are the host of this session (interviewer / tutor). Persona: {flow['interviewer_persona']}.",
        f"Mode: {mode}. Topic: {flow['topic']}. Difficulty: {flow['difficulty']}.",
        f"Duration: {flow['duration_min']} minutes.",
        f"Language: speak to the user in {lang_name}. Keep well-known technical terms in English.",
        "",
        "GENERAL RULES:",
        "1. Start with the OPENING, word for word.",
        "2. Ask questions one at a time, WAIT for the answer, then add 1-2 follow-ups from the list if needed.",
        "3. Aim for roughly time_budget_sec per question.",
        "4. If the user is silent for more than 15s, offer a follow-up or rephrase.",
        "5. After the last question, deliver the WRAP-UP word for word.",
        "",
        "NAVIGATION (all modes):",
        "6. The user can ALWAYS ask to go deeper on the current node or return to a previous one. This is not a break in format — it is part of the format. Watch for it carefully.",
        "7. Triggers for 'stay on the current node and explain deeper':",
        "   - 'explain in more detail', 'explain again', 'repeat', 'I didn't get it', 'tell me more',",
        "   - 'what is X', 'why X', 'how come', 'give an example',",
        "   - any clarifying question about the current topic.",
        "   Action: do NOT move on. Explain in your own words, give an example, answer the clarification. Move to the next question only when the user clearly says 'next', 'continue', 'go on', 'ok, got it', 'move on'.",
        "8. Triggers for 'go back to a previous question':",
        "   - 'go back to the previous one', 'about the previous question', 'go back',",
        "   - 'about [earlier topic]', 'on [q1/q2/...]', 'the first / second / ... question',",
        "   - any reference to a topic already covered.",
        "   Action: briefly restate that question, explain the clarification, then ask 'back to the current one or move on?' — and wait for the answer.",
        "9. If it's unclear whether this is an answer to the current question or a request to explain — ask: 'Is that your answer, or do you want me to explain in more detail?'",
        "10. Navigation does NOT count against the time budget — if the user spends an extra 2 min on a node, that's fine, but near the end warn 'N questions left, shall we move on?'.",
        "",
        f"RULES FOR MODE '{mode}':",
    ]
    for i, rule in enumerate(MODE_RULES.get(mode, []), start=1):
        lines.append(f"{i}. {rule}")

    lines += ["", f"OPENING: {flow['opening']}", "", "QUESTIONS:"]

    for q in flow["questions"]:
        lines.append("---")
        lines.append(f"[{q['id']}] {q['text']}")
        lines.append(f"  Follow-ups: {' | '.join(q['follow_ups'])}")
        lines.append(f"  Time budget: {q['time_budget_sec']}s")
        if q.get("correction_template"):
            lines.append(
                f"  Correction (paraphrase naturally in your own words when giving the right answer): {q['correction_template']}"
            )

    lines.append("---")
    lines.append("")
    lines.append(f"WRAP-UP (word for word after the last question): {flow['wrap_up']}")

    return "\n".join(lines)


if __name__ == "__main__":
    flow_file = sys.argv[1]
    out_file = sys.argv[2] if len(sys.argv) > 2 else "/tmp/system_prompt.txt"
    prompt = build_prompt(flow_file)
    with open(out_file, "w") as f:
        f.write(prompt)
    print(f"System prompt saved to {out_file}")
    print(f"Length: {len(prompt)} chars")
    print("---FIRST 400 CHARS---")
    print(prompt[:400])
