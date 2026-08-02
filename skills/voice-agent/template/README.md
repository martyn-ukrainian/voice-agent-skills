# voice-agent (terminal)

A local voice agent on Pipecat that runs **right in the terminal** — microphone
and speakers directly via `LocalAudioTransport`. No browser, no WebRTC server,
no external service for transport.

Pipeline: **Deepgram STT → OpenAI LLM → Cartesia TTS**.

## Start

```bash
cp .env.example .env
# fill in: OPENAI_API_KEY, CARTESIA_API_KEY, DEEPGRAM_API_KEY
uv sync                     # or: pip install -e .  in a venv
uv run python bot_cli.py --system-prompt "You are a friendly companion." --lang en
```

Talk into the mic. To **end your turn**, say the word **"over"** (like on a
radio). A natural pause does not end the turn by itself — this keeps the bot
from cutting you off mid-thought.

## Flags

| Flag | What it does |
|---|---|
| `--flow <name>` | build the system prompt from `flows/<name>.json` |
| `--system-prompt "..."` | manual system prompt |
| `--voice-id <id>` | Cartesia voice id (default baked into the file) |
| `--lang en` | session language — ISO code (`en` default, `uk`, `es`, `fr`, …) |
| `--lang multi` | auto-detect language (`nova-3`); the bot replies in the user's language |
| `--trigger <word>` | override the turn-end trigger word (default: per-language, `over` for English) |
| `--free-vad` | disable the trigger — the turn ends on a pause |
| `--session-id`, `--transcript-dir` | control transcript output |

## Read the conversation live

The transcript is printed to stdout (`[USER] ...` / `[ASSISTANT] ...`). Redirect
it to a file and any agent/script can read the dialogue in real time:

```bash
uv run python bot_cli.py --flow X > /tmp/voice-live.log 2>&1
```

## Flow files

Structured tutor/lesson/interview sessions — JSON in `flows/`, named
`{mode}_{topic}_{difficulty}.json`. Generate them with the `voice-agent-flow`
skill. Session transcripts are saved to `transcripts/*.json` + `*.vtt`.

## Microphone diagnostics

Every 2s a `[DIAG] audio: N frames, peak=...` line goes to stderr. If you see
`0 frames / 2s — the microphone is silent`, it's the wrong input device or the
mic has no access. A peak near 0 means the mic is too quiet — raise the input
volume.

## Files

| File | Purpose |
|---|---|
| `bot_cli.py` | the agent: LocalAudioTransport → STT → LLM → TTS + processors |
| `build_prompt.py` | flow JSON → system prompt |
| `transcript.py` | saving the transcript (JSON + VTT) |
| `pyproject.toml` | dependencies (CLI-only) |
| `.env.example` | API keys |
| `flows/` | tutor/lesson/interview scenarios |
