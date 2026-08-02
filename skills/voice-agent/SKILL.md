---
name: voice-agent
description: |
  Scaffold a local, terminal-based voice agent into a repo. Use when the user
  wants a spoken voice bot / voice interviewer / voice tutor that runs in the
  terminal (microphone + speakers directly, no browser). Drops a self-contained
  Pipecat CLI app: Deepgram STT -> OpenAI LLM -> Cartesia TTS over
  LocalAudioTransport, with a push-to-talk trigger word, self-echo muting, and
  live transcript printed to stdout so an agent can read the conversation.
license: MIT
metadata:
  version: "0.1.0"
---

# Voice Agent (terminal) — scaffold

Set up a **terminal-only** voice agent in the current project. No browser, no
WebRTC signaling server — audio goes straight through the machine's microphone
and speakers via Pipecat's `LocalAudioTransport`. The transcript is printed to
stdout (`[USER] ...` / `[ASSISTANT] ...`), so a coding agent can watch the
conversation live by redirecting output to a file.

## When to use

- "build me a voice agent I can talk to in the terminal"
- "voice interviewer / voice tutor for practicing X"
- "spoken bot, no web UI"

If the user instead wants an in-browser voice widget, this is the wrong skill —
they need the WebRTC/`SmallWebRTCTransport` variant, not this one.

## What it installs

Copy the files from this skill's `template/` directory into the target repo.
Default destination is a `voice/` subfolder — confirm with the user if a
different location fits better.

```
voice/
  bot_cli.py        # the agent: LocalAudioTransport -> STT -> LLM -> TTS
  build_prompt.py   # turns a flow JSON into a system prompt
  transcript.py     # saves transcript to JSON + VTT
  pyproject.toml    # CLI-only deps (pipecat-ai[...,local]) — no fastapi/webrtc
  .env.example      # API keys
  README.md         # usage
  flows/            # (created empty) tutor/lesson/interview flow JSON files go here
```

## Setup steps

1. **Copy the template.** Copy every file in `template/` into `voice/` in the
   target repo. Create `voice/flows/` (empty). Do NOT copy `.env` — only
   `.env.example`.
2. **Keys.** Tell the user to `cp .env.example .env` and fill in
   `OPENAI_API_KEY`, `CARTESIA_API_KEY`, `DEEPGRAM_API_KEY`. Never write real
   keys into a tracked file.
3. **Install deps.** Recommend `uv` — `cd voice && uv sync` (or
   `uv run python bot_cli.py ...` which resolves on first run). Fallback:
   `pip install -e .` inside a venv.
4. **Voice.** `bot_cli.py` ships a multilingual Cartesia `sonic-3` voice id as
   `DEFAULT_VOICE_ID`. To change it, pass `--voice-id <id>` or edit the
   constant.
5. **Run.** See "Running" below. Confirm the mic works — the `[DIAG]` lines on
   stderr report audio frames and peak volume every 2s; `0 frames` means the
   microphone is silent / wrong input device.

## Running

Manual system prompt:

```bash
cd voice
uv run python bot_cli.py --system-prompt "You are a friendly companion. Ask how things are going." --lang en
```

From a flow file (pairs with the `voice-agent-flow` skill):

```bash
uv run python bot_cli.py --flow tutor_biological-neurons_medium --lang en
```

Let a coding agent read the conversation live:

```bash
uv run python bot_cli.py --flow X > /tmp/voice-live.log 2>&1
# then tail/read /tmp/voice-live.log
```

## Key behaviours to explain to the user

- **Turn-taking is push-to-talk by default.** A turn ends only when the user
  says the trigger word **"over"** (radio-protocol). A natural VAD pause does
  NOT end the turn — this stops the bot cutting the user off mid-thought. Pass
  `--free-vad` to switch to normal pause-based turn ends (useful for long
  monologues). Override the trigger with `--trigger <word>`; per-language
  defaults live in `DEFAULT_TRIGGERS` in `bot_cli.py`.
- **Self-echo protection.** `MuteWhileBotSpeaking` drops user-side audio/
  transcription while the bot is speaking (+0.8s tail) so the mic hearing the
  speakers doesn't create a feedback loop. Essential without headphones.
- **Language.** `--lang en` (default; Deepgram `nova-3`) or any ISO code
  (`uk`, `es`, `fr`, … via `nova-2-general`), or `--lang multi` for auto
  language detection. In `multi` mode the LLM is instructed to reply in the
  language just spoken. STT model, TTS language, and default trigger word all
  follow `--lang`.
- **Transcripts** land in `voice/transcripts/<session>.json` and `.vtt`.

## Customising

- Swap providers by editing the service constructors in `bot_cli.py`
  (`DeepgramSTTService`, `OpenAILLMService`, `CartesiaTTSService`). Keep the
  pipeline order.
- The `DiagProcessor` is a debugging aid — safe to remove from the pipeline
  once audio is confirmed working, or leave it (it only logs to stderr).
- VAD is tuned for Bluetooth mics (low confidence/volume thresholds, 2.0s
  silence). Tighten `VADParams` for a good wired mic.
