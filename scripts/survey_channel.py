"""
Unstocks Channel Video Survey & Inspection Engine
Fetches every video on @unstocks, extracts all metadata, statistics, thumbnails,
and generates a full diagnostic survey report (data/channel_inventory.json and .md).
Allows exact restoration or custom title/description updates per video.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict, List
import urllib.request
import urllib.error

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from yt_manager.config import YTManagerConfig
from yt_manager.auth import YouTubeAuthManager


def fetch_all_channel_videos() -> List[Dict[str, Any]]:
    config = YTManagerConfig.load()
    auth = YouTubeAuthManager(config)
    token = auth.get_valid_access_token()

    # 1. Get uploads playlist
    ch_url = "https://www.googleapis.com/youtube/v3/channels?part=id,snippet,contentDetails,statistics&mine=true"
    req = urllib.request.Request(ch_url, headers={"Authorization": f"Bearer {token}"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        ch_data = json.loads(resp.read().decode("utf-8"))

    channel = ch_data["items"][0]
    channel_title = channel["snippet"]["title"]
    uploads_id = channel["contentDetails"]["relatedPlaylists"]["uploads"]
    total_videos_stat = channel.get("statistics", {}).get("videoCount", "N/A")

    print("=" * 70)
    print(f"📡 SURVEYING CHANNEL: {channel_title} (@unstocks)")
    print(f"📊 Total Video Count Reported: {total_videos_stat}")
    print(f"📂 Uploads Playlist ID: {uploads_id}")
    print("=" * 70)

    # 2. Page through uploads playlist
    video_items = []
    next_page = ""
    while True:
        pl_url = f"https://www.googleapis.com/youtube/v3/playlistItems?part=snippet,contentDetails&playlistId={uploads_id}&maxResults=50"
        if next_page:
            pl_url += f"&pageToken={next_page}"
        req_pl = urllib.request.Request(pl_url, headers={"Authorization": f"Bearer {token}"})
        with urllib.request.urlopen(req_pl, timeout=30) as resp:
            pl_data = json.loads(resp.read().decode("utf-8"))

        for item in pl_data.get("items", []):
            vid = item["contentDetails"]["videoId"]
            snip = item["snippet"]
            video_items.append({
                "video_id": vid,
                "url": f"https://youtu.be/{vid}",
                "title": snip.get("title", ""),
                "description": snip.get("description", ""),
                "published_at": snip.get("publishedAt", ""),
                "thumbnail": snip.get("thumbnails", {}).get("high", {}).get("url", ""),
            })

        next_page = pl_data.get("nextPageToken")
        if not next_page:
            break

    # 3. Fetch detailed statistics and tags for each video
    enriched_videos = []
    chunk_size = 50
    for i in range(0, len(video_items), chunk_size):
        chunk = video_items[i : i + chunk_size]
        ids_str = ",".join(v["video_id"] for v in chunk)
        v_url = f"https://www.googleapis.com/youtube/v3/videos?part=snippet,contentDetails,statistics,status&id={ids_str}"
        req_v = urllib.request.Request(v_url, headers={"Authorization": f"Bearer {token}"})
        with urllib.request.urlopen(req_v, timeout=30) as resp:
            v_data = json.loads(resp.read().decode("utf-8"))

        detail_map = {item["id"]: item for item in v_data.get("items", [])}
        for v in chunk:
            vid = v["video_id"]
            if vid in detail_map:
                detail = detail_map[vid]
                snip = detail.get("snippet", {})
                stats = detail.get("statistics", {})
                content = detail.get("contentDetails", {})
                status = detail.get("status", {})

                v["tags"] = snip.get("tags", [])
                v["category_id"] = snip.get("categoryId", "")
                v["duration"] = content.get("duration", "")
                v["view_count"] = stats.get("viewCount", "0")
                v["like_count"] = stats.get("likeCount", "0")
                v["comment_count"] = stats.get("commentCount", "0")
                v["privacy_status"] = status.get("privacyStatus", "")
            enriched_videos.append(v)

    # 4. Save to JSON
    out_dir = ROOT_DIR / "data"
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "channel_inventory.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(enriched_videos, f, indent=4)

    # 5. Save to Markdown Report
    md_path = out_dir / "channel_inventory.md"
    lines = [
        f"# 📋 Unstocks Video Survey Report",
        f"",
        f"**Channel:** {channel_title} (`@unstocks`)  ",
        f"**Total Videos Surveyed:** {len(enriched_videos)}  ",
        f"",
        f"| # | Video ID | Current Title | Privacy | Views | Published At | Watch Link |",
        f"| :--- | :--- | :--- | :--- | :--- | :--- | :--- |",
    ]
    for idx, v in enumerate(enriched_videos, 1):
        clean_title = v["title"].replace("|", "-")
        lines.append(
            f"| {idx} | `{v['video_id']}` | **{clean_title}** | `{v.get('privacy_status', 'public')}` | {v.get('view_count', '0')} | {v['published_at'][:10]} | [Watch]({v['url']}) |"
        )

    lines.append("")
    lines.append("## Detailed Video Inventory & Content Context\n")
    for idx, v in enumerate(enriched_videos, 1):
        lines.append(f"### Video {idx}: {v['title']}")
        lines.append(f"- **ID:** `{v['video_id']}`")
        lines.append(f"- **URL:** {v['url']}")
        lines.append(f"- **Published:** {v['published_at']}")
        lines.append(f"- **Duration:** `{v.get('duration', '')}` | **Views:** `{v.get('view_count', '0')}` | **Privacy:** `{v.get('privacy_status', '')}`")
        lines.append(f"- **Category:** `{v.get('category_id', '')}`")
        lines.append(f"- **Tags:** {', '.join(v.get('tags', [])) or 'None'}")
        lines.append(f"- **Current Description:**\n```\n{v['description']}\n```\n")

    with open(md_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    print(f"\n✅ Survey completed successfully!")
    print(f"📄 Detailed JSON saved to: {json_path}")
    print(f"📊 Detailed Markdown Report saved to: {md_path}")
    print(f"\nFound {len(enriched_videos)} total videos on @unstocks.\n")

    for idx, v in enumerate(enriched_videos, 1):
        print(f" {idx}. [{v['video_id']}] {v['title']} (Views: {v.get('view_count', '0')})")

    return enriched_videos


if __name__ == "__main__":
    fetch_all_channel_videos()
