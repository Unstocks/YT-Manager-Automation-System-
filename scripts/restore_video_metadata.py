"""
Unstocks Video Metadata Restoration Engine
Restores or surgically updates video titles, descriptions, and tags
from a customized restoration plan (data/restore_plan.json).
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


def apply_restore_plan(plan_path: Optional[Path] = None) -> None:
    config = YTManagerConfig.load()
    auth = YouTubeAuthManager(config)
    token = auth.get_valid_access_token()

    target_file = plan_path or (ROOT_DIR / "data" / "restore_plan.json")
    if not target_file.exists():
        print(f"❌ Restore plan file not found at: {target_file}")
        print("Run scripts/survey_channel.py first or populate data/restore_plan.json.")
        return

    with open(target_file, "r", encoding="utf-8") as f:
        plan = json.load(f)

    print("=" * 70)
    print(f"🔄 APPLYING METADATA RESTORATION PLAN ({len(plan)} videos)")
    print("=" * 70)

    for item in plan:
        vid = item.get("video_id")
        new_title = item.get("title")
        new_desc = item.get("description", "")
        new_tags = item.get("tags", [])
        new_cat = item.get("category_id", "27")

        if not vid or not new_title:
            continue

        print(f"\n🎬 Restoring Video: [{vid}] -> '{new_title}'")

        # Fetch current snippet to keep required fields
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
            print(f" ❌ Failed to fetch current details for [{vid}]: {e}")
            continue

        snippet["title"] = new_title
        snippet["description"] = new_desc
        if new_tags:
            snippet["tags"] = new_tags
        if new_cat:
            snippet["categoryId"] = new_cat

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
                print(f" ✅ Restored Video [{vid}] successfully!")
        except Exception as e:
            print(f" ❌ Failed to restore Video [{vid}]: {e}")

    print("\n🎉 Restoration complete!")


if __name__ == "__main__":
    apply_restore_plan()
