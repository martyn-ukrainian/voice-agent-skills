"""Provider factories for STT / LLM / TTS, selected via environment variables.

Each factory reads a `*_PROVIDER` env var and lazily imports only the chosen
provider's pipecat service, so you don't need every provider's optional deps
installed to run one of them.

Add a new provider by adding a branch to the relevant factory — nothing in
`bot_cli.py` needs to change.

Env vars (see .env.example):
    STT_PROVIDER   deepgram
    LLM_PROVIDER   openai            (any OpenAI-compatible API via OPENAI_BASE_URL)
    TTS_PROVIDER   cartesia | elevenlabs
"""

import os

from pipecat.transcriptions.language import Language


# Default Cartesia sonic-3 voice (multilingual). Override with CARTESIA_VOICE_ID
# or --voice-id.
DEFAULT_CARTESIA_VOICE_ID = "05ffab9c-d380-4909-8375-cd12f59238c3"

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


def lang_enum(language_mode: str) -> Language:
    return LANG_ENUM.get(language_mode, Language.EN)


def build_stt(language_mode: str):
    """STT service. STT_PROVIDER selects the backend (default: deepgram)."""
    provider = os.getenv("STT_PROVIDER", "deepgram").lower()

    if provider == "deepgram":
        from deepgram import LiveOptions
        from pipecat.services.deepgram.stt import DeepgramSTTService

        if language_mode == "multi":
            model, lang = "nova-3", "multi"
        else:
            # nova-3 has the best English; nova-2-general has the widest coverage.
            model = "nova-3" if language_mode == "en" else "nova-2-general"
            lang = lang_enum(language_mode).value

        return DeepgramSTTService(
            api_key=os.environ["DEEPGRAM_API_KEY"],
            audio_passthrough=True,
            live_options=LiveOptions(
                model=model,
                language=lang,
                smart_format=True,
                punctuate=True,
                interim_results=True,
                encoding="linear16",
                channels=1,
                sample_rate=16000,
            ),
        )

    raise ValueError(f"Unknown STT_PROVIDER: {provider!r} (supported: deepgram)")


def build_llm():
    """LLM service. LLM_PROVIDER selects the backend (default: openai).

    For openai, set OPENAI_BASE_URL to point at any OpenAI-compatible endpoint
    (OpenRouter, Together, a local vLLM, …) — no other change needed.
    """
    provider = os.getenv("LLM_PROVIDER", "openai").lower()

    if provider == "openai":
        from pipecat.services.openai.llm import OpenAILLMService

        temperature = float(os.getenv("LLM_TEMPERATURE", "0.4"))
        kwargs = dict(
            api_key=os.environ["OPENAI_API_KEY"],
            model=os.getenv("OPENAI_MODEL", "gpt-4.1-mini"),
            params=OpenAILLMService.InputParams(temperature=temperature),
        )
        base_url = os.getenv("OPENAI_BASE_URL")
        if base_url:
            kwargs["base_url"] = base_url
        return OpenAILLMService(**kwargs)

    raise ValueError(f"Unknown LLM_PROVIDER: {provider!r} (supported: openai)")


def build_tts(language_mode: str, voice_id: str | None = None):
    """TTS service. TTS_PROVIDER selects the backend (default: cartesia).

    `voice_id` (from --voice-id) wins over the provider's env voice id.
    """
    provider = os.getenv("TTS_PROVIDER", "cartesia").lower()
    # In 'multi' mode we don't pin a TTS language — the model speaks the user's.
    lang = None if language_mode == "multi" else lang_enum(language_mode)

    if provider == "cartesia":
        from pipecat.services.cartesia.tts import CartesiaTTSService

        params = (
            CartesiaTTSService.InputParams(language=lang)
            if lang
            else CartesiaTTSService.InputParams()
        )
        return CartesiaTTSService(
            api_key=os.environ["CARTESIA_API_KEY"],
            voice_id=voice_id
            or os.getenv("CARTESIA_VOICE_ID", DEFAULT_CARTESIA_VOICE_ID),
            model=os.getenv("CARTESIA_MODEL", "sonic-3"),
            params=params,
        )

    if provider == "elevenlabs":
        from pipecat.services.elevenlabs.tts import ElevenLabsTTSService

        params = (
            ElevenLabsTTSService.InputParams(language=lang)
            if lang
            else ElevenLabsTTSService.InputParams()
        )
        return ElevenLabsTTSService(
            api_key=os.environ["ELEVENLABS_API_KEY"],
            voice_id=voice_id or os.environ["ELEVENLABS_VOICE_ID"],
            model=os.getenv("ELEVENLABS_MODEL", "eleven_turbo_v2_5"),
            params=params,
        )

    raise ValueError(
        f"Unknown TTS_PROVIDER: {provider!r} (supported: cartesia, elevenlabs)"
    )
