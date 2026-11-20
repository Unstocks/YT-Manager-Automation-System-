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
from typing import Any, Dict, List, Optional

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
        Generates a search-friendly, high-CTR, non-clickbait YouTube title (< 80 chars).
        Uses strong opening keywords directly related to the actual topic.
        """
        subject = understanding.subject.strip()
        topic = understanding.central_topic.strip()
        is_short = understanding.is_short

        # Choose primary phrase
        primary = topic if topic and len(topic) <= 45 else subject
        if len(primary) > 45:
            primary = primary[:45].rsplit(" ", 1)[0]

        if is_short:
            # YouTube Shorts format: Punchy Hook | Context #Shorts
            title = f"{primary}: Core Architecture Guide #Shorts"
            if len(title) > 75:
                title = f"{primary} #Shorts"
        else:
            # Standard video: High intent search format
            title = f"How {primary} Works | System Architecture Deep Dive"
            if len(title) > 90:
                title = f"{primary} Explained"

        return title.strip()

    def _generate_description(
        self,
        understanding: ContentUnderstanding,
        title: str,
    ) -> Tuple[str, List[str]]:
        """
        Generates a 6-tier structured YouTube description reflecting the actual clip.
        """
        subject = understanding.subject
        topic = understanding.central_topic
        summary = understanding.summary
        takeaway = understanding.main_takeaway
        is_short = understanding.is_short

        # 1. Compelling opening hook sentence
        opening_hook = f"Mastering {topic.lower()} is essential for building scalable, high-conviction engineering systems."

        # 2. Concise explanation of the video
        explanation = (
            f"In this {'Short' if is_short else 'video'}, we break down the core mechanics of {topic.lower()}. "
            f"{takeaway}"
        )

        # 3. Relevant search keywords naturally incorporated
        keywords_context = (
            f"Key technical areas covered:\n"
            f"• Core implementation principles for {topic.lower()}\n"
            f"• Architecture tradeoffs and decision-making patterns\n"
            f"• Engineering durability and technical debt mitigation"
        )

        # 4. Additional context
        additional_context = (
            f"Whether you are designing production backend services or optimizing developer workflows, "
            f"mastering these foundational patterns ensures long-term Lindy durability."
        )

        # 5. Relevant Call to Action
        cta = (
            f"📌 About Unstocks:\n"
            f"Unstocks provides curated digital blueprints and execution engines to turn high-conviction ideas "
            f"into durable software deliverables.\n\n"
            f"👉 Subscribe to @unstocks for more architecture blueprints and systems engineering breakdowns.\n"
            f"🌐 Channel: {self.config.channel_url}"
        )

        # 6. Relevant Hashtags
        # Clean entity words for hashtags
        clean_entities = []
        for e in understanding.entities:
            clean = re.sub(r'[^a-zA-Z0-9]', '', e)
            if clean and len(clean) >= 3 and clean.lower() not in [c.lower() for c in clean_entities]:
                clean_entities.append(clean)

        hashtags = clean_entities[:3]
        if "SoftwareEngineering" not in hashtags and len(hashtags) < 4:
            hashtags.append("SoftwareEngineering")
        if "SystemDesign" not in hashtags and len(hashtags) < 4:
            hashtags.append("SystemDesign")
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
            additional_context,
            "",
            cta,
            "",
            hashtags_formatted,
        ]

        description = "\n".join(description_parts)
        return description, hashtags

    def _generate_tags(self, understanding: ContentUnderstanding) -> List[str]:
        """Generates focused, high-relevance YouTube tags under 500 characters total."""
        tags = []
        
        # Add primary entities and topic
        if understanding.central_topic:
            tags.append(understanding.central_topic.lower())
        if understanding.subject and understanding.subject.lower() != understanding.central_topic.lower():
            tags.append(understanding.subject.lower())

        for ent in understanding.entities:
            ent_clean = ent.strip().lower()
            if ent_clean and ent_clean not in tags:
                tags.append(ent_clean)

        # Relevant niche terms
        standard_terms = [
            "software architecture",
            "system design",
            "developer productivity",
            "technical decision making",
            "unstocks",
            "engineering leadership",
        ]
        for term in standard_terms:
            if term not in tags:
                tags.append(term)

        if understanding.is_short:
            tags.extend(["shorts", "tech shorts", "youtube shorts"])

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
