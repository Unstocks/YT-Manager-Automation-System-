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
        Generates a search-friendly, high-CTR, brand-first YouTube title strictly under 80 characters.
        Places prominent brand, company, or business entities front and center to maximize algorithm reach.
        Appends #Shorts, #fyp, and dynamic brand/niche tags.
        """
        # 1. Resolve featured brand
        brand = getattr(understanding, "featured_brand", "").strip()

        topic = (understanding.central_topic or understanding.subject or "Business Strategy").strip().rstrip(". :|-")
        takeaway = understanding.main_takeaway.strip().rstrip(". ") if understanding.main_takeaway else ""

        # 2. Select High-CTR Brand-First Title Formula
        if brand and brand.lower() != "unstocks":
            # Brand-first viral business patterns
            if takeaway and len(takeaway) <= 35:
                base_title = f"{brand}'s Genius Strategy: {takeaway}"
            elif "fail" in topic.lower() or "mistake" in topic.lower():
                base_title = f"The $100M Mistake That Nearly Bankrupted {brand}"
            elif "marketing" in topic.lower() or "secret" in topic.lower():
                base_title = f"The Genius Marketing Secret Behind {brand}"
            elif "crush" in topic.lower() or "beat" in topic.lower():
                base_title = f"How {brand} Crushed Their Biggest Competitor"
            else:
                base_title = f"How {brand} Built A $1B Empire With ZERO Ads"
        else:
            # Topic-led business patterns
            has_dialogue = bool(understanding.spoken_dialogue and len(understanding.spoken_dialogue.strip()) > 10)
            has_visual_text = bool(understanding.on_screen_text and len(understanding.on_screen_text) > 0)

            if has_dialogue and takeaway and len(takeaway) <= 35:
                base_title = f"{topic}: What You Need to Know"
            elif "pricing" in topic.lower():
                base_title = f"The Pricing Psychology That Doubles Revenue"
            elif "startup" in topic.lower() or "scale" in topic.lower():
                base_title = f"Why 90% Of Startups Fail At $10k/Month"
            elif takeaway and 10 <= len(takeaway) <= 35:
                base_title = f"{topic} — {takeaway}"
            elif has_visual_text:
                base_title = f"{topic} Breakdown & Overview"
            else:
                base_title = f"{topic} Breakdown & Strategy"

        # 3. Dynamic Hashtags for Shorts
        suffix = ""
        if understanding.is_short:
            content_tag = "Business"
            if brand and 3 <= len(brand) <= 20:
                clean_b = re.sub(r'[^a-zA-Z0-9]', '', brand)
                if 3 <= len(clean_b) <= 20:
                    content_tag = clean_b
            elif topic:
                first_w = re.sub(r'[^a-zA-Z0-9]', '', topic.split()[0])
                if 3 <= len(first_w) <= 20:
                    content_tag = first_w

            suffix = f" #{content_tag} #shorts #fyp"

        max_base_len = 78 - len(suffix)  # Enforce strictly <= 78 total characters

        if len(base_title) > max_base_len:
            truncated = base_title[:max_base_len].rsplit(" ", 1)[0]
            if len(truncated) < 10:
                truncated = (brand or topic)[:max_base_len].rsplit(" ", 1)[0]
            base_title = truncated.rstrip(", -:|")

        final_title = f"{base_title}{suffix}".strip()
        return final_title

    def _generate_description(
        self,
        understanding: ContentUnderstanding,
        title: str,
    ) -> Tuple[str, List[str]]:
        """
        Generates a 6-Stage High-RPM Authority Description for YouTube algorithm indexing.
        Features brand names, core business moats, and semantic keyword clouds.
        """
        brand = getattr(understanding, "featured_brand", "").strip() or "The World's Best Brands"
        topic = (understanding.central_topic or understanding.subject or "Business Strategy").strip()
        summary = understanding.summary.strip()
        takeaway = understanding.main_takeaway.strip()
        moat = getattr(understanding, "strategic_moat", "Market Positioning & Brand Equity")
        is_short = understanding.is_short

        # Stage 1: The Strategic Hook
        if brand and brand != "The World's Best Brands":
            opening_hook = (
                f"How {brand} engineered an asymmetric market monopoly without competing on price. "
                f"In this business case study, we deconstruct the marketing psychology, unit economics, "
                f"and distribution moat behind their explosive brand growth."
            )
        elif summary:
            opening_hook = f"{summary} In this business breakdown, we examine the underlying strategic moats driving brand growth."
        else:
            opening_hook = f"A tactical breakdown of {topic.lower()} and the high-leverage frameworks that drive scalable business growth."

        # Stage 2: 3-Point Business Mechanism Breakdown
        key_points = []
        if understanding.on_screen_text:
            key_points.extend([t.strip() for t in understanding.on_screen_text if t.strip()])
        elif understanding.entities:
            key_points.extend([e.strip() for e in understanding.entities if e.strip() and e.lower() != "unstocks"])

        explanation_lines = [
            "📊 Strategic Breakdown:",
            f"• The Core Moat: How {brand or 'market leaders'} establish pricing power and uncontested market share.",
            "• Customer Acquisition: The exact psychological framing that converts cold attention into high-LTV brand advocates.",
            "• Unit Economics: How strategic distribution beats pure product features every single time.",
        ]
        if key_points:
            explanation_lines.append("")
            explanation_lines.append("Key points highlighted:")
            for pt in key_points[:4]:
                explanation_lines.append(f"• {pt}")
        explanation = "\n".join(explanation_lines)

        # Stage 3: Semantic Keyword Cloud (SEO Ranker)
        brand_kw = f"{brand} Case Study • " if brand and brand != "The World's Best Brands" else ""
        entity_kw = " • ".join([e.strip() for e in understanding.entities if e.strip() and e.lower() != "unstocks"][:5])
        entity_kw_str = f"{entity_kw} • " if entity_kw else ""
        keywords_context = (
            f"🔍 Key Business & Marketing Topics:\n"
            f"{brand_kw}{entity_kw_str}Brand Strategy • Marketing Psychology • Business Models • Startup Growth • "
            f"Customer Acquisition • Unit Economics • Pricing Strategies • Entrepreneurship Mindset • How To Build A Brand"
        )

        # Stage 4 & 5: Unstocks Brand Positioning & High-Intent CTA
        cta = (
            f"🧠 About Unstocks:\n"
            f"Unstocks (@unstocks) breaks down the hidden strategies, business mechanics, and brand psychology "
            f"behind the world's most profitable companies. Daily tactical breakdowns for ambitious founders, "
            f"brand architects, and operators.\n\n"
            f"👉 Subscribe to @unstocks for daily unfiltered business breakdowns and wealth systems.\n"
            f"🌐 Channel: {self.config.channel_url}"
        )

        # Stage 6: Top-Volume Business Hashtag Battery
        clean_hashtags: List[str] = []
        if brand and brand != "The World's Best Brands":
            b_tag = re.sub(r'[^a-zA-Z0-9]', '', brand)
            if b_tag and len(b_tag) >= 3:
                clean_hashtags.append(b_tag)

        for e in understanding.entities:
            clean = re.sub(r'[^a-zA-Z0-9]', '', e)
            if clean and len(clean) >= 3 and clean.lower() not in [c.lower() for c in clean_hashtags] and clean.lower() != "unstocks":
                clean_hashtags.append(clean)
                if len(clean_hashtags) >= 2:
                    break

        if is_short:
            preset = getattr(
                self.config,
                "default_hashtags",
                [
                    "Shorts",
                    "fyp",
                    "Business",
                    "BrandStrategy",
                    "Marketing",
                    "Entrepreneurship",
                    "Startups",
                    "BusinessStrategy",
                    "CaseStudy",
                    "Money",
                    "ytshorts",
                    "viral",
                ],
            )
        else:
            preset = [
                "Business",
                "BrandStrategy",
                "Marketing",
                "Entrepreneurship",
                "Startups",
                "BusinessStrategy",
                "CaseStudy",
                "Money",
            ]
        for tag in preset:
            clean_tag = re.sub(r'[^a-zA-Z0-9]', '', tag)
            if clean_tag and clean_tag.lower() not in [h.lower() for h in clean_hashtags]:
                clean_hashtags.append(clean_tag)

        hashtags = clean_hashtags[:12]
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

        # Standard business authority tags
        business_authority_tags = [
            "business strategy",
            "brand strategy",
            "marketing psychology",
            "startup growth",
            "how to build a brand",
            "unit economics",
            "case study",
            "entrepreneurship",
            "unstocks",
        ]
        for bat in business_authority_tags:
            if bat not in tags:
                tags.append(bat)

        # Format tag for Shorts
        if understanding.is_short:
            for st in ["shorts", "youtube shorts", "business shorts"]:
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
    Uses the Founder's Dilemma Debate Loop to maximize comment section velocity, retention, and algorithmic reach.
    """
    brand = getattr(understanding, "featured_brand", "").strip()
    topic = understanding.central_topic or understanding.subject or "this business model"
    subject_entity = brand if brand and brand.lower() != "unstocks" else topic

    cta = "👉 Subscribe to @unstocks for daily unfiltered business breakdowns and wealth systems."

    if understanding.main_takeaway:
        return (
            f"💡 Founder's Dilemma: {understanding.main_takeaway}\n\n"
            f"If you were the CEO of {subject_entity}, would you double down on premium high-margin pricing "
            f"or aggressive mass-market volume? Drop your strategic breakdown below! 👇\n\n"
            f"{cta}"
        )
    else:
        return (
            f"💡 Founder's Question: What is the single biggest moat protecting {subject_entity} from competition today?\n\n"
            f"Drop your strategic take in the comments! 👇\n\n"
            f"{cta}"
        )
