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
| `--lang en` | session language — ISO code (`en` default, `uk`, `es`, `fr`, …). Env: `SESSION_LANG` |
| `--lang multi` | auto-detect language (`nova-3`); the bot replies in the user's language |
| `--trigger <word>` | override the turn-end trigger word (default: per-language, `over` for English). Env: `TRIGGER_WORD` |
| `--turn trigger\|vad` | turn-taking mode (trigger word vs natural pause). Env: `TURN_MODE` |
| `--free-vad` | alias for `--turn vad` |
| `--voice-id <id>` | override the TTS voice for this run |
| `--session-id`, `--transcript-dir` | control transcript output |

## Run from anywhere (global install)

This folder works both copied into a project **and** as a single global agent
callable from any directory. `.env` is loaded from **this** directory (not your
current one), and `flows/` + `transcripts/` resolve here too — so a `voice`
command that runs `bot_cli.py` by absolute path works from any cwd:

```bash
# ~/.local/bin/voice
HOME_DIR="$HOME/.local/share/voice-agent"
exec uv run --project "$HOME_DIR" python "$HOME_DIR/bot_cli.py" "$@"
```

Important: the wrapper must **not** `cd` into the home dir — run the script by
absolute path from your current cwd. (If cwd equals the script's own directory,
that dir shadows Python's import path and some packages — e.g. `nltk` — refuse
to import, aborting startup.)

## Read the conversation live

The transcript is printed to stdout (`[USER] ...` / `[ASSISTANT] ...`). Redirect
it to a file and any agent/script can read the dialogue in real time:

```bash
uv run python bot_cli.py --flow X > /tmp/voice-live.log 2>&1
```

## Providers (STT / LLM / TTS)

Providers are chosen in `.env`, not in code — `providers.py` has one factory per
stage and lazily imports only the selected backend:

```
STT_PROVIDER=deepgram
LLM_PROVIDER=openai            # any OpenAI-compatible API via OPENAI_BASE_URL
TTS_PROVIDER=cartesia          # or elevenlabs
```

- **Different LLM / model:** set `OPENAI_MODEL`, or point `OPENAI_BASE_URL` at an
  OpenAI-compatible endpoint (OpenRouter, Together, local vLLM) — no code change.
- **ElevenLabs TTS:** `TTS_PROVIDER=elevenlabs` + `ELEVENLABS_API_KEY` +
  `ELEVENLABS_VOICE_ID`.
- **Add a new provider:** add a branch to the matching factory in `providers.py`
  (import the pipecat service inside the branch), add its env vars here, and add
  any needed extra to `pyproject.toml`. `bot_cli.py` doesn't change.

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
| `providers.py` | STT / LLM / TTS factories selected via `*_PROVIDER` env vars |
| `build_prompt.py` | flow JSON → system prompt |
| `transcript.py` | saving the transcript (JSON + VTT) |
| `pyproject.toml` | dependencies (CLI-only) |
| `.env.example` | API keys |
| `flows/` | tutor/lesson/interview scenarios |
