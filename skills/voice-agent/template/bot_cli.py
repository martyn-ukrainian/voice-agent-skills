"""Terminal-only voice agent — LocalAudioTransport instead of WebRTC/browser.

Usage:
    uv run python bot_cli.py --flow tutor_biological-neurons_medium
    uv run python bot_cli.py --system-prompt "You are..." --lang en

By default a turn ends only on the trigger word (a natural VAD pause is
ignored). Pass --free-vad to let a natural pause close the turn again.

The transcript is printed to stdout as:
    [USER] ...
    [ASSISTANT] ...

Redirect it to a file so another agent/script can read it live:
    uv run python bot_cli.py --flow X > /tmp/voice-live.log 2>&1
"""

import argparse
import asyncio
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from loguru import logger

from pipecat.audio.vad.silero import SileroVADAnalyzer
from pipecat.audio.vad.vad_analyzer import VADParams
from pipecat.frames.frames import (
    BotStartedSpeakingFrame,
    BotStoppedSpeakingFrame,
    Frame,
    InputAudioRawFrame,
    InterimTranscriptionFrame,
    LLMRunFrame,
    TranscriptionFrame,
    UserStartedSpeakingFrame,
    UserStoppedSpeakingFrame,
)
from pipecat.processors.frame_processor import FrameDirection, FrameProcessor
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.runner import PipelineRunner
from pipecat.pipeline.task import PipelineParams, PipelineTask
from pipecat.processors.aggregators.openai_llm_context import OpenAILLMContext
from pipecat.processors.transcript_processor import TranscriptProcessor
from pipecat.services.cartesia.tts import CartesiaTTSService
from pipecat.services.deepgram.stt import DeepgramSTTService
from pipecat.services.openai.llm import OpenAILLMService
from pipecat.transcriptions.language import Language
from pipecat.transports.local.audio import (
    LocalAudioTransport,
    LocalAudioTransportParams,
)
from deepgram import LiveOptions

from build_prompt import build_prompt
from transcript import TranscriptCollector

load_dotenv()

# Cartesia voice id (sonic-3). sonic-3 voices are multilingual — override with
# --voice-id if you want a different one.
DEFAULT_VOICE_ID = "05ffab9c-d380-4909-8375-cd12f59238c3"
DEFAULT_SYSTEM_PROMPT = (
    "You are a friendly voice companion. The user started a session without a "
    "flow file. Greet them, briefly ask what they'd like to talk about, and "
    "keep a natural conversation going. For a structured interview or lesson, "
    "suggest starting from a flow: '--flow <flow-name>'."
)

# ISO 639-1 code -> pipecat Language enum, for STT and TTS.
LANG_ENUM = {
    "en": Language.EN,
    "uk": Language.UK,
    "es": Language.ES,
    "fr": Language.FR,
    "de": Language.DE,
    "it": Language.IT,
    "pt": Language.PT,
    "pl": Language.PL,
}

# Human-readable names, used in the "speak <language>" instruction.
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

# Default turn-end trigger word per language (radio-style "over"). Override with
# --trigger. Falls back to "over" for any language not listed here.
DEFAULT_TRIGGERS = {
    "en": ("over",),
    "uk": ("прийом", "прийома", "прийоми", "приом", "приьом"),
    "es": ("cambio",),
    "fr": ("terminé",),
    "de": ("ende",),
}


class DiagProcessor(FrameProcessor):
    """Logs audio activity and VAD/STT events to stderr with a [DIAG] prefix."""

    def __init__(self):
        super().__init__()
        self._audio_frames = 0
        self._audio_bytes = 0
        self._peak = 0
        self._reporter_task = None

    async def _report_loop(self):
        while True:
            await asyncio.sleep(2.0)
            if self._audio_frames:
                # Peak as a fraction of int16 max=32768 -> normalized 0..1.
                peak_norm = self._peak / 32768.0 if self._peak else 0.0
                logger.info(
                    f"[DIAG] audio: {self._audio_frames} frames, "
                    f"peak={peak_norm:.3f} (raw {self._peak})"
                )
            else:
                logger.warning("[DIAG] audio: 0 frames / 2s — the microphone is silent!")
            self._audio_frames = 0
            self._audio_bytes = 0
            self._peak = 0

    async def process_frame(self, frame: Frame, direction: FrameDirection):
        await super().process_frame(frame, direction)

        if self._reporter_task is None:
            self._reporter_task = asyncio.create_task(self._report_loop())

        if isinstance(frame, InputAudioRawFrame):
            self._audio_frames += 1
            self._audio_bytes += len(frame.audio)
            # int16 little-endian: compute peak amplitude.
            import struct

            n = len(frame.audio) // 2
            if n:
                samples = struct.unpack(f"<{n}h", frame.audio)
                p = max(abs(s) for s in samples)
                if p > self._peak:
                    self._peak = p
        elif isinstance(frame, UserStartedSpeakingFrame):
            logger.info("[DIAG] 🎤 VAD: user STARTED speaking")
        elif isinstance(frame, UserStoppedSpeakingFrame):
            logger.info("[DIAG] 🛑 VAD: user STOPPED speaking")
        elif isinstance(frame, InterimTranscriptionFrame):
            logger.info(f"[DIAG] 📝 interim: {frame.text!r}")
        elif isinstance(frame, TranscriptionFrame):
            logger.info(f"[DIAG] ✅ FINAL: {frame.text!r}")
        elif isinstance(frame, BotStartedSpeakingFrame):
            logger.info("[DIAG] 🔊 bot STARTED speaking")
        elif isinstance(frame, BotStoppedSpeakingFrame):
            logger.info("[DIAG] 🔇 bot STOPPED speaking")

        await self.push_frame(frame, direction)


class WaitForCompletionPhrase(FrameProcessor):
    """Ends a turn on a trigger word (radio-protocol "over").

    With `require_trigger=True` (default) a natural VAD-based
    UserStoppedSpeakingFrame (a pause of stop_secs) does NOT close the turn by
    itself — it is dropped. The turn closes ONLY when the user explicitly says
    the trigger word. This prevents cutting the user off mid-thought.

    `require_trigger=False` restores the old behaviour (VAD closes the turn as
    usual, the trigger just speeds up "finish without waiting for the pause") —
    enabled via the `--free-vad` flag for sessions where the trigger gets in the
    way (e.g. a monologue with long pauses where saying "over" each time is
    annoying).
    """

    def __init__(self, triggers=("over",), require_trigger: bool = True):
        super().__init__()
        self.triggers = tuple(t.lower() for t in triggers)
        self.require_trigger = require_trigger

    def _strip_trigger(self, text: str) -> tuple[str, bool]:
        lower = text.lower()
        for t in self.triggers:
            if t in lower:
                idx = lower.rfind(t)
                cleaned = (text[:idx] + text[idx + len(t) :]).strip(" .,!?…")
                return cleaned, True
        return text, False

    async def process_frame(self, frame: Frame, direction: FrameDirection):
        await super().process_frame(frame, direction)

        if isinstance(frame, TranscriptionFrame):
            cleaned, triggered = self._strip_trigger(frame.text)
            if triggered:
                logger.info(
                    f"[TRIGGER] trigger word detected → fast flush. clean={cleaned!r}"
                )
                if cleaned:
                    # Forward the payload without the trigger word.
                    new_frame = TranscriptionFrame(
                        text=cleaned,
                        user_id=frame.user_id,
                        timestamp=frame.timestamp,
                    )
                    await self.push_frame(new_frame, direction)
                # Force turn end so the aggregator flushes whatever it buffered.
                await self.push_frame(UserStoppedSpeakingFrame(), direction)
                return
            await self.push_frame(frame, direction)
            return

        if isinstance(frame, UserStoppedSpeakingFrame) and self.require_trigger:
            # A natural VAD turn-end is dropped — we wait for the explicit trigger.
            logger.info(
                "[TRIGGER] VAD UserStoppedSpeakingFrame suppressed (waiting for trigger word)"
            )
            return

        await self.push_frame(frame, direction)


class MuteWhileBotSpeaking(FrameProcessor):
    """Drops user-speech / transcription frames while the bot is speaking
    (+ an 800ms tail). Guards against self-echo when the mic hears the speakers."""

    HOLD_OFF_SEC = 0.8

    def __init__(self):
        super().__init__()
        self._bot_speaking = False
        self._bot_stopped_at = 0.0

    def _muted(self) -> bool:
        if self._bot_speaking:
            return True
        if (
            self._bot_stopped_at
            and (asyncio.get_event_loop().time() - self._bot_stopped_at)
            < self.HOLD_OFF_SEC
        ):
            return True
        return False

    async def process_frame(self, frame: Frame, direction: FrameDirection):
        await super().process_frame(frame, direction)

        if isinstance(frame, BotStartedSpeakingFrame):
            self._bot_speaking = True
        elif isinstance(frame, BotStoppedSpeakingFrame):
            self._bot_speaking = False
            self._bot_stopped_at = asyncio.get_event_loop().time()

        # Block user-side speech events while the bot is speaking (or the tail).
        if self._muted() and isinstance(
            frame,
            (
                TranscriptionFrame,
                InterimTranscriptionFrame,
                UserStartedSpeakingFrame,
                UserStoppedSpeakingFrame,
            ),
        ):
            logger.info(f"[MUTE] dropped {type(frame).__name__} (bot speaking)")
            return

        await self.push_frame(frame, direction)


BOT_DIR = Path(__file__).parent.resolve()
FLOWS_DIR = BOT_DIR / "flows"


async def run_cli(
    system_prompt: str,
    voice_id: str,
    language_mode: str,
    triggers: tuple,
    session_id: str,
    transcript_dir: str,
    require_trigger: bool = True,
):
    logger.info(f"Session {session_id} [lang={language_mode}]")

    # VAD tuning for BT microphones: lower confidence threshold, lower min_volume,
    # longer "silence" (2.0s) so speech isn't cut on pauses.
    transport = LocalAudioTransport(
        LocalAudioTransportParams(
            audio_in_enabled=True,
            audio_out_enabled=True,
            audio_out_10ms_chunks=2,
            vad_analyzer=SileroVADAnalyzer(
                params=VADParams(
                    confidence=0.3,
                    min_volume=0.05,
                    start_secs=0.15,
                    stop_secs=2.0,
                )
            ),
        )
    )

    if language_mode == "multi":
        stt_opts = LiveOptions(
            model="nova-3",
            language="multi",
            smart_format=True,
            punctuate=True,
            interim_results=True,
            encoding="linear16",
            channels=1,
            sample_rate=16000,
        )
        tts_params = CartesiaTTSService.InputParams()
        lang_instruction = (
            "IMPORTANT: reply in the same language the user just spoke."
        )
    else:
        lang_enum = LANG_ENUM.get(language_mode, Language.EN)
        # nova-3 has the best English; nova-2-general has the widest language coverage.
        stt_model = "nova-3" if language_mode == "en" else "nova-2-general"
        stt_opts = LiveOptions(
            model=stt_model,
            language=lang_enum.value,
            smart_format=True,
            punctuate=True,
            interim_results=True,
            encoding="linear16",
            channels=1,
            sample_rate=16000,
        )
        tts_params = CartesiaTTSService.InputParams(language=lang_enum)
        lang_instruction = f"Speak {LANG_NAMES.get(language_mode, language_mode)}."

    stt = DeepgramSTTService(
        api_key=os.environ["DEEPGRAM_API_KEY"],
        audio_passthrough=True,
        live_options=stt_opts,
    )
    llm = OpenAILLMService(
        api_key=os.environ["OPENAI_API_KEY"],
        model=os.getenv("OPENAI_MODEL", "gpt-4.1"),
        params=OpenAILLMService.InputParams(temperature=0.4),
    )
    tts = CartesiaTTSService(
        api_key=os.environ["CARTESIA_API_KEY"],
        voice_id=voice_id,
        model="sonic-3",
        params=tts_params,
    )

    context = OpenAILLMContext(
        messages=[
            {"role": "system", "content": f"{system_prompt}\n\n{lang_instruction}"},
            {"role": "user", "content": "Hi, I'm ready. Let's begin."},
        ]
    )
    context_aggregator = llm.create_context_aggregator(context)

    transcript_proc = TranscriptProcessor()
    collector = TranscriptCollector(session_id, out_dir=transcript_dir)
    collector.start_session(datetime.now(timezone.utc))

    diag = DiagProcessor()
    mute = MuteWhileBotSpeaking()
    wait_trigger = WaitForCompletionPhrase(
        triggers=triggers, require_trigger=require_trigger
    )
    pipeline = Pipeline(
        [
            transport.input(),
            diag,
            stt,
            mute,
            wait_trigger,
            transcript_proc.user(),
            context_aggregator.user(),
            llm,
            tts,
            transport.output(),
            transcript_proc.assistant(),
            context_aggregator.assistant(),
        ]
    )

    task = PipelineTask(
        pipeline,
        params=PipelineParams(
            allow_interruptions=False,
            enable_metrics=True,
            enable_usage_metrics=True,
            report_only_initial_ttfb=True,
        ),
    )

    @transcript_proc.event_handler("on_transcript_update")
    async def _on_transcript(_proc, frame):
        for msg in frame.messages:
            collector.add_utterance(msg.role, msg.content)
            # The key line — another agent/script reads this:
            print(f"[{msg.role.upper()}] {msg.content}", flush=True)

    # Start immediately (no client_connected — audio is already connected).
    async def _kickoff():
        await asyncio.sleep(0.3)
        await task.queue_frames([LLMRunFrame()])

    runner = PipelineRunner(handle_sigint=True)
    try:
        await asyncio.gather(runner.run(task), _kickoff())
    finally:
        collector.save()
        logger.info(f"Session {session_id} ended → {transcript_dir}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--flow", help="flow name (without .json), e.g. tutor_biological-neurons_medium"
    )
    ap.add_argument("--system-prompt", help="manual system prompt (if no flow)")
    ap.add_argument("--voice-id", default=DEFAULT_VOICE_ID)
    ap.add_argument(
        "--lang",
        default="en",
        help="session language: an ISO code (en, uk, es, fr, ...) or 'multi' for auto-detect",
    )
    ap.add_argument(
        "--trigger",
        default=None,
        help="turn-end trigger word (default: per-language, 'over' for English)",
    )
    ap.add_argument("--session-id", default=None)
    ap.add_argument("--transcript-dir", default=str(BOT_DIR / "transcripts"))
    ap.add_argument(
        "--free-vad",
        action="store_true",
        help="Disable the mandatory trigger word — VAD closes the turn on a pause as usual.",
    )
    args = ap.parse_args()

    if args.flow:
        flow_path = FLOWS_DIR / f"{args.flow}.json"
        if not flow_path.exists():
            print(f"❌ Flow not found: {flow_path}", file=sys.stderr)
            sys.exit(1)
        prompt = build_prompt(str(flow_path))
    elif args.system_prompt:
        prompt = args.system_prompt
    else:
        prompt = DEFAULT_SYSTEM_PROMPT

    if args.trigger:
        triggers = (args.trigger,)
    else:
        triggers = DEFAULT_TRIGGERS.get(args.lang, ("over",))

    session_id = (
        args.session_id
        or f"cli-{datetime.now().strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:6]}"
    )

    # Strip loguru formatting so stdout stays clean for parsing.
    logger.remove()
    logger.add(
        sys.stderr, format="<dim>{time:HH:mm:ss}</dim> | {message}", level="INFO"
    )

    print(
        f"[SYSTEM] session={session_id} flow={args.flow or 'manual'} lang={args.lang}",
        flush=True,
    )
    print(
        f"[SYSTEM] speak into the mic; say '{triggers[0]}' to end your turn",
        flush=True,
    )

    asyncio.run(
        run_cli(
            system_prompt=prompt,
            voice_id=args.voice_id,
            language_mode=args.lang,
            triggers=triggers,
            session_id=session_id,
            transcript_dir=args.transcript_dir,
            require_trigger=not args.free_vad,
        )
    )


if __name__ == "__main__":
    main()
