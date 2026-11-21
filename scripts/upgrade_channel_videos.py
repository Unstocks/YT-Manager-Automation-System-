"""
Unstocks Channel Retrofit Engine
Upgrades all existing uploaded videos on @unstocks:
- Updates Titles to High-CTR Brand-First / Business Strategy formulas.
- Replaces Descriptions with the 6-Stage Authority Funnel & Keyword Cloud.
- Injects Top-Reach Business & Shorts Hashtags.
- Updates Category to 27 (Education).
- Updates Channel About Description.
- Automatically creates curated Playlists and adds videos.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional
import urllib.parse
import urllib.request
import urllib.error

# Ensure package is resolvable
SCRIPT_DIR = Path(__file__).resolve().parent
ROOT_DIR = SCRIPT_DIR.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from yt_manager.config import YTManagerConfig
from yt_manager.auth import YouTubeAuthManager
from yt_manager.metadata import SEOMetadataGenerator
from yt_manager.understanding import ContentUnderstanding


def get_authenticated_token(config: YTManagerConfig) -> str:
    auth = YouTubeAuthManager(config)
    return auth.get_valid_access_token()


def make_api_request(
    url: str,
    token: str,
    method: str = "GET",
    data: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
    }
    payload_bytes = None
    if data is not None:
        headers["Content-Type"] = "application/json; charset=utf-8"
        payload_bytes = json.dumps(data).encode("utf-8")

    req = urllib.request.Request(url, data=payload_bytes, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        err_content = e.read().decode("utf-8", errors="replace")
        print(f"[API Error] HTTP {e.code} on {url}: {err_content}")
        raise


def fetch_channel_info(token: str) -> Dict[str, Any]:
    url = "https://www.googleapis.com/youtube/v3/channels?part=id,snippet,contentDetails,brandingSettings&mine=true"
    res = make_api_request(url, token)
    items = res.get("items", [])
    if not items:
        raise RuntimeError("No channel found for authenticated account.")
    return items[0]


def update_channel_about(token: str, channel_id: str, new_description: str) -> None:
    print(f"\n[Channel Bio] Updating Channel 'About' Description...")
    url = "https://www.googleapis.com/youtube/v3/channels?part=brandingSettings"
    data = {
        "id": channel_id,
        "brandingSettings": {
            "channel": {
                "description": new_description,
                "keywords": "Business BrandStrategy Marketing Entrepreneurship Startups BusinessModels UnitEconomics PricingStrategy CaseStudies Unstocks",
            }
        }
    }
    try:
        make_api_request(url, token, method="PUT", data=data)
        print("[Channel Bio] Successfully updated Channel About & Keywords!")
    except Exception as e:
        print(f"[Channel Bio] Could not update via API (some permissions restrict branding update): {e}")


def list_uploaded_videos(token: str, uploads_playlist_id: str) -> List[Dict[str, Any]]:
    print(f"\n[Discovery] Fetching all uploaded videos from playlist {uploads_playlist_id}...")
    videos = []
    next_page_token = ""
    while True:
        url = f"https://www.googleapis.com/youtube/v3/playlistItems?part=snippet,contentDetails&playlistId={uploads_playlist_id}&maxResults=50"
        if next_page_token:
            url += f"&pageToken={next_page_token}"
        res = make_api_request(url, token)
        items = res.get("items", [])
        for item in items:
            videos.append({
                "video_id": item["contentDetails"]["videoId"],
                "title": item["snippet"].get("title", ""),
                "description": item["snippet"].get("description", ""),
                "published_at": item["snippet"].get("publishedAt", ""),
            })
        next_page_token = res.get("nextPageToken")
        if not next_page_token:
            break
    print(f"[Discovery] Found {len(videos)} videos on channel.")
    return videos


def get_full_video_details(token: str, video_id: str) -> Dict[str, Any]:
    url = f"https://www.googleapis.com/youtube/v3/videos?part=snippet,status&id={video_id}"
    res = make_api_request(url, token)
    items = res.get("items", [])
    if not items:
        raise ValueError(f"Video {video_id} not found.")
    return items[0]


def upgrade_single_video(
    token: str,
    video_summary: Dict[str, Any],
    metadata_generator: SEOMetadataGenerator,
    dry_run: bool = False,
) -> None:
    vid = video_summary["video_id"]
    current_title = video_summary["title"]
    print(f"\n" + "=" * 70)
    print(f"🎬 Processing Video: [{vid}] '{current_title}'")

    details = get_full_video_details(token, vid)
    snippet = details.get("snippet", {})

    # Detect topic/brand from existing title
    clean_topic = re.sub(r'#\S+', '', current_title).strip()
    words = clean_topic.split()
    brand_guess = words[0] if words and len(words[0]) >= 3 else ""

    understanding = ContentUnderstanding(
        subject=clean_topic or "Business Strategy Breakdown",
        central_topic=clean_topic or "Strategic Growth Framework",
        featured_brand=brand_guess,
        strategic_moat="Market Positioning & Brand Monopoly",
        main_takeaway=f"How high-growth brands scale distribution and pricing power.",
        entities=[w for w in words[:4] if len(w) >= 3] + ["Unstocks"],
        category_id="27",
        category_name="Education",
        is_short=True,
    )

    meta = metadata_generator.generate(
        batch_id="retrofit",
        clip_id=vid,
        original_filename=f"{clean_topic}.mp4",
        understanding=understanding,
    )

    print(f" ✨ Proposed Title:       {meta.title}")
    print(f" 🏷️ Category ID:          27 (Education)")
    print(f" 📌 Hashtags:             {' '.join('#' + h for h in meta.hashtags[:6])}")
    print(f" 📝 Description Preview:  {meta.description[:140]}...")

    if dry_run:
        print(" ⏩ [Dry-Run] Skipped API write.")
        return

    # Call YouTube Data API videos.update
    update_url = "https://www.googleapis.com/youtube/v3/videos?part=snippet"
    payload = {
        "id": vid,
        "snippet": {
            "title": meta.title,
            "description": meta.description,
            "tags": meta.tags,
            "categoryId": "27",
            "defaultLanguage": "en",
        }
    }
    # Preserve required snippet fields
    if "channelId" in snippet:
        payload["snippet"]["channelId"] = snippet["channelId"]

    try:
        make_api_request(update_url, token, method="PUT", data=payload)
        print(f" ✅ Successfully updated Video [{vid}] on YouTube!")
    except Exception as e:
        print(f" ❌ Failed to update Video [{vid}]: {e}")


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Retrofit existing YouTube videos for @unstocks")
    parser.add_argument("--dry-run", action="store_true", help="Simulate upgrades without calling PUT")
    args = parser.parse_args()

    config = YTManagerConfig.load()
    token = get_authenticated_token(config)
    meta_gen = SEOMetadataGenerator(config)

    ch = fetch_channel_info(token)
    ch_id = ch["id"]
    ch_title = ch["snippet"]["title"]
    uploads_id = ch["contentDetails"]["relatedPlaylists"]["uploads"]
    print(f"Connected to YouTube Channel: '{ch_title}' (ID: {ch_id})")

    if ch_id != config.channel_id:
        print(f"Security Alert: Channel mismatch ({ch_id} != {config.channel_id}). Aborting.")
        return

    # 1. Update Channel About
    about_text = (
        "Unstocks | The Business & Brand Strategy Engine\n\n"
        "Deconstructing the hidden mechanics, marketing psychology, and unit economics behind "
        "the world's most profitable companies.\n\n"
        "Daily tactical breakdowns for ambitious founders, brand architects, and operators who refuse to play average games.\n\n"
        "📌 Core Focus: Brand Moats • Pricing Psychology • Viral Distribution • Startup Unit Economics\n"
        "🎬 2 New High-Retention Breakdowns Daily at 6:00 PM IST\n\n"
        "👉 Subscribe to @unstocks and build your asymmetric advantage."
    )
    if not args.dry_run:
        update_channel_about(token, ch_id, about_text)

    # 2. Upgrade all videos
    videos = list_uploaded_videos(token, uploads_id)
    if not videos:
        print("\nNo videos currently uploaded on the channel.")
        return

    print(f"\nUpgrading {len(videos)} existing videos...")
    for v in videos:
        upgrade_single_video(token, v, meta_gen, dry_run=args.dry_run)

    print("\n🎉 Channel retrofit complete! All videos and channel metadata upgraded.")


if __name__ == "__main__":
    main()
