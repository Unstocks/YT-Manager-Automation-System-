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
    featured_brand: str = ""
    strategic_moat: str = ""
    on_screen_text: List[str] = field(default_factory=list)
    spoken_dialogue: str = ""
    entities: List[str] = field(default_factory=list)
    intended_audience: str = "Founders, Entrepreneurs, Brand Builders, Operators"
    main_takeaway: str = ""
    category_id: str = "27"  # 27: Education (High-RPM Business, Strategy, Case Studies)
    category_name: str = "Education"
    language: str = "en"
    is_short: bool = True
    confidence: float = 1.0
    summary: str = ""
    is_fallback: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def clean_title_from_filename(filename: str) -> str:
    """Extracts a readable, capitalized topic phrase from a video filename, aggressively removing web scraper boilerplate."""
    stem = Path(filename).stem

    # 1. Strip transformed prefixes
    stem = re.sub(r'^(transformed_|masked_|cleaned_)+', '', stem, flags=re.IGNORECASE)

    # 2. Strip web scraper prefixes (Klickpin, Pinterest, TikTok, etc.)
    stem = re.sub(r'^(from\s*klickpin\.com[\s\-_]*|from\s*pinterest[\s\-_]*|pinterest[\s\-_]*)', '', stem, flags=re.IGNORECASE)

    # 3. Strip pin IDs and url slugs
    stem = re.sub(r'(-?pin-id-?\d*|-?[a-f0-9]{16,})', '', stem, flags=re.IGNORECASE)

    # 4. Strip boilerplate SEO sentences commonly appended by web scrapers
    stem = re.sub(r'(that are trending right now.*|with easy charm.*|for ideas worth saving.*|to spark your next plan.*)', '', stem, flags=re.IGNORECASE)

    # 5. Remove common file tags like clip_, batch_, test_, raw_, media_, numbers, hashes
    cleaned = re.sub(r'^(clip_?\d*|batch_?\d*|test_?\d*|media_?\d*|video_?\d*)[_\-\s]*', '', stem, flags=re.IGNORECASE)
    cleaned = re.sub(r'(_\d{8}_\d{6}|_[a-f0-9]{8,})', '', cleaned)

    # Replace delimiters with spaces
    words = re.split(r'[_\-\s\.]+', cleaned)
    words = [w.strip() for w in words if w.strip() and not w.isdigit() and len(w) > 1 and w.lower() not in {"com", "mp4", "mov", "mkv", "pin", "id", "klickpin"}]

    if not words or len(words) < 2:
        return "Business Strategy & Brand Growth"

    # Limit to first 6 meaningful words so we don't carry full paragraphs
    return " ".join(w.capitalize() for w in words[:6])


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
        headers = {
            "Content-Type": "application/json",
            "x-goog-api-key": self.api_key,
        }

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
                error_body = ""
                try:
                    error_body = he.read().decode("utf-8")
                except Exception:
                    pass

                is_transient = he.code in (429, 500, 502, 503, 504)
                if is_transient and attempt < max_attempts:
                    logger.warning(
                        f"Gemini API returned transient HTTP {he.code}: {he.reason}. "
                        f"Retrying in 2 seconds (attempt {attempt}/{max_attempts})..."
                    )
                    time.sleep(2)
                    continue

                if he.code == 402:
                    logger.error(
                        f"Gemini API HTTP 402 (Payment Required): Google AI Studio / Google Cloud project prepayment credits are depleted ($0.00). "
                        f"To fix: Create a 100% free API key in a new unbilled project at https://aistudio.google.com/apikey, or top up prepaid credits. Details: {error_body}"
                    )
                else:
                    logger.warning(f"Gemini API HTTP error {he.code}: {he.reason}. Details: {error_body}. Falling back to local analysis.")
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
        """Checks for accompanying .json or .txt sidecar metadata next to the video or in parent batch directories."""
        clean_name = video_path.name
        if clean_name.startswith("transformed_"):
            clean_name = clean_name[len("transformed_"):]

        search_locations = [
            video_path.with_suffix(".json"),
            video_path.with_suffix(".txt"),
            video_path.parent / Path(clean_name).with_suffix(".json"),
            video_path.parent / Path(clean_name).with_suffix(".txt"),
            video_path.parent.parent / Path(clean_name).with_suffix(".json"),
            video_path.parent.parent / Path(clean_name).with_suffix(".txt"),
        ]

        for cand in search_locations:
            if not cand.exists():
                continue
            if cand.suffix == ".json":
                try:
                    with open(cand, "r", encoding="utf-8") as f:
                        return json.load(f)
                except Exception:
                    pass
            elif cand.suffix == ".txt":
                try:
                    with open(cand, "r", encoding="utf-8") as f:
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
            featured_brand = sidecar.get("featured_brand", "")
            strategic_moat = sidecar.get("strategic_moat", "Distribution & Brand Moat")
            on_screen_text = sidecar.get("on_screen_text", [])
            spoken_dialogue = sidecar.get("spoken_dialogue", "")
            entities = sidecar.get("entities", [featured_brand or topic_from_name, "Unstocks", "Business Strategy"])
            audience = sidecar.get("intended_audience", "Founders, Entrepreneurs, Brand Builders, Operators")
            takeaway = sidecar.get("main_takeaway", sidecar.get("summary", f"Strategic business breakdown of {central_topic}."))
            cat_id = str(sidecar.get("category_id", "27"))
            cat_name = "Education"
            lang = sidecar.get("language", "en")
            summary = sidecar.get("summary", f"{subject}: {takeaway}")

            return ContentUnderstanding(
                subject=subject,
                central_topic=central_topic,
                featured_brand=featured_brand,
                strategic_moat=strategic_moat,
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
                is_fallback=False,
            )

        # 2. Attempt Gemini Multimodal Vision API if key is available
        if self.api_key:
            gemini_prompt = """
Analyze the provided video frames for a high-retention Business, Brand Strategy & Monetization YouTube Short.
Identify:
1. The exact Brand, Company, Founder, or Product featured (e.g. Nike, Zara, Apple, Red Bull, Starbucks, Airbnb, DS Group, Pulse, etc.).
2. The strategic mechanism or business lesson (e.g. pricing strategy, marketing psychology, distribution moat, zero-ad model, customer acquisition, viral loop).
3. Any visible on-screen text or headline.

Return a valid JSON object matching this schema:
{
  "featured_brand": "Name of the featured company or brand",
  "subject": "Concise main subject (3-6 words)",
  "central_topic": "Specific business topic (3-6 words)",
  "on_screen_text": ["Exact list of visible text snippets across frames"],
  "spoken_dialogue": "Any transcript or spoken dialogue if identifiable",
  "entities": ["List of key brands, companies, business terms, and founders"],
  "intended_audience": "Founders, Entrepreneurs, Brand Builders, Operators",
  "main_takeaway": "Direct strategic or business takeaway",
  "strategic_moat": "Core business moat (pricing, distribution, brand, retention, etc.)",
  "category_id": "27",
  "language": "en",
  "summary": "2-sentence factual business summary of what the clip shows"
}
CRITICAL ACCURACY RULE: Do NOT invent claims, numbers, facts, or quotes not visible in the frames.
"""
            res = self._call_gemini_vision(inspection, gemini_prompt)
            if res:
                cat_id = str(res.get("category_id", "27"))
                return ContentUnderstanding(
                    subject=res.get("subject", topic_from_name),
                    central_topic=res.get("central_topic", topic_from_name),
                    featured_brand=res.get("featured_brand", ""),
                    strategic_moat=res.get("strategic_moat", "Market Positioning"),
                    on_screen_text=res.get("on_screen_text", []),
                    spoken_dialogue=res.get("spoken_dialogue", ""),
                    entities=res.get("entities", [topic_from_name, "Unstocks"]),
                    intended_audience=res.get("intended_audience", "Founders, Entrepreneurs, Brand Builders, Operators"),
                    main_takeaway=res.get("main_takeaway", f"Core strategic growth principles for {topic_from_name}."),
                    category_id=cat_id,
                    category_name="Education",
                    language=res.get("language", "en"),
                    is_short=inspection.is_short,
                    confidence=0.95,
                    summary=res.get("summary", ""),
                    is_fallback=False,
                )

        # 3. Deterministic Local Fallback (Strictly Factual & Content-Grounded)
        format_str = "YouTube Shorts (9:16 vertical)" if inspection.is_short else "Standard Landscape (16:9)"
        audio_str = f"with {inspection.audio_codec} audio" if inspection.has_audio else "silent video"
        
        brand_guess = ""
        summary = (
            f"Business breakdown '{filename}' ({inspection.duration_seconds:.1f}s, {inspection.width}x{inspection.height}, "
            f"{format_str}, {audio_str}). Topic: {topic_from_name}."
        )

        takeaway = f"Strategic breakdown of {topic_from_name}."

        entities = [
            topic_from_name,
            "Unstocks",
        ]

        cat_id = "27"

        return ContentUnderstanding(
            subject=topic_from_name,
            central_topic=topic_from_name,
            featured_brand=brand_guess,
            strategic_moat="Brand Strategy & Market Positioning",
            on_screen_text=[],
            spoken_dialogue="",
            entities=entities,
            intended_audience="Founders, Entrepreneurs, Brand Builders, Operators",
            main_takeaway=takeaway,
            category_id=cat_id,
            category_name="Education",
            language="en",
            is_short=inspection.is_short,
            confidence=0.7,
            summary=summary,
            is_fallback=True,
        )
