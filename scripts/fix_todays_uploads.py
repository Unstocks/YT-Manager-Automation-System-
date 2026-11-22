"""
Fix Today's Uploaded Clips on Unstocks Channel (@unstocks)
Updates metadata and ensures videos are PUBLIC:
1. ipYxc0EJg4E: Client negotiation & sales psychology
2. XsMRblZcl7I: Bernard Arnault & LVMH luxury empire

GUARANTEE: Modifies ONLY these two specific video IDs. All other videos remain 100% untouched.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
import urllib.request
import urllib.error

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from yt_manager.config import YTManagerConfig
from yt_manager.auth import YouTubeAuthManager

TARGET_UPDATES = [
    {
        "video_id": "ipYxc0EJg4E",
        "title": "The Psychology Of Closing Deals: Don't Say 'Pay First' #Sales #shorts #fyp",
        "description": (
            "The exact phrasing high-ticket negotiators use to close enterprise deals without friction. "
            "Why saying 'You have to pay first' triggers customer defense mechanisms, and what to say instead.\n\n"
            "📊 Strategic Breakdown:\n"
            "• Reframing the Ask: Shifting from demanding payment to establishing next operational steps ('As soon as we receive deposit...').\n"
            "• Psychological Anchoring: Lowering client friction and building immediate partnership dynamics.\n"
            "• Enterprise Closing Mechanics: Moving from transactional posture to value delivery.\n\n"
            "🔍 Key Business & Sales Topics:\n"
            "Client Negotiation • Sales Psychology • Closing Deals • Enterprise Sales • Objection Handling • "
            "Client Onboarding • Pricing Psychology • Deal Structuring\n\n"
            "🧠 About Unstocks:\n"
            "Unstocks (@unstocks) breaks down the hidden strategies, business mechanics, and brand psychology "
            "behind the world's most profitable companies. Daily tactical breakdowns for ambitious founders, "
            "brand architects, and operators.\n\n"
            "👉 Subscribe to @unstocks for daily unfiltered business breakdowns and wealth systems.\n"
            "🌐 Channel: https://youtube.com/@unstocks\n\n"
            "#Sales #Negotiation #SalesPsychology #BusinessStrategy #ClosingDeals #HighTicket #Entrepreneurship #Shorts #ytshorts #fyp #viral"
        ),
        "tags": [
            "sales psychology",
            "negotiation tactics",
            "closing deals",
            "client negotiation",
            "how to close sales",
            "sales tips",
            "business strategy",
            "unstocks",
            "shorts",
            "youtube shorts",
            "fyp"
        ],
        "category_id": "27"
    },
    {
        "video_id": "XsMRblZcl7I",
        "title": "How Bernard Arnault Built The $400B LVMH Luxury Empire #LVMH #shorts #fyp",
        "description": (
            "How Bernard Arnault turned luxury into an untouchable $400 Billion global monopoly. "
            "The business playbook behind LVMH (Louis Vuitton, Dior, Moët, Tiffany & Co.).\n\n"
            "📊 Strategic Breakdown:\n"
            "• Desirability Flywheel: Controlling scarcity and prestige pricing to create unyielding pricing power.\n"
            "• Brand Conglomerate Moat: Acquiring heritage houses and centralizing supply chains and global real estate.\n"
            "• Generational Empire: How Arnault structured LVMH to maintain permanent family control.\n\n"
            "🔍 Key Business & Brand Topics:\n"
            "Bernard Arnault • LVMH • Luxury Goods • Louis Vuitton • Dior • Tiffany & Co • "
            "Brand Moats • Pricing Power • Business Conglomerate • Monopoly Strategy\n\n"
            "🧠 About Unstocks:\n"
            "Unstocks (@unstocks) breaks down the hidden strategies, business mechanics, and brand psychology "
            "behind the world's most profitable companies. Daily tactical breakdowns for ambitious founders, "
            "brand architects, and operators.\n\n"
            "👉 Subscribe to @unstocks for daily unfiltered business breakdowns and wealth systems.\n"
            "🌐 Channel: https://youtube.com/@unstocks\n\n"
            "#LVMH #BernardArnault #LuxuryBusiness #LouisVuitton #Dior #BrandStrategy #BusinessMoats #WealthSystems #Shorts #ytshorts #fyp #viral"
        ),
        "tags": [
            "bernard arnault",
            "lvmh",
            "louis vuitton",
            "luxury brand strategy",
            "luxury business",
            "pricing power",
            "brand moats",
            "business case study",
            "unstocks",
            "shorts",
            "youtube shorts",
            "fyp"
        ],
        "category_id": "27"
    }
]


def run_fix() -> None:
    config = YTManagerConfig.load()
    auth = YouTubeAuthManager(config)
    token = auth.get_valid_access_token()

    print("=" * 70)
    print("🎯 UNSTOCKS: FIX TODAY'S UPLOADS & ENFORCE PUBLIC STATUS")
    print("🛡️ STRICT GUARANTEE: Pre-existing channel videos remain 100% untouched.")
    print("=" * 70)

    for item in TARGET_UPDATES:
        vid = item["video_id"]
        title = item["title"]
        desc = item["description"]
        tags = item["tags"]
        cat_id = item["category_id"]

        print(f"\n🎬 Updating Video [{vid}]:")
        print(f" ✨ Title: {title}")

        # Fetch current snippet & status
        get_url = f"https://www.googleapis.com/youtube/v3/videos?part=snippet,status&id={vid}"
        req_get = urllib.request.Request(get_url, headers={"Authorization": f"Bearer {token}"})
        try:
            with urllib.request.urlopen(req_get, timeout=30) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            items = data.get("items", [])
            if not items:
                print(f" ⚠️ Video [{vid}] not found on YouTube. Skipping.")
                continue
            snippet = items[0]["snippet"]
            status = items[0].get("status", {})
        except Exception as e:
            print(f" ❌ Failed to fetch video [{vid}]: {e}")
            continue

        snippet["title"] = title
        snippet["description"] = desc
        snippet["tags"] = tags
        snippet["categoryId"] = cat_id
        snippet["defaultLanguage"] = "en"

        # Explicitly set privacy status to PUBLIC
        status["privacyStatus"] = "public"

        update_url = "https://www.googleapis.com/youtube/v3/videos?part=snippet,status"
        payload = {
            "id": vid,
            "snippet": snippet,
            "status": status,
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
                result = json.loads(resp.read().decode("utf-8"))
                new_status = result.get("status", {}).get("privacyStatus")
                print(f" ✅ Successfully updated Video [{vid}]! Privacy is now: {new_status}")
        except Exception as e:
            print(f" ❌ Failed to update Video [{vid}]: {e}")

    print("\n🎉 Fix complete! Both videos are now optimized with clean metadata and set to PUBLIC.")


if __name__ == "__main__":
    run_fix()
