"""
Unstocks Channel Undo & Cleanup Engine
Privatizes or Deletes the test videos that were mistakenly uploaded during testing:
- dNrMoLs5VOY (kitchen_organization_ideas.mp4)
- wuMZFV_zse8 (flower_bed_ideas.mp4)
- 9PK37JRn6C8 (test pin clip)
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

TEST_VIDEO_IDS = [
    "dNrMoLs5VOY",  # kitchen_organization_ideas
    "wuMZFV_zse8",  # flower_bed_ideas
    "9PK37JRn6C8",  # test clip
]


def delete_video(video_id: str, token: str) -> bool:
    url = f"https://www.googleapis.com/youtube/v3/videos?id={video_id}"
    req = urllib.request.Request(
        url,
        headers={"Authorization": f"Bearer {token}"},
        method="DELETE",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            print(f"🗑️ Deleted video [{video_id}] permanently from channel.")
            return True
    except urllib.error.HTTPError as e:
        if e.code == 404:
            print(f"ℹ️ Video [{video_id}] is already deleted or not found.")
            return True
        print(f"❌ Failed to delete video [{video_id}]: HTTP {e.code}")
        return False


def privatize_video(video_id: str, token: str) -> bool:
    # First get current snippet
    get_url = f"https://www.googleapis.com/youtube/v3/videos?part=snippet,status&id={video_id}"
    req = urllib.request.Request(get_url, headers={"Authorization": f"Bearer {token}"})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        print(f"❌ Could not retrieve video [{video_id}]: {e}")
        return False

    items = data.get("items", [])
    if not items:
        print(f"ℹ️ Video [{video_id}] not found.")
        return True

    item = items[0]
    snippet = item["snippet"]
    status = item["status"]
    status["privacyStatus"] = "private"

    update_url = "https://www.googleapis.com/youtube/v3/videos?part=snippet,status"
    update_data = {
        "id": video_id,
        "snippet": snippet,
        "status": status,
    }
    req_update = urllib.request.Request(
        update_url,
        data=json.dumps(update_data).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        method="PUT",
    )
    try:
        with urllib.request.urlopen(req_update, timeout=30) as resp:
            print(f"🔒 Set video [{video_id}] to PRIVATE.")
            return True
    except Exception as e:
        print(f"❌ Failed to privatize [{video_id}]: {e}")
        return False


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Clean up test videos from @unstocks")
    parser.add_argument("--action", choices=["delete", "privatize"], default="delete", help="Action to take")
    args = parser.parse_args()

    config = YTManagerConfig.load()
    auth = YouTubeAuthManager(config)
    token = auth.get_valid_access_token()

    print("=" * 65)
    print(f"UNSTOCKS CHANNEL CLEANUP: {args.action.upper()} TEST VIDEOS")
    print("=" * 65)
    print(f"Targeting test video IDs: {TEST_VIDEO_IDS}\n")

    for vid in TEST_VIDEO_IDS:
        if args.action == "delete":
            delete_video(vid, token)
        else:
            privatize_video(vid, token)

    print("\n✅ Cleanup operation complete.")


if __name__ == "__main__":
    main()
