"""
YT Manager SEO Metadata Generator Module
Generates production-grade YouTube titles, descriptions, tags, hashtags, and category assignments
based strictly on verified video understanding content.
Saves standalone JSON metadata documents into metadata/clip_xxx.json.
"""
from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .config import YTManagerConfig
from .understanding import ContentUnderstanding


@dataclass
class VideoMetadata:
    batch_id: str
    clip_id: str
    original_filename: str
    title: str
    description: str
    tags: List[str]
    hashtags: List[str]
    category_id: str
    language: str
    content_summary: str
    generation_timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def to_youtube_snippet_payload(self) -> Dict[str, Any]:
        """Formats the metadata into YouTube Data API v3 snippet format."""
        desc_with_tags = self.description.strip()
        tags_str = " ".join(f"#{h.lstrip('#')}" for h in self.hashtags)
        if tags_str and tags_str not in desc_with_tags:
            desc_with_tags += f"\n\n{tags_str}"

        return {
            "title": self.title[:100],  # YouTube max 100 chars
            "description": desc_with_tags[:5000],  # YouTube max 5000 chars
            "tags": [t.strip() for t in self.tags if t.strip()][:50],  # Max 50 tags
            "categoryId": str(self.category_id),
            "defaultLanguage": self.language,
        }


class SEOMetadataGenerator:
    def __init__(self, config: YTManagerConfig):
        self.config = config

    def _generate_title(self, understanding: ContentUnderstanding) -> str:
        """
        Generates a search-friendly, high-CTR, non-clickbait YouTube title strictly under 80 characters.
        Dynamically adapts structure based on content attributes (spoken dialogue, on-screen text, key takeaways).
        Appends #Shorts strictly when is_short is True.
        """
        topic = (understanding.central_topic or understanding.subject or "Technical Guide").strip()
        topic = topic.rstrip(". :|-")
        
        has_dialogue = bool(understanding.spoken_dialogue and len(understanding.spoken_dialogue.strip()) > 10)
        has_visual_text = bool(understanding.on_screen_text and len(understanding.on_screen_text) > 0)
        takeaway = understanding.main_takeaway.strip().rstrip(". ") if understanding.main_takeaway else ""

        # Dynamic title variation based on content characteristics
        if has_dialogue and takeaway:
            base_title = f"{topic}: What You Need to Know"
        elif has_visual_text:
            base_title = f"{topic} Breakdown & Overview"
        elif takeaway and 10 <= len(takeaway) <= 40:
            base_title = f"{topic} — {takeaway}"
        else:
            base_title = f"{topic} Explained"

        suffix = " #Shorts" if understanding.is_short else ""
        max_base_len = 78 - len(suffix)  # Guarantees final title length <= 78 (< 80 chars)

        if len(base_title) > max_base_len:
            truncated = base_title[:max_base_len].rsplit(" ", 1)[0]
            if len(truncated) < 10:
                truncated = topic[:max_base_len].rsplit(" ", 1)[0]
            base_title = truncated.rstrip(", -:|")

        final_title = f"{base_title}{suffix}".strip()
        return final_title

    def _generate_description(
        self,
        understanding: ContentUnderstanding,
        title: str,
    ) -> Tuple[str, List[str]]:
        """
        Generates a structured YouTube description reflecting the actual clip content.
        Uses summary, main_takeaway, on_screen_text, and extracted entities.
        """
        topic = (understanding.central_topic or understanding.subject or "Technology").strip()
        summary = understanding.summary.strip()
        takeaway = understanding.main_takeaway.strip()
        is_short = understanding.is_short

        # 1. Opening hook derived from actual content
        if summary and takeaway and takeaway not in summary:
            opening_hook = f"{summary} {takeaway}"
        elif summary:
            opening_hook = summary
        elif takeaway:
            opening_hook = f"In this breakdown, we examine {topic.lower()}: {takeaway}"
        else:
            opening_hook = f"A concise breakdown of {topic.lower()}."

        # 2. Key takeaways and content explanation
        explanation_lines = []
        if takeaway and takeaway not in opening_hook:
            explanation_lines.append(f"Key Takeaway: {takeaway}")
        if understanding.on_screen_text:
            key_points = [t.strip() for t in understanding.on_screen_text[:4] if t.strip()]
            if key_points:
                explanation_lines.append("Key points highlighted:")
                for pt in key_points:
                    explanation_lines.append(f"• {pt}")
        explanation = "\n".join(explanation_lines) if explanation_lines else f"Exploring the core details and practical applications of {topic.lower()}."

        # 3. Dynamic keywords / topics covered derived from actual entities
        entity_items = [e.strip() for e in understanding.entities if e.strip() and e.lower() != "unstocks"]
        if entity_items:
            keywords_context = "Topics covered in this clip:\n" + "\n".join(f"• {e}" for e in entity_items[:6])
        else:
            keywords_context = f"Topic covered: {topic}"

        # 4. Relevant Call to Action
        cta = (
            f"📌 About Unstocks:\n"
            f"Unstocks provides curated digital blueprints and execution engines to turn high-conviction ideas "
            f"into durable software deliverables.\n\n"
            f"👉 Subscribe to @unstocks for more insights and breakdowns.\n"
            f"🌐 Channel: {self.config.channel_url}"
        )

        # 5. Hashtags derived from actual entities
        clean_hashtags: List[str] = []
        for e in understanding.entities:
            clean = re.sub(r'[^a-zA-Z0-9]', '', e)
            if clean and len(clean) >= 3 and clean.lower() not in [c.lower() for c in clean_hashtags]:
                clean_hashtags.append(clean)

        hashtags = clean_hashtags[:3]
        if "Unstocks" not in hashtags and len(hashtags) < 4:
            hashtags.append("Unstocks")
        if is_short and "Shorts" not in hashtags:
            hashtags.append("Shorts")

        hashtags_formatted = " ".join([f"#{h}" for h in hashtags])

        description_parts = [
            opening_hook,
            "",
            explanation,
            "",
            keywords_context,
            "",
            cta,
            "",
            hashtags_formatted,
        ]

        description = "\n".join(description_parts).strip()
        return description, hashtags

    def _generate_tags(self, understanding: ContentUnderstanding) -> List[str]:
        """Generates focused, high-relevance YouTube tags under 500 characters total."""
        tags: List[str] = []

        # Add primary topic and subject
        if understanding.central_topic:
            t = understanding.central_topic.strip().lower()
            if t and t not in tags:
                tags.append(t)
        if understanding.subject:
            s = understanding.subject.strip().lower()
            if s and s not in tags:
                tags.append(s)

        # Add content-specific entities
        for ent in understanding.entities:
            ent_clean = ent.strip().lower()
            if ent_clean and ent_clean not in tags:
                tags.append(ent_clean)

        # Include on-screen text phrases if short and informative
        for text in understanding.on_screen_text:
            cleaned_text = text.strip().lower()
            if 3 <= len(cleaned_text) <= 30 and cleaned_text not in tags:
                tags.append(cleaned_text)

        # Standard channel tag
        if "unstocks" not in tags:
            tags.append("unstocks")

        # Format tag for Shorts
        if understanding.is_short:
            for st in ["shorts", "youtube shorts"]:
                if st not in tags:
                    tags.append(st)

        # Enforce YouTube 500 characters limit
        result_tags: List[str] = []
        total_len = 0
        for tag in tags:
            tag_len = len(tag) + 1  # tag + comma
            if total_len + tag_len <= 450 and len(result_tags) < 40:
                result_tags.append(tag)
                total_len += tag_len

        return result_tags

    def generate(
        self,
        batch_id: str,
        clip_id: str,
        original_filename: str,
        understanding: ContentUnderstanding,
    ) -> VideoMetadata:
        """
        Generates deterministic, highly optimized YouTube SEO metadata
        tailored to the actual video content.
        """
        title = self._generate_title(understanding)
        description, hashtags = self._generate_description(understanding, title)
        tags = self._generate_tags(understanding)

        metadata = VideoMetadata(
            batch_id=batch_id,
            clip_id=clip_id,
            original_filename=original_filename,
            title=title,
            description=description,
            tags=tags,
            hashtags=hashtags,
            category_id=understanding.category_id or self.config.default_category_id,
            language=understanding.language or self.config.default_language,
            content_summary=understanding.summary or understanding.main_takeaway,
        )

        return metadata

    def save_metadata(self, metadata: VideoMetadata, custom_path: Optional[Path] = None) -> Path:
        """Saves metadata as a clean JSON document in metadata/ directory."""
        target_path = custom_path or (self.config.metadata_dir / f"{metadata.clip_id}.json")
        target_path.parent.mkdir(parents=True, exist_ok=True)
        with open(target_path, "w", encoding="utf-8") as f:
            json.dump(metadata.to_dict(), f, indent=4)
        return target_path


def generate_creator_comment(understanding: ContentUnderstanding) -> str:
    """
    Generates a high-engagement creator first-comment for YouTube algorithm distribution.
    Prompts viewers with a content-specific question and includes the channel subscription CTA.
    """
    topic = understanding.central_topic or understanding.subject or "this topic"
    cta = "👉 Subscribe to @unstocks for daily engineering breakdowns and system architecture deep dives!"
    if understanding.main_takeaway:
        return f"💡 Key Takeaway: {understanding.main_takeaway}\n\nWhat's your take on {topic.lower()}? Drop your thoughts below!\n\n{cta}"
    else:
        return f"💡 What are your thoughts on {topic.lower()}? Share your perspective in the comments below!\n\n{cta}"
