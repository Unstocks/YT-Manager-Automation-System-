"""
YT Manager Audio Transcription Engine
Uses system FFmpeg's built-in whisper.cpp filter to transcribe video audio locally,
100% offline with zero cloud tokens and zero API keys.
"""
from __future__ import annotations

import logging
import re
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("yt_manager.transcriber")


class AudioTranscriber:
    """
    Offline local speech transcription engine using FFmpeg whisper.cpp filter.
    Requires ggml-tiny.bin or ggml-base.bin placed in models/ directory.
    """

    def __init__(self, models_dir: Optional[Path] = None):
        base_dir = Path(__file__).resolve().parent.parent
        self.models_dir = models_dir or (base_dir / "models")
        self.preferred_model = self._find_model()

    def _find_model(self) -> Optional[Path]:
        """Finds the best available whisper model in models_dir."""
        if not self.models_dir.exists():
            return None
        # Priority order: tiny -> base -> small
        for name in ("ggml-tiny.bin", "ggml-base.bin", "ggml-small.bin"):
            candidate = self.models_dir / name
            if candidate.exists() and candidate.stat().st_size > 1024 * 1024:
                return candidate
        # Any .bin in models_dir
        for cand in self.models_dir.glob("*.bin"):
            if cand.stat().st_size > 1024 * 1024:
                return cand
        return None

    def is_available(self) -> bool:
        """Returns True if a local whisper model is present."""
        return self._find_model() is not None

    def extract_audio(self, video_path: Path, output_wav: Path, duration_sec: int = 60) -> bool:
        """Extracts 16kHz mono 16-bit PCM WAV for transcription (fast, 0.1s)."""
        cmd = [
            "ffmpeg",
            "-y",
            "-i",
            str(video_path),
            "-vn",
            "-ss",
            "0",
            "-t",
            str(duration_sec),
            "-ar",
            "16000",
            "-ac",
            "1",
            "-c:a",
            "pcm_s16le",
            str(output_wav),
        ]
        try:
            res = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, timeout=15)
            return res.returncode == 0 and output_wav.exists() and output_wav.stat().st_size > 500
        except Exception as e:
            logger.warning(f"Audio extraction failed for {video_path.name}: {e}")
            return False

    def transcribe_with_ffmpeg_whisper(
        self, audio_wav: Path, output_txt: Path
    ) -> Optional[str]:
        """Runs FFmpeg's built-in whisper filter against audio_wav."""
        model_path = self._find_model()
        if not model_path:
            logger.warning("No whisper model found in models/ directory.")
            return None

        # Format path for FFmpeg filter argument (escape backslashes and colons on Windows)
        safe_model_path = str(model_path).replace("\\", "/").replace(":", "\\:")
        safe_dest_path = str(output_txt).replace("\\", "/").replace(":", "\\:")

        cmd = [
            "ffmpeg",
            "-y",
            "-i",
            str(audio_wav),
            "-af",
            f"whisper=model={safe_model_path}:destination={safe_dest_path}:format=text:language=en",
            "-f",
            "null",
            "-",
        ]
        try:
            subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, timeout=30)
            if output_txt.exists():
                text = output_txt.read_text(encoding="utf-8", errors="ignore").strip()
                if text:
                    logger.info(f"Local Whisper transcription successful: '{text[:80]}...'")
                    return text
        except Exception as e:
            logger.warning(f"FFmpeg whisper transcription failed: {e}")

        return None

    def transcribe(self, video_path: Path, work_dir: Optional[Path] = None) -> Optional[str]:
        """
        Extracts audio and transcribes it locally.
        Returns spoken transcript text or None if model missing / silent.
        """
        work = work_dir or video_path.parent
        audio_wav = work / f"{video_path.stem}_audio.wav"
        output_txt = work / f"{video_path.stem}_transcript.txt"

        if not self.extract_audio(video_path, audio_wav):
            return None

        return self.transcribe_with_ffmpeg_whisper(audio_wav, output_txt)

    def parse_transcript_into_context(self, transcript: str) -> Dict[str, Any]:
        """
        Parses raw spoken speech into structured business metadata:
        identifies key entities, hooks, topics, and takeaways.
        """
        text = transcript.strip()
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        cleaned = " ".join(lines)

        # Detect prominent business entities and founders
        entity_patterns = {
            "Elon Musk": [r"\belon\b", r"\bmusk\b", r"\btesla\b", r"\bspacex\b"],
            "Starbucks": [r"\bstarbucks\b", r"\bhoward schultz\b", r"\bthird place\b"],
            "Ferrari": [r"\bferrari\b", r"\benzo\b"],
            "Toyota": [r"\btoyota\b", r"\bhilux\b"],
            "Steve Jobs": [r"\bsteve jobs\b", r"\bapple\b"],
            "Warren Buffett": [r"\bwarren buffett\b", r"\bbuffett\b", r"\bberkshire\b"],
            "Jeff Bezos": [r"\bbezos\b", r"\bamazon\b"],
            "Bernard Arnault": [r"\bbernard arnault\b", r"\blvmh\b", r"\blouis vuitton\b"],
            "Competitor Intelligence": [r"\bcompetitor\b", r"\bcompetitors\b", r"\banalyse\b", r"\bseo\b"],
            "Sales & Negotiation": [r"\bdeposit\b", r"\bnegotiat\b", r"\bclosing\b", r"\bclients?\b"],
        }

        detected_entities: List[str] = []
        featured_brand = ""
        for brand, patterns in entity_patterns.items():
            for pat in patterns:
                if re.search(pat, cleaned, re.IGNORECASE):
                    detected_entities.append(brand)
                    if not featured_brand:
                        featured_brand = brand
                    break

        # Fallback entity
        if not detected_entities:
            detected_entities = ["Business Strategy", "Unstocks"]

        # Topic & Hook determination
        first_sentence = lines[0] if lines else cleaned[:80]
        hook = first_sentence[:80]

        return {
            "subject": featured_brand or hook,
            "central_topic": f"{featured_brand or 'Business Strategy'}: {hook}",
            "featured_brand": featured_brand,
            "strategic_moat": "Brand Identity & Execution Moat",
            "spoken_dialogue": cleaned,
            "entities": detected_entities + ["Unstocks"],
            "intended_audience": "Founders, Brand Builders, Operators, Marketers",
            "main_takeaway": cleaned[:120] if len(cleaned) <= 120 else f"{cleaned[:117]}...",
            "category_id": "27",
            "language": "en",
            "confidence": 0.95,
        }
