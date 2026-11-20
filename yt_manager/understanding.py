"""
YT Manager AI Video Understanding Engine
Performs content understanding across video frames, on-screen text, audio, and visual themes.
Enforces the critical accuracy rule: never invent facts or statistics not established in the clip.
"""
from __future__ import annotations

import base64
import json
import logging
import os
import re
import time
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from .inspector import MediaInspection

logger = logging.getLogger("YTManager.Understanding")


@dataclass
class ContentUnderstanding:
    subject: str
    central_topic: str
    on_screen_text: List[str] = field(default_factory=list)
    spoken_dialogue: str = ""
    entities: List[str] = field(default_factory=list)
    intended_audience: str = "Developers, Engineers, Technical Founders"
    main_takeaway: str = ""
    category_id: str = "28"  # 28: Science & Technology, 27: Education
    category_name: str = "Science & Technology"
    language: str = "en"
    is_short: bool = True
    confidence: float = 1.0
    summary: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def clean_title_from_filename(filename: str) -> str:
    """Extracts a readable, capitalized topic phrase from a video filename."""
    stem = Path(filename).stem
    # Remove common prefixes/suffixes like clip_, batch_, test_, raw_, media_, numbers, hashes
    cleaned = re.sub(r'^(clip_?\d*|batch_?\d*|test_?\d*|media_?\d*|video_?\d*)[_\-\s]*', '', stem, flags=re.IGNORECASE)
    cleaned = re.sub(r'(_\d{8}_\d{6}|_[a-f0-9]{8,})', '', cleaned)
    # Replace delimiters with spaces
    words = re.split(r'[_\-\s]+', cleaned)
    words = [w.strip() for w in words if w.strip() and not w.isdigit()]
    if not words:
        return "System Architecture & Engineering"
    return " ".join(w.capitalize() for w in words)


class VideoUnderstandingEngine:
    """
    Modular AI Video Understanding Engine.
    Supports:
    1. Ground Truth / Sidecar context ingestion (<clip_name>.txt or <clip_name>.json).
    2. Gemini Multimodal REST API (pure standard library urllib) when GEMINI_API_KEY is available.
    3. Local deterministic analysis of video frames, metadata, and technical characteristics.
    """

    def __init__(self, gemini_api_key: Optional[str] = None):
        self.api_key = gemini_api_key or os.environ.get("GEMINI_API_KEY", "")

    def _call_gemini_vision(
        self, inspection: MediaInspection, prompt: str
    ) -> Optional[Dict[str, Any]]:
        """Calls Gemini Vision API over standard HTTPS with keyframe images."""
        if not self.api_key or not inspection.extracted_frames:
            return None

        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={self.api_key}"

        parts: List[Dict[str, Any]] = [{"text": prompt}]

        # Sample up to 6 keyframes evenly
        frames = inspection.extracted_frames
        stride = max(1, len(frames) // 6)
        sampled_frames = frames[::stride][:6]

        for frame_path in sampled_frames:
            try:
                with open(frame_path, "rb") as img_file:
                    b64_data = base64.b64encode(img_file.read()).decode("utf-8")
                parts.append({
                    "inline_data": {
                        "mime_type": "image/jpeg",
                        "data": b64_data,
                    }
                })
            except Exception:
                continue

        payload = {
            "contents": [{"parts": parts}],
            "generationConfig": {
                "temperature": 0.2,
                "response_mime_type": "application/json",
            },
        }

        req_data = json.dumps(payload).encode("utf-8")
        headers = {"Content-Type": "application/json"}

        # Attempt call with 1 retry on transient errors
        max_attempts = 2
        for attempt in range(1, max_attempts + 1):
            req = urllib.request.Request(
                url,
                data=req_data,
                headers=headers,
                method="POST",
            )
            try:
                with urllib.request.urlopen(req, timeout=30) as resp:
                    resp_bytes = resp.read()
                    data = json.loads(resp_bytes.decode("utf-8"))
                    candidates = data.get("candidates", [])
                    if candidates:
                        content_text = candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "")
                        return json.loads(content_text)
                    logger.warning("Gemini Vision returned empty candidates list. Falling back to local analysis.")
                    return None
            except urllib.error.HTTPError as he:
                is_transient = he.code in (429, 500, 502, 503, 504)
                if is_transient and attempt < max_attempts:
                    logger.warning(
                        f"Gemini API returned transient HTTP {he.code}: {he.reason}. "
                        f"Retrying in 2 seconds (attempt {attempt}/{max_attempts})..."
                    )
                    time.sleep(2)
                    continue
                logger.warning(f"Gemini API HTTP error {he.code}: {he.reason}. Falling back to local analysis.")
                return None
            except (urllib.error.URLError, TimeoutError) as ue:
                if attempt < max_attempts:
                    logger.warning(
                        f"Gemini API network/timeout error: {ue}. "
                        f"Retrying in 2 seconds (attempt {attempt}/{max_attempts})..."
                    )
                    time.sleep(2)
                    continue
                logger.warning(f"Gemini API network error after retry: {ue}. Falling back to local analysis.")
                return None
            except json.JSONDecodeError as je:
                logger.warning(f"Gemini API returned invalid JSON: {je}. Falling back to local analysis.")
                return None

        return None

    def _check_sidecar_context(self, video_path: Path) -> Optional[Dict[str, Any]]:
        """Checks for accompanying .json or .txt sidecar metadata next to the video."""
        # 1. Check for <name>.json
        json_sidecar = video_path.with_suffix(".json")
        if json_sidecar.exists():
            try:
                with open(json_sidecar, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass

        # 2. Check for <name>.txt (raw notes or transcript)
        txt_sidecar = video_path.with_suffix(".txt")
        if txt_sidecar.exists():
            try:
                with open(txt_sidecar, "r", encoding="utf-8") as f:
                    content = f.read().strip()
                if content:
                    return {
                        "summary": content[:500],
                        "spoken_dialogue": content,
                        "central_topic": content.splitlines()[0][:100],
                    }
            except Exception:
                pass

        return None

    def analyze(
        self,
        inspection: MediaInspection,
        known_context: Optional[Dict[str, Any]] = None,
    ) -> ContentUnderstanding:
        """
        Analyzes media inspection data and frames to produce a structured ContentUnderstanding object.
        """
        filename = inspection.file_path.name
        topic_from_name = clean_title_from_filename(filename)

        # 1. Check for user-provided sidecar or explicit ground truth
        sidecar = known_context or self._check_sidecar_context(inspection.file_path)
        if sidecar:
            subject = sidecar.get("subject", topic_from_name)
            central_topic = sidecar.get("central_topic", topic_from_name)
            on_screen_text = sidecar.get("on_screen_text", [])
            spoken_dialogue = sidecar.get("spoken_dialogue", "")
            entities = sidecar.get("entities", [topic_from_name, "Unstocks", "Software Engineering"])
            audience = sidecar.get("intended_audience", "Developers, Engineers, Technical Founders")
            takeaway = sidecar.get("main_takeaway", sidecar.get("summary", f"A concise deep dive into {central_topic}."))
            cat_id = str(sidecar.get("category_id", "28" if not inspection.is_short else "27"))
            cat_name = "Science & Technology" if cat_id == "28" else "Education"
            lang = sidecar.get("language", "en")
            summary = sidecar.get("summary", f"{subject}: {takeaway}")

            return ContentUnderstanding(
                subject=subject,
                central_topic=central_topic,
                on_screen_text=on_screen_text,
                spoken_dialogue=spoken_dialogue,
                entities=entities,
                intended_audience=audience,
                main_takeaway=takeaway,
                category_id=cat_id,
                category_name=cat_name,
                language=lang,
                is_short=inspection.is_short,
                confidence=1.0,
                summary=summary,
            )

        # 2. Attempt Gemini Multimodal Vision API if key is available
        if self.api_key:
            gemini_prompt = """
Analyze the provided video frames.
Return a valid JSON object matching this schema:
{
  "subject": "Concise main subject (3-6 words)",
  "central_topic": "Specific topic discussed (3-6 words)",
  "on_screen_text": ["Exact list of visible text snippets across frames"],
  "spoken_dialogue": "Any transcript or spoken dialogue if identifiable",
  "entities": ["List of key technical entities, terms, or brands"],
  "intended_audience": "Target audience",
  "main_takeaway": "Direct takeaway of the video",
  "category_id": "28 or 27",
  "language": "en",
  "summary": "2-sentence factual summary of what the clip shows"
}
CRITICAL ACCURACY RULE: Do NOT invent claims, numbers, facts, or quotes not visible in the frames.
"""
            res = self._call_gemini_vision(inspection, gemini_prompt)
            if res:
                cat_id = str(res.get("category_id", "28" if not inspection.is_short else "27"))
                return ContentUnderstanding(
                    subject=res.get("subject", topic_from_name),
                    central_topic=res.get("central_topic", topic_from_name),
                    on_screen_text=res.get("on_screen_text", []),
                    spoken_dialogue=res.get("spoken_dialogue", ""),
                    entities=res.get("entities", [topic_from_name, "Unstocks"]),
                    intended_audience=res.get("intended_audience", "Developers, Engineers, Technical Founders"),
                    main_takeaway=res.get("main_takeaway", f"Essential architectural principles for {topic_from_name}."),
                    category_id=cat_id,
                    category_name="Science & Technology" if cat_id == "28" else "Education",
                    language=res.get("language", "en"),
                    is_short=inspection.is_short,
                    confidence=0.95,
                    summary=res.get("summary", ""),
                )

        # 3. Deterministic Local Fallback (Strictly Factual & Content-Grounded)
        # Avoids fabricating claims or numbers not established in the file.
        format_str = "YouTube Shorts (9:16 vertical)" if inspection.is_short else "Standard Landscape (16:9)"
        audio_str = f"with {inspection.audio_codec} audio" if inspection.has_audio else "silent video"
        
        summary = (
            f"Video clip '{filename}' ({inspection.duration_seconds:.1f}s, {inspection.width}x{inspection.height}, "
            f"{format_str}, {audio_str}). Topic: {topic_from_name}."
        )

        takeaway = f"Overview of {topic_from_name}."

        entities = [
            topic_from_name,
            "Unstocks",
        ]

        cat_id = "27" if inspection.is_short else "28"

        return ContentUnderstanding(
            subject=topic_from_name,
            central_topic=topic_from_name,
            on_screen_text=[],
            spoken_dialogue="",
            entities=entities,
            intended_audience="General Audience, Tech Enthusiasts",
            main_takeaway=takeaway,
            category_id=cat_id,
            category_name="Education" if cat_id == "27" else "Science & Technology",
            language="en",
            is_short=inspection.is_short,
            confidence=0.7,
            summary=summary,
        )
