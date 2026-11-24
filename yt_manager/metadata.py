"""
YT Manager SEO Metadata Generator Module
Generates production-grade YouTube titles, descriptions, tags, hashtags, and category assignments
based strictly on verified video understanding content.
Saves standalone JSON metadata documents into metadata/clip_xxx.json.
"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .config import YTManagerConfig
from .understanding import ContentUnderstanding


def classify_narrative_pillar(
    brand: str, topic: str, dialogue: str = "", on_screen_text: Optional[List[str]] = None
) -> str:
    """
    Classifies content into 1 of 5 high-retention business storytelling pillars.
    Used to select dynamic narrative hooks, tailored breakdown bullets, and debate-driven comments.
    """
    ost_str = " ".join(on_screen_text or [])
    combined = f"{brand} {topic} {dialogue} {ost_str}".lower()

    if any(k in combined for k in [
        "ferrari", "rolex", "luxury", "scarcity", "hermes", "louis vuitton",
        "lvmh", "porsche", "lamborghini", "monopoly", "pricing power", "exclusive"
    ]):
        return "LUXURY_SCARCITY"
    elif any(k in combined for k in [
        "elon", "musk", "physics", "first principle", "principles", "spacex",
        "tesla", "steve jobs", "bezos", "mental model", "reasoning by analogy"
    ]):
        return "FIRST_PRINCIPLES"
    elif any(k in combined for k in [
        "competitor", "competitors", "seo", "backlink", "analyse", "reverse engineer",
        "traffic", "growth hack", "spy on competitors"
    ]):
        return "COMPETITIVE_INTEL"
    elif any(k in combined for k in [
        "starbucks", "third place", "community", "psychology", "habit", "addict",
        "anchor", "belonging", "loyalty", "retail experience"
    ]):
        return "PSYCHOLOGY_MOAT"
    elif any(k in combined for k in [
        "negotiat", "client", "deposit", "say this", "don't say", "dont say",
        "sales", "closing", "objection", "high-ticket", "closing deal"
    ]):
        return "SALES_FRAME_CONTROL"
    else:
        return "STRATEGIC_GROWTH"


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

    def _generate_title(self, understanding: ContentUnderstanding, clip_id: str = "") -> str:
        """
        Generates a search-friendly, high-CTR YouTube title strictly under 80 characters.
        Uses the 5 Narrative Pillars to select diverse, non-repetitive storytelling hooks.
        Appends #Shorts, #fyp, and dynamic brand/niche tags.
        """
        brand = getattr(understanding, "featured_brand", "").strip()
        topic = (understanding.central_topic or understanding.subject or "Business Strategy").strip().rstrip(". :|-")
        dialogue = getattr(understanding, "spoken_dialogue", "") or ""
        ost = getattr(understanding, "on_screen_text", []) or []
        takeaway = getattr(understanding, "main_takeaway", "") or ""

        pillar = classify_narrative_pillar(brand, topic, dialogue, ost)

        # Seed hash for deterministic yet rotating variant selection across different clips
        seed_str = f"{clip_id}_{brand}_{topic}_{takeaway[:20]}"
        variant = int(hashlib.md5(seed_str.encode("utf-8")).hexdigest(), 16)

        # 1. Brand-first viral business patterns
        if brand and brand.lower() != "unstocks":
            if pillar == "LUXURY_SCARCITY":
                formulas = [
                    f"Why {brand} Literally Rejects 90% Of Buyers",
                    f"Selling LESS Made {brand} 10x Richer",
                    f"The Artificial Scarcity Secret Behind {brand}",
                    f"Why {brand} Will NEVER Lower Their Prices",
                    f"How {brand} Creates An Insane Cult Following",
                    f"The Extreme Luxury Playbook Behind {brand}",
                ]
            elif pillar == "FIRST_PRINCIPLES":
                formulas = [
                    f"{brand}'s Physics Rule For Hard Problems",
                    f"Why 99% Think Wrong (And How {brand} Thinks)",
                    f"The First Principles Mental Model: {brand}",
                    f"Stop Reasoning By Analogy: The {brand} Rule",
                    f"How {brand} Solves 'Impossible' Problems",
                    f"The Extreme Mental Model That Built {brand}",
                ]
            elif pillar == "COMPETITIVE_INTEL":
                formulas = [
                    f"Stop Guessing: How {brand} Steals Traffic",
                    f"The Competitor Playbook Used By {brand}",
                    f"How {brand} Reverse-Engineered Their Moat",
                    f"The Unfair SEO Playbook Behind {brand}",
                ]
            elif pillar == "PSYCHOLOGY_MOAT":
                formulas = [
                    f"{brand} Doesn't Sell Products. The Real Moat",
                    f"The Psychological Moat That Built {brand}",
                    f"Why People Happily Pay 10x More For {brand}",
                    f"The Habit Loop That Makes {brand} Addictive",
                    f"The 'Third Place' Customer Moat of {brand}",
                ]
            elif pillar == "SALES_FRAME_CONTROL":
                formulas = [
                    f"DON'T SAY: 'Pay first.' SAY THIS INSTEAD",
                    f"The 1 Sentence That Closes High-Ticket Deals",
                    f"Stop Lowering Your Prices: The {brand} Script",
                    f"How {brand} Closes High-Ticket Clients Fast",
                ]
            else:
                formulas = [
                    f"The Counter-Intuitive Strategy Behind {brand}",
                    f"{brand}'s High-Leverage Growth Playbook",
                    f"The Asymmetric Advantage That Built {brand}",
                    f"Why Competitors Can't Copy {brand}'s Moat",
                    f"The 1 Strategic Pivot That Saved {brand}",
                ]
            base_title = formulas[variant % len(formulas)]
        else:
            # 2. Topic-led patterns (ensure topic name is prominently featured)
            has_dialogue = bool(dialogue and len(dialogue.strip()) > 10)
            has_visual_text = bool(ost and len(ost) > 0)

            if pillar == "COMPETITIVE_INTEL":
                formulas = [
                    f"Stop Guessing: How To Legally Steal Traffic",
                    f"The 3 Metrics To Reverse-Engineer in {topic}",
                    f"Stop Building In The Dark: {topic}",
                    f"How Top Founders Reverse-Engineer {topic}",
                    f"The Unfair Advantage: {topic} Playbook",
                ]
            elif pillar == "SALES_FRAME_CONTROL":
                formulas = [
                    f"DON'T SAY: 'Pay first.' SAY THIS INSTEAD",
                    f"The 1 Sentence That Closes High-Ticket Deals",
                    f"Stop Lowering Your Prices: {topic}",
                    f"The High-Stakes Script For {topic}",
                ]
            elif pillar == "FIRST_PRINCIPLES":
                formulas = [
                    f"The First Principles Rule: {topic}",
                    f"Why 99% Think Wrong About {topic}",
                    f"{topic}: The Physics Way To Problem Solving",
                ]
            elif has_dialogue and takeaway and 10 <= len(takeaway) <= 35:
                formulas = [
                    f"{topic}: {takeaway}",
                    f"{topic} — What You Need to Know",
                    f"The Counter-Intuitive Truth: {topic}",
                ]
            elif has_visual_text:
                formulas = [
                    f"{topic} Breakdown & Overview",
                    f"The Masterclass Guide: {topic}",
                    f"{topic} — Core Architecture & Strategy",
                ]
            else:
                formulas = [
                    f"{topic} Breakdown & Strategy",
                    f"The Asymmetric Playbook: {topic}",
                    f"Why 90% Fail At {topic}",
                ]
            base_title = formulas[variant % len(formulas)]

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
        Features dynamic narrative hooks, bespoke breakdown bullets, and exact speech excerpts.
        """
        brand = getattr(understanding, "featured_brand", "").strip() or "The World's Best Brands"
        topic = (understanding.central_topic or understanding.subject or "Business Strategy").strip()
        summary = understanding.summary.strip()
        takeaway = understanding.main_takeaway.strip()
        moat = getattr(understanding, "strategic_moat", "Market Positioning & Brand Equity")
        dialogue = getattr(understanding, "spoken_dialogue", "") or ""
        ost = getattr(understanding, "on_screen_text", []) or []
        is_short = understanding.is_short

        pillar = classify_narrative_pillar(brand, topic, dialogue, ost)

        # Stage 1: The Narrative Hook
        if brand and brand != "The World's Best Brands":
            if pillar == "LUXURY_SCARCITY":
                opening_hook = (
                    f"Why {brand} intentionally refuses customer demand to engineer extreme brand equity. "
                    f"In this breakdown, we examine the economics of manufactured scarcity, luxury pricing power, "
                    f"and how capping volume creates an untouchable market moat."
                )
            elif pillar == "FIRST_PRINCIPLES":
                opening_hook = (
                    f"How {brand} solves 'impossible' engineering and business problems using First Principles. "
                    f"Rather than reasoning by analogy or copying competitors, this mental model deconstructs "
                    f"challenges to fundamental truths and innovates at 10x velocity."
                )
            elif pillar == "COMPETITIVE_INTEL":
                opening_hook = (
                    f"The competitive intelligence framework that eliminates guesswork in customer acquisition. "
                    f"We deconstruct how {brand} analyzes top-performing competitor assets, search traffic moats, "
                    f"and reverse-engineers proven distribution funnels."
                )
            elif pillar == "PSYCHOLOGY_MOAT":
                opening_hook = (
                    f"Why {brand} doesn't compete on product features or commodity pricing. "
                    f"In this business breakdown, we analyze the 'Third Place' psychology, habit loops, "
                    f"and emotional customer retention moats that make their business model unshakeable."
                )
            elif pillar == "SALES_FRAME_CONTROL":
                opening_hook = (
                    f"The high-stakes conversational framing that eliminates price resistance. "
                    f"We break down the client psychology, deposit framing, and frame control scripts "
                    f"used by top negotiators to close deals with zero friction."
                )
            else:
                opening_hook = (
                    f"How {brand} engineered an asymmetric market monopoly without competing on price. "
                    f"In this business case study, we deconstruct the marketing psychology, unit economics, "
                    f"and distribution moat behind their explosive brand growth."
                )
        elif summary:
            opening_hook = f"{summary} In this business breakdown, we examine the underlying strategic moats driving brand growth."
        else:
            opening_hook = f"A tactical breakdown of {topic.lower()} and the high-leverage frameworks that drive scalable business growth."

        # Stage 2: 3-Point Business Mechanism Breakdown (Tailored to Narrative Pillar)
        if pillar == "LUXURY_SCARCITY":
            pillar_bullets = [
                f"• The Scarcity Mechanism: How artificial supply limits protect pricing power for {brand or 'luxury icons'}.",
                "• Buyer Psychology: Why high-net-worth customers desire what they cannot easily acquire.",
                "• Margin Dominance: How premium positioning protects gross margins against inflationary cycles.",
            ]
        elif pillar == "FIRST_PRINCIPLES":
            pillar_bullets = [
                "• Fundamental Truths: Stripping away assumptions down to foundational physics and core unit costs.",
                "• Cost Curve Reduction: Re-engineering from raw materials up rather than paying middleman margins.",
                "• Execution Velocity: Why questioning industry norms enables 10x iteration speed.",
            ]
        elif pillar == "COMPETITIVE_INTEL":
            pillar_bullets = [
                "• Unfair Intelligence: Identifying high-intent search queries and content assets that drive conversion.",
                "• Backlink & Authority Moats: Deconstructing how market leaders capture organic rank.",
                "• Traffic Arbitrage: Converting discovered competitor gaps into scalable customer acquisition.",
            ]
        elif pillar == "PSYCHOLOGY_MOAT":
            pillar_bullets = [
                "• The Third Place Concept: Monetizing belonging and physical atmosphere over raw commodities.",
                "• Habit Architecture: Turning daily customer routines into recurring, high-LTV revenue.",
                "• Brand Loyalty Lock-in: Why emotional affinity beats competing feature checklists.",
            ]
        elif pillar == "SALES_FRAME_CONTROL":
            pillar_bullets = [
                "• Frame Control: Shifting conversational authority without creating adversarial client friction.",
                "• Risk Reversal: How deposit framing removes hesitation before commitment.",
                "• Value Anchoring: Establishing high-ticket positioning before discussing deliverables.",
            ]
        else:
            pillar_bullets = [
                f"• The Core Moat: How {brand or 'market leaders'} establish pricing power and uncontested market share.",
                "• Customer Acquisition: The exact psychological framing that converts cold attention into brand advocates.",
                "• Unit Economics: How strategic distribution beats pure product features every single time.",
            ]

        key_points = []
        if understanding.on_screen_text:
            key_points.extend([t.strip() for t in understanding.on_screen_text if t.strip()])
        elif understanding.entities:
            key_points.extend([e.strip() for e in understanding.entities if e.strip() and e.lower() != "unstocks"])

        explanation_lines = ["📊 Strategic Breakdown:"] + pillar_bullets

        # If speech transcript excerpt exists, quote it!
        if dialogue and len(dialogue.strip()) > 20:
            quote = dialogue.strip()[:140]
            if len(dialogue.strip()) > 140:
                quote = f"{quote.rsplit(' ', 1)[0]}..."
            explanation_lines.append("")
            explanation_lines.append(f'🎙️ Spoken Key Insight: "{quote}"')

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
            if b_tag and 3 <= len(b_tag) <= 20:
                clean_hashtags.append(b_tag)

        SCRAPER_BLACKLIST = ("klickpin", "pinterest", "dreamboard", "transformed", "pinid", "pin")
        for e in understanding.entities:
            if any(b in e.lower() for b in SCRAPER_BLACKLIST):
                continue
            clean = re.sub(r'[^a-zA-Z0-9]', '', e)
            if clean and 3 <= len(clean) <= 20 and clean.lower() not in [c.lower() for c in clean_hashtags] and clean.lower() != "unstocks":
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
        title = self._generate_title(understanding, clip_id=clip_id)
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
    Uses the Founder's Dilemma Debate Loop tailored to the video's narrative pillar to maximize comment velocity, retention, and reach.
    """
    brand = getattr(understanding, "featured_brand", "").strip()
    topic = (understanding.central_topic or understanding.subject or "this business model").strip()
    dialogue = getattr(understanding, "spoken_dialogue", "") or ""
    ost = getattr(understanding, "on_screen_text", []) or []
    takeaway = getattr(understanding, "main_takeaway", "") or ""

    pillar = classify_narrative_pillar(brand, topic, dialogue, ost)
    subject_entity = brand if brand and brand.lower() != "unstocks" else topic

    cta = "👉 Subscribe to @unstocks for daily unfiltered business breakdowns and wealth systems."

    if pillar == "LUXURY_SCARCITY":
        question = (
            f"💡 Founder's Debate: Would you rather build a high-volume mass brand, "
            f"or an ultra-exclusive luxury brand like {subject_entity} that turns away 90% of buyers? "
            f"Which business model survives longer in a recession?"
        )
    elif pillar == "FIRST_PRINCIPLES":
        question = (
            f"💡 The First Principles Test: When facing a bottleneck in your business or life, "
            f"do you reason by analogy (copy what others do) or break it down to physics-level fundamentals like {subject_entity}? "
            f"What's one belief you held that completely flipped?"
        )
    elif pillar == "COMPETITIVE_INTEL":
        question = (
            f"💡 The Growth Dilemma: In your experience, is it smarter to innovate completely from scratch, "
            f"or reverse-engineer your top 3 competitors' traffic sources and out-execute them on distribution? "
            f"Drop your strategic take below!"
        )
    elif pillar == "PSYCHOLOGY_MOAT":
        question = (
            f"💡 The Moat Test: Does {subject_entity} win because of product quality, or because of pure behavioral psychology and habit design? "
            f"If an exact identical product launched at half the price tomorrow, would customers switch?"
        )
    elif pillar == "SALES_FRAME_CONTROL":
        question = (
            f"💡 Negotiation Dilemma: What's the biggest mistake founders make when closing high-ticket clients: "
            f"lowering the price when pushed, or failing to hold frame on upfront commitment? "
            f"How do you handle price objections in your deals?"
        )
    else:
        if takeaway:
            question = (
                f"💡 Founder's Dilemma: {takeaway}\n\n"
                f"If you were the CEO of {subject_entity}, would you double down on premium high-margin pricing "
                f"or aggressive mass-market volume? Drop your strategic breakdown below!"
            )
        else:
            question = (
                f"💡 Founder's Question: What is the single biggest moat protecting {subject_entity} from competition today?\n\n"
                f"Drop your strategic take in the comments!"
            )

    return f"{question}\n\n{cta}"
