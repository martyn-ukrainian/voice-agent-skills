# voice-agent-skills

Claude Code skills for building and running **local, terminal-based voice
agents** on [Pipecat](https://github.com/pipecat-ai/pipecat) — a voice bot you
talk to in the terminal (microphone + speakers, no browser), plus a generator
for the structured "flows" that drive it.

Two skills:

| Skill | What it does |
|---|---|
| **`voice-agent`** | Scaffolds a self-contained terminal voice agent into a repo: Deepgram STT → OpenAI LLM → Cartesia TTS over `LocalAudioTransport`, with a push-to-talk trigger word, self-echo muting, and a live transcript printed to stdout. |
| **`voice-agent-flow`** | Generates a valid `{mode}_{topic}_{difficulty}.json` flow — a tutoring session, ELI5 explainer, fluency-practice conversation, or mock interview — that the agent runs as its script. Language-neutral modes; default English. |

## Why terminal, not browser

The agent uses Pipecat's `LocalAudioTransport`, so there's no WebRTC signaling
server, no web UI, and no external service for transport. You run one Python
command and start talking. Because the transcript streams to stdout
(`[USER] ...` / `[ASSISTANT] ...`), a coding agent can watch the whole
conversation live by redirecting output to a file.

## Install (as a Claude Code plugin)

```
/plugin marketplace add martyn-ukrainian/voice-agent-skills
/plugin install voice-agent-skills@voice-agent-skills
```

Then, in any repo:

- *"scaffold a terminal voice agent here"* → runs `voice-agent`
- *"make a medium RAG tutor flow"* → runs `voice-agent-flow`

## Quick start (what the scaffold gives you)

```bash
cd voice
cp .env.example .env          # add OPENAI_API_KEY, CARTESIA_API_KEY, DEEPGRAM_API_KEY
uv run python bot_cli.py --system-prompt "You are a friendly companion." --lang en
```

Talk into the mic; say **"over"** to end your turn. Run from a flow:

```bash
uv run python bot_cli.py --flow tutor_rag_medium --lang en
```

The session language is set per flow (`language` field) and passed via `--lang`
(`en` default, `uk`, `es`, `fr`, … or `multi` for auto-detect).

## Stack

- **STT** — Deepgram (`nova-3` for English/multi, `nova-2-general` for others)
- **LLM** — OpenAI (`gpt-4.1`, temperature 0.4)
- **TTS** — Cartesia (`sonic-3`)
- **Transport** — Pipecat `LocalAudioTransport` (local mic/speakers)
- **VAD** — Silero, tuned for Bluetooth mics

Origin: distilled from a working voice tutor/interviewer used for practice,
stripped down to a clean, reusable terminal core.

## License

MIT — see [LICENSE](./LICENSE).
