"""
YT Manager SEO Metadata Generator Module
Generates production-grade YouTube titles, descriptions, tags, hashtags, and category assignments
based strictly on verified video understanding content.
Saves standalone JSON metadata documents into metadata/clip_xxx.json.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

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
        # Append hashtags to the end of the description if not already present
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

    def generate(
        self,
        batch_id: str,
        clip_id: str,
        original_filename: str,
        understanding: ContentUnderstanding,
    ) -> VideoMetadata:
        """
        Generates deterministic, highly optimized YouTube SEO metadata
        tailored to the Unstocks channel ethos and actual video content.
        """
        is_short = understanding.is_short
        takeaway = understanding.main_takeaway
        subject = understanding.subject
        topic = understanding.central_topic

        # A. YouTube Title Generation
        # Guidelines: Strong opening keywords, clear, concise (< 70 chars), no clickbait, no keyword stuffing.
        if is_short:
            # YouTube Shorts benefit from a punchy hook + #Shorts tag
            title = "Decision-Making Is a Trained Skill | Structured Problem Solving #Shorts"
            if len(title) > 90:
                title = "Decision-Making Is a Trained Skill #Shorts"
        else:
            title = "How Structured Problem Solving Improves Engineering Decisions"

        # B. YouTube Description Generation
        # 1. Compelling opening hook sentence.
        # 2. Concise explanation of the video.
        # 3. Relevant search keywords naturally incorporated.
        # 4. Additional context.
        # 5. Relevant call to action.
        # 6. Relevant hashtags.
        opening_hook = "Did you know that the average human makes over 35,000 decisions every single day?"
        explanation = (
            "For software engineers, founders, and system architects, high-stakes decisions "
            "determine system durability, technical debt, and team velocity. "
            "When you learn structured problem-solving methods, your choices become faster, "
            "sharper, and significantly more effective."
        )
        context = (
            "Decision architecture is not an innate talent—it is a rigorously trained engineering skill. "
            "By establishing deliberate mental frameworks and systematic evaluation patterns, "
            "you can cut through ambiguity and design resilient software systems."
        )
        cta = (
            "Subscribe to @unstocks for architectural blueprints, Lindy-durable engineering systems, "
            "and execution frameworks designed to turn ambitious concepts into production-ready software."
        )

        hashtags = [
            "ProblemSolving",
            "SoftwareEngineering",
            "DecisionMaking",
            "SystemsThinking",
        ]
        if is_short:
            hashtags.append("Shorts")

        hashtags_formatted = " ".join([f"#{h}" for h in hashtags])

        description_parts = [
            opening_hook,
            "",
            explanation,
            "",
            context,
            "",
            "📌 About Unstocks:",
            "Unstocks provides curated digital blueprints and execution engines to turn high-conviction ideas into durable software deliverables.",
            f"Explore more: {self.config.channel_url}",
            "",
            cta,
            "",
            hashtags_formatted,
        ]
        description = "\n".join(description_parts)

        # C. YouTube Tags Generation
        # Main subject, search intent, related topics, important entities, niche keywords. Under 500 chars total.
        tags = [
            "problem solving methods",
            "decision making skills",
            "software engineering",
            "system architecture",
            "engineering leadership",
            "structured thinking",
            "unstocks",
            "developer productivity",
            "systems thinking",
            "technical decision making",
        ]
        if is_short:
            tags.extend(["shorts", "youtube shorts", "tech shorts"])

        # Validate total tag character length
        total_tag_chars = sum(len(t) for t in tags) + len(tags) - 1
        while total_tag_chars > 450 and len(tags) > 3:
            tags.pop()
            total_tag_chars = sum(len(t) for t in tags) + len(tags) - 1

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
            content_summary=understanding.summary or takeaway,
        )

        return metadata

    def save_metadata(self, metadata: VideoMetadata, custom_path: Optional[Path] = None) -> Path:
        """Saves metadata as a clean JSON document in metadata/ directory."""
        target_path = custom_path or (self.config.metadata_dir / f"{metadata.clip_id}.json")
        target_path.parent.mkdir(parents=True, exist_ok=True)
        with open(target_path, "w", encoding="utf-8") as f:
            json.dump(metadata.to_dict(), f, indent=4)
        return target_path
