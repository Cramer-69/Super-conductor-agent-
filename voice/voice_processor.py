"""
Voice processing: speech-to-text and text-to-speech.

Backend selection (automatic, based on available API keys):
  TTS:  Gemini TTS (gemini-3.1-flash-tts-preview) if GOOGLE_API_KEY is set,
        otherwise OpenAI TTS (tts-1) if OPENAI_API_KEY is set.
  STT:  OpenAI Whisper (whisper-1) if OPENAI_API_KEY is set,
        otherwise Gemini multimodal transcription if GOOGLE_API_KEY is set.
"""
from __future__ import annotations

import io
import mimetypes
import os
import struct
from pathlib import Path
from typing import Optional

from utils.logger import logger


# --------------------------------------------------------------------------- #
#  WAV conversion helpers (needed for Gemini PCM output)                      #
# --------------------------------------------------------------------------- #

def _parse_audio_mime_type(mime_type: str) -> dict:
    bits_per_sample = 16
    rate = 24000
    for part in mime_type.split(";"):
        part = part.strip()
        if part.lower().startswith("rate="):
            try:
                rate = int(part.split("=", 1)[1])
            except (ValueError, IndexError):
                pass
        elif part.startswith("audio/L"):
            try:
                bits_per_sample = int(part.split("L", 1)[1])
            except (ValueError, IndexError):
                pass
    return {"bits_per_sample": bits_per_sample, "rate": rate}


def _pcm_to_wav(audio_data: bytes, mime_type: str) -> bytes:
    params = _parse_audio_mime_type(mime_type)
    bits_per_sample = params["bits_per_sample"]
    sample_rate = params["rate"]
    num_channels = 1
    data_size = len(audio_data)
    bytes_per_sample = bits_per_sample // 8
    block_align = num_channels * bytes_per_sample
    byte_rate = sample_rate * block_align
    chunk_size = 36 + data_size
    header = struct.pack(
        "<4sI4s4sIHHIIHH4sI",
        b"RIFF", chunk_size, b"WAVE", b"fmt ", 16,
        1, num_channels, sample_rate, byte_rate,
        block_align, bits_per_sample, b"data", data_size,
    )
    return header + audio_data


# --------------------------------------------------------------------------- #
#  Gemini TTS voices                                                           #
# --------------------------------------------------------------------------- #

GEMINI_VOICES = [
    {"id": "Zephyr",   "name": "Zephyr",   "description": "Bright, clear"},
    {"id": "Puck",     "name": "Puck",      "description": "Upbeat, friendly"},
    {"id": "Charon",   "name": "Charon",    "description": "Informative, calm"},
    {"id": "Kore",     "name": "Kore",      "description": "Firm, professional"},
    {"id": "Fenrir",   "name": "Fenrir",    "description": "Excitable, energetic"},
    {"id": "Aoede",    "name": "Aoede",     "description": "Breezy, natural"},
    {"id": "Leda",     "name": "Leda",      "description": "Youthful, expressive"},
    {"id": "Achernar", "name": "Achernar",  "description": "Soft, warm"},
    {"id": "Sulafat",  "name": "Sulafat",   "description": "Warm, conversational"},
]

OPENAI_VOICES = [
    {"id": "nova",    "name": "Nova",    "description": "Female, clear, professional"},
    {"id": "alloy",   "name": "Alloy",   "description": "Neutral, versatile"},
    {"id": "echo",    "name": "Echo",    "description": "Male, clear"},
    {"id": "fable",   "name": "Fable",   "description": "British accent, expressive"},
    {"id": "onyx",    "name": "Onyx",    "description": "Deep, authoritative"},
    {"id": "shimmer", "name": "Shimmer", "description": "Soft female, warm"},
]


# --------------------------------------------------------------------------- #
#  VoiceProcessor                                                              #
# --------------------------------------------------------------------------- #

class VoiceProcessor:
    """
    Auto-selects TTS and STT backends from available API keys.
    Raises ValueError only if no usable key is found at all.
    """

    def __init__(self):
        self._google_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
        self._openai_key = os.getenv("OPENAI_API_KEY")

        # Determine backends
        if self._google_key:
            self.tts_backend = "gemini"
            self.tts_voice = "Zephyr"       # default Gemini voice
            self.tts_model = "gemini-2.5-flash-preview-tts"
        elif self._openai_key:
            self.tts_backend = "openai"
            self.tts_voice = "nova"
            self.tts_model = "tts-1"
        else:
            raise ValueError(
                "No TTS API key configured. "
                "Set GOOGLE_API_KEY (Gemini TTS) or OPENAI_API_KEY (OpenAI TTS)."
            )

        if self._openai_key:
            self.stt_backend = "openai"
            self.whisper_model = "whisper-1"
        elif self._google_key:
            self.stt_backend = "gemini"
        else:
            self.stt_backend = "none"

        logger.info(
            f"VoiceProcessor initialized "
            f"(tts={self.tts_backend}/{self.tts_model}, stt={self.stt_backend})"
        )

    # ------------------------------------------------------------------ #
    #  Speech-to-text                                                      #
    # ------------------------------------------------------------------ #

    async def transcribe_audio(self, audio_file_path: Path) -> str:
        if self.stt_backend == "openai":
            return await self._transcribe_openai(audio_file_path)
        if self.stt_backend == "gemini":
            return await self._transcribe_gemini(audio_file_path)
        raise ValueError("No STT backend configured")

    async def _transcribe_openai(self, audio_file_path: Path) -> str:
        from openai import OpenAI
        client = OpenAI(api_key=self._openai_key)
        logger.info(f"Transcribing with Whisper: {audio_file_path}")
        with open(audio_file_path, "rb") as f:
            transcript = client.audio.transcriptions.create(
                model=self.whisper_model, file=f, response_format="text"
            )
        logger.info(f"Transcription complete: {str(transcript)[:100]}")
        return transcript

    async def _transcribe_gemini(self, audio_file_path: Path) -> str:
        from google import genai as gai
        from google.genai import types as gtypes
        client = gai.Client(api_key=self._google_key)
        logger.info(f"Transcribing with Gemini multimodal: {audio_file_path}")
        audio_bytes = audio_file_path.read_bytes()
        suffix = audio_file_path.suffix.lstrip(".")
        mime = f"audio/{suffix}" if suffix else "audio/webm"
        resp = client.models.generate_content(
            model="gemini-1.5-flash",
            contents=[
                gtypes.Content(parts=[
                    gtypes.Part.from_text("Transcribe this audio exactly. Return only the transcript text, nothing else."),
                    gtypes.Part.from_bytes(data=audio_bytes, mime_type=mime),
                ])
            ],
        )
        text = resp.text or ""
        logger.info(f"Gemini transcription: {text[:100]}")
        return text.strip()

    # ------------------------------------------------------------------ #
    #  Text-to-speech                                                      #
    # ------------------------------------------------------------------ #

    async def synthesize_speech(
        self,
        text: str,
        output_path: Optional[Path] = None,
        voice: Optional[str] = None,
    ) -> Path:
        if self.tts_backend == "gemini":
            return await self._synthesize_gemini(text, output_path, voice)
        if self.tts_backend == "openai":
            return await self._synthesize_openai(text, output_path, voice)
        raise ValueError("No TTS backend configured")

    async def _synthesize_gemini(
        self,
        text: str,
        output_path: Optional[Path],
        voice: Optional[str],
    ) -> Path:
        from google import genai as gai
        from google.genai import types as gtypes

        client = gai.Client(api_key=self._google_key)
        voice_name = voice or self.tts_voice
        if not output_path:
            output_path = Path("temp_audio.wav")

        logger.info(f"Synthesizing with Gemini TTS (voice={voice_name}): {text[:100]}")

        config = gtypes.GenerateContentConfig(
            temperature=1,
            response_modalities=["audio"],
            speech_config=gtypes.SpeechConfig(
                voice_config=gtypes.VoiceConfig(
                    prebuilt_voice_config=gtypes.PrebuiltVoiceConfig(voice_name=voice_name)
                )
            ),
        )

        audio_chunks: list[bytes] = []
        last_mime = "audio/L16;rate=24000"

        for chunk in client.models.generate_content_stream(
            model=self.tts_model,
            contents=[gtypes.Content(role="user", parts=[gtypes.Part.from_text(text)])],
            config=config,
        ):
            if not chunk.parts:
                continue
            part = chunk.parts[0]
            if part.inline_data and part.inline_data.data:
                last_mime = part.inline_data.mime_type or last_mime
                audio_chunks.append(part.inline_data.data)

        raw = b"".join(audio_chunks)
        file_ext = mimetypes.guess_extension(last_mime) or ".wav"
        # Always write as WAV for broad compatibility
        wav_path = output_path.with_suffix(".wav")
        wav_data = _pcm_to_wav(raw, last_mime)
        wav_path.write_bytes(wav_data)
        logger.info(f"Gemini TTS saved: {wav_path} ({len(wav_data)} bytes)")
        return wav_path

    async def _synthesize_openai(
        self,
        text: str,
        output_path: Optional[Path],
        voice: Optional[str],
    ) -> Path:
        from openai import OpenAI
        client = OpenAI(api_key=self._openai_key)
        voice = voice or self.tts_voice
        if not output_path:
            output_path = Path("temp_audio.mp3")
        logger.info(f"Synthesizing with OpenAI TTS (voice={voice}): {text[:100]}")
        response = client.audio.speech.create(
            model=self.tts_model, voice=voice, input=text, response_format="mp3"
        )
        response.stream_to_file(str(output_path))
        logger.info(f"OpenAI TTS saved: {output_path}")
        return output_path

    # ------------------------------------------------------------------ #
    #  Voice list                                                          #
    # ------------------------------------------------------------------ #

    def get_available_voices(self) -> list:
        if self.tts_backend == "gemini":
            return GEMINI_VOICES
        return OPENAI_VOICES


# --------------------------------------------------------------------------- #
#  Singleton factory                                                           #
# --------------------------------------------------------------------------- #

_instance: Optional[VoiceProcessor] = None


def get_voice_processor() -> VoiceProcessor:
    global _instance
    if _instance is None:
        _instance = VoiceProcessor()
    return _instance
