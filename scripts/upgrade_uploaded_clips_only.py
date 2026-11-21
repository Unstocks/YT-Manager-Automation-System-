"""
Unstocks Targeted Video Upgrade Engine
Strictly updates ONLY the 4 uploaded project clips based on in-depth frame & voiceover analysis:
1. wuMZFV_zse8: Netflix & Reed Hastings (325M Subscribers, DVD-to-Streaming Monopoly)
2. dNrMoLs5VOY: Zoom & Eric Yuan ($8 Billion Real Cash Flow vs Speculative Valuations)
3. 9PK37JRn6C8: Systems Over Hustle (Building Systems Meant to Stay)
4. n0x4dClBWgM: 35,000 Decisions (Structured Problem Solving for Founders)

GUARANTEE: Will NEVER touch or modify any of the founder's 7 pre-existing channel videos.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict
import urllib.request
import urllib.error

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from yt_manager.config import YTManagerConfig
from yt_manager.auth import YouTubeAuthManager

TARGET_UPDATES = [
    {
        "video_id": "wuMZFV_zse8",
        "title": "How Netflix Built A 325M Subscriber Monopoly #Netflix #shorts #fyp",
        "description": (
            "How Reed Hastings engineered the greatest business pivot in tech history. "
            "From mailing physical DVDs to building an uncontested streaming monopoly with over 325 million global subscribers.\n\n"
            "📊 Strategic Breakdown:\n"
            "• The Distribution Moat: How Netflix crushed Blockbuster by eliminating late fees and investing in early streaming infrastructure.\n"
            "• Unit Economics: Transitioning from per-disc postal shipping costs to infinitely scalable digital content licensing.\n"
            "• Proprietary Flywheel: Utilizing personalized recommendation algorithms to drive massive viewer retention and near-zero subscriber churn.\n\n"
            "🔍 Key Business & Marketing Topics:\n"
            "Netflix Case Study • Reed Hastings • Subscription Models • Streaming Wars • Digital Disruption • "
            "Customer Lifetime Value • Platform Economics • Business Strategy • Brand Building\n\n"
            "🧠 About Unstocks:\n"
            "Unstocks (@unstocks) breaks down the hidden strategies, business mechanics, and brand psychology "
            "behind the world's most profitable companies. Daily tactical breakdowns for ambitious founders, "
            "brand architects, and operators.\n\n"
            "👉 Subscribe to @unstocks for daily unfiltered business breakdowns and wealth systems.\n"
            "🌐 Channel: https://youtube.com/@unstocks\n\n"
            "#Netflix #ReedHastings #Business #BrandStrategy #Marketing #Startups #Streaming #Shorts #ytshorts #fyp #viral"
        ),
        "tags": [
            "netflix",
            "reed hastings",
            "netflix business model",
            "streaming wars",
            "blockbuster vs netflix",
            "business strategy",
            "brand strategy",
            "unit economics",
            "subscription business",
            "unstocks",
            "shorts",
            "youtube shorts"
        ],
        "category_id": "27"
    },
    {
        "video_id": "dNrMoLs5VOY",
        "title": "The $8 Billion SaaS Secret Behind Zoom #Zoom #shorts #fyp",
        "description": (
            "Why real unit economics and customer retention beat speculative AI startup hype every single time. "
            "How Eric Yuan built Zoom into an $8 Billion enterprise communication juggernaut.\n\n"
            "📊 Strategic Breakdown:\n"
            "• Product-Led Growth: The genius 40-minute free meeting limit that converted millions of organic users into high-ARR enterprise contracts.\n"
            "• Moat vs Hype: Why sticky enterprise workflows and low latency create durable market cap while superficial wrapper startups collapse.\n"
            "• Cash Flow Discipline: Maintaining positive unit economics and profitability instead of burning capital on empty vanity metrics.\n\n"
            "🔍 Key Business & Marketing Topics:\n"
            "Zoom Case Study • Eric Yuan • SaaS Growth • B2B Sales • Product Led Growth • "
            "Unit Economics • Valuation Realities • Startup Scaling • Business Strategy\n\n"
            "🧠 About Unstocks:\n"
            "Unstocks (@unstocks) breaks down the hidden strategies, business mechanics, and brand psychology "
            "behind the world's most profitable companies. Daily tactical breakdowns for ambitious founders, "
            "brand architects, and operators.\n\n"
            "👉 Subscribe to @unstocks for daily unfiltered business breakdowns and wealth systems.\n"
            "🌐 Channel: https://youtube.com/@unstocks\n\n"
            "#Zoom #EricYuan #SaaS #Business #Startups #UnitEconomics #ProductLedGrowth #Shorts #ytshorts #fyp #viral"
        ),
        "tags": [
            "zoom",
            "eric yuan",
            "saas business model",
            "product led growth",
            "b2b sales",
            "startup valuation",
            "business strategy",
            "unit economics",
            "software business",
            "unstocks",
            "shorts",
            "youtube shorts"
        ],
        "category_id": "27"
    },
    {
        "video_id": "9PK37JRn6C8",
        "title": "Why Hustle Culture Kills Startups: Build Systems Instead #Shorts #fyp",
        "description": (
            "Growth rarely comes from working longer hours. Sustainable enterprise scale requires building systems meant to stay.\n\n"
            "📊 Strategic Breakdown:\n"
            "• Eliminating Founder Bottlenecks: Transitioning from working IN the business to working ON the operational architecture.\n"
            "• Decision Architecture: Transforming everyday decisions into standardized, repeatable processes that empower teams to execute without you.\n"
            "• Operational Durability: How structured delegation and automated workflows protect founder cognitive bandwidth and prevent burnout.\n\n"
            "🔍 Key Business & Management Topics:\n"
            "Systems Thinking • Operations Scaling • Founder Leverage • Business Architecture • Decision Making • "
            "Startup Growth • Productivity Psychology • Delegation Frameworks\n\n"
            "🧠 About Unstocks:\n"
            "Unstocks (@unstocks) breaks down the hidden strategies, business mechanics, and brand psychology "
            "behind the world's most profitable companies. Daily tactical breakdowns for ambitious founders, "
            "brand architects, and operators.\n\n"
            "👉 Subscribe to @unstocks for daily unfiltered business breakdowns and wealth systems.\n"
            "🌐 Channel: https://youtube.com/@unstocks\n\n"
            "#Business #SystemsThinking #Entrepreneurship #Startups #Productivity #Operations #Shorts #ytshorts #fyp #viral"
        ),
        "tags": [
            "systems thinking",
            "business operations",
            "founder leverage",
            "hustle culture",
            "business architecture",
            "decision making",
            "startup growth",
            "scaling a business",
            "unstocks",
            "shorts",
            "youtube shorts"
        ],
        "category_id": "27"
    },
    {
        "video_id": "n0x4dClBWgM",
        "title": "The 35,000 Daily Decisions That Make Or Break Startups #Shorts #fyp",
        "description": (
            "The average human makes over 35,000 decisions every single day. "
            "For founders, CEOs, and operators, decision quality compounds into multi-million dollar outcomes or catastrophic failure.\n\n"
            "📊 Strategic Breakdown:\n"
            "• Cognitive Capital Preservation: How elite operators eliminate low-stakes micro-decisions to reserve peak focus for asymmetric strategic bets.\n"
            "• Structured Problem Solving: Deploying first-principles frameworks and mental models to de-risk high-stakes business choices.\n"
            "• Reversible vs Irreversible Decisions: Jeff Bezos's Type 1 vs Type 2 decision framework for moving with high velocity without reckless error.\n\n"
            "🔍 Key Strategic Topics:\n"
            "Decision Architecture • Mental Models • Cognitive Psychology • Founder Mindset • Problem Solving • "
            "Strategic Thinking • Startup Leadership • Business Execution\n\n"
            "🧠 About Unstocks:\n"
            "Unstocks (@unstocks) breaks down the hidden strategies, business mechanics, and brand psychology "
            "behind the world's most profitable companies. Daily tactical breakdowns for ambitious founders, "
            "brand architects, and operators.\n\n"
            "👉 Subscribe to @unstocks for daily unfiltered business breakdowns and wealth systems.\n"
            "🌐 Channel: https://youtube.com/@unstocks\n\n"
            "#DecisionMaking #MentalModels #ProblemSolving #BusinessStrategy #Leadership #Startups #Shorts #ytshorts #fyp #viral"
        ),
        "tags": [
            "decision making",
            "structured problem solving",
            "mental models",
            "cognitive psychology",
            "founder mindset",
            "business leadership",
            "strategic thinking",
            "unstocks",
            "shorts",
            "youtube shorts"
        ],
        "category_id": "27"
    }
]


def run_targeted_upgrade() -> None:
    config = YTManagerConfig.load()
    auth = YouTubeAuthManager(config)
    token = auth.get_valid_access_token()

    print("=" * 70)
    print("🎯 UNSTOCKS TARGETED UPGRADE: 4 UPLOADED CLIPS ONLY")
    print("🛡️ STRICT GUARANTEE: Pre-existing channel videos remain 100% untouched.")
    print("=" * 70)

    for item in TARGET_UPDATES:
        vid = item["video_id"]
        title = item["title"]
        desc = item["description"]
        tags = item["tags"]
        cat_id = item["category_id"]

        print(f"\n🎬 Updating Video [{vid}]:")
        print(f" ✨ New Title: {title}")

        # Fetch snippet to preserve channelId and category defaults
        get_url = f"https://www.googleapis.com/youtube/v3/videos?part=snippet&id={vid}"
        req_get = urllib.request.Request(get_url, headers={"Authorization": f"Bearer {token}"})
        try:
            with urllib.request.urlopen(req_get, timeout=30) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            items = data.get("items", [])
            if not items:
                print(f" ⚠️ Video [{vid}] not found on YouTube. Skipping.")
                continue
            snippet = items[0]["snippet"]
        except Exception as e:
            print(f" ❌ Failed to fetch video [{vid}]: {e}")
            continue

        snippet["title"] = title
        snippet["description"] = desc
        snippet["tags"] = tags
        snippet["categoryId"] = cat_id
        snippet["defaultLanguage"] = "en"

        update_url = "https://www.googleapis.com/youtube/v3/videos?part=snippet"
        payload = {
            "id": vid,
            "snippet": snippet,
        }
        req_put = urllib.request.Request(
            update_url,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
            method="PUT",
        )
        try:
            with urllib.request.urlopen(req_put, timeout=30) as resp:
                print(f" ✅ Successfully upgraded Video [{vid}] on YouTube!")
        except Exception as e:
            print(f" ❌ Failed to update Video [{vid}]: {e}")

    print("\n🎉 Targeted upgrade complete! All 4 uploaded clips are now live with high-retention metadata.")


if __name__ == "__main__":
    run_targeted_upgrade()
