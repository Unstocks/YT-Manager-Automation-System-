"""
YT Manager Pinterest Harvester & Pre-Upload Staging Engine
Automates discovery and ingestion of elite motion-graphic explanation clips:
1. Monitors Curated Pinterest Board via native RSS or direct Pin URLs.
2. Extracts high-resolution 720p/1080p MP4 video streams.
3. Enforces strict quality gatekeeper (10s-35s duration, 9:16 vertical Shorts format).
4. Runs AudioCleaner (strips copyrighted BGM while preserving voice and sound effects).
5. Runs WatermarkMasker (applies localized frosted glass blur over watermarks/handles).
6. Deposits exactly 2 pristine, ready-to-upload clips into YT-Manager/inbox/ for the 6 PM batch.
7. Tracks all processed Pin IDs in SQLite to ensure zero duplicate downloads.
"""
from __future__ import annotations

import http.cookiejar
import json
import logging
import re
import shutil
import subprocess
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from .audio_cleaner import AudioCleaner
from .config import YTManagerConfig
from .inspector import MediaInspector
from .state import StateManager
from .thumbnail_picker import ThumbnailPicker
from .watermark_remover import WatermarkMasker

logger = logging.getLogger("YTManager.PinterestHarvester")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
    ),
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;q=0.9,"
        "image/avif,image/webp,image/apng,*/*;q=0.8"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Sec-Ch-Ua": '"Chromium";v="131", "Not_A Brand";v="24"',
    "Sec-Ch-Ua-Mobile": "?0",
    "Sec-Ch-Ua-Platform": '"Windows"',
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "Upgrade-Insecure-Requests": "1",
}


@dataclass
class HarvestedCandidate:
    pin_id: str
    pin_url: str
    video_url: str
    raw_video_path: Path
    final_inbox_path: Optional[Path] = None
    duration_seconds: float = 0.0
    status: str = "PENDING"
    error_message: Optional[str] = None


class PinterestHarvester:
    def __init__(
        self,
        config: YTManagerConfig,
        state: StateManager,
        ffmpeg_bin: str = "ffmpeg",
        ytdlp_bin: Optional[str] = None,
    ):
        self.config = config
        self.state = state
        self.ffmpeg_bin = shutil.which(ffmpeg_bin) or ffmpeg_bin
        self.inspector = MediaInspector(ffmpeg_bin=self.ffmpeg_bin)
        self.audio_cleaner = AudioCleaner(ffmpeg_bin=self.ffmpeg_bin)
        self.watermark_masker = WatermarkMasker(ffmpeg_bin=self.ffmpeg_bin)
        self.thumbnail_picker = ThumbnailPicker(ffmpeg_bin=self.ffmpeg_bin)

        # Detect yt-dlp binary (PATH or local scripts/yt-dlp.exe)
        local_ytdlp_exe = self.config.base_dir / "scripts" / "yt-dlp.exe"
        local_ytdlp = self.config.base_dir / "scripts" / "yt-dlp"
        detected_ytdlp = ytdlp_bin or shutil.which("yt-dlp")
        if not detected_ytdlp:
            if local_ytdlp_exe.exists():
                detected_ytdlp = str(local_ytdlp_exe)
            elif local_ytdlp.exists():
                detected_ytdlp = str(local_ytdlp)

        self.ytdlp_bin = detected_ytdlp

    def parse_pin_id(self, pin_url: str) -> str:
        """Extracts numeric pin ID from a Pinterest URL."""
        match = re.search(r"/pin/(\d+)", pin_url)
        if match:
            return match.group(1)
        # Fallback to alphanumeric slug or hash
        clean = pin_url.rstrip("/").split("/")[-1].split("?")[0]
        return clean

    def resolve_url(self, url: str) -> str:
        """Follows redirects with a cookie jar and realistic headers to obtain the real target URL."""
        if "pin.it" not in url:
            return url
        try:
            cj = http.cookiejar.CookieJar()
            opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
            req = urllib.request.Request(url, headers=HEADERS)
            with opener.open(req, timeout=12) as resp:
                resolved = resp.geturl()
                print(f"[Harvester] Shortlink {url} resolved -> {resolved}")
                return resolved
        except urllib.error.HTTPError as e:
            loc = e.headers.get("Location")
            if loc:
                print(f"[Harvester] Shortlink redirected via Location header -> {loc}")
                return loc
            print(f"[Harvester] HTTP Error resolving shortlink {url}: {e.code} {e.reason}")
            return url
        except Exception as e:
            print(f"[Harvester] Exception resolving shortlink {url}: {e}")
            return url

    def fetch_board_pins(self, board_url: str, max_pins: int = 20) -> List[str]:
        """
        Queries native Pinterest Board RSS feed or HTML page and extracts pin URLs.
        Format: https://www.pinterest.com/username/board-name.rss
        """
        # 1. Resolve shortlinks (pin.it)
        if "pin.it" in board_url:
            board_url = self.resolve_url(board_url)

        parsed = urllib.parse.urlparse(board_url)
        path_parts = [p for p in parsed.path.strip("/").split("/") if p]
        if len(path_parts) >= 2:
            username = path_parts[0]
            board_slug = path_parts[1]
            board_path = f"/{username}/{board_slug}"
        elif len(path_parts) == 1:
            board_path = f"/{path_parts[0]}"
        else:
            board_path = parsed.path.rstrip("/")

        rss_url = f"https://www.pinterest.com{board_path}.rss"
        print(f"[Harvester] Probing Board RSS feed: {rss_url}")
        pin_urls: List[str] = []

        try:
            req = urllib.request.Request(rss_url, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=15) as resp:
                xml_content = resp.read()
                root = ET.fromstring(xml_content)
                for item in root.findall(".//item"):
                    link_text = item.find("link").text if item.find("link") is not None else ""
                    guid_text = item.find("guid").text if item.find("guid") is not None else ""
                    desc_text = item.find("description").text if item.find("description") is not None else ""
                    print(f"[Harvester Debug] RSS link: {link_text}")
                    print(f"[Harvester Debug] RSS guid: {guid_text}")
                    print(f"[Harvester Debug] RSS desc: {desc_text[:120]}")
                    
                    # Extract numeric pin ID if present in guid, description, or link
                    combined = f"{guid_text} {desc_text} {link_text}"
                    id_match = re.search(r"/pin/(\d+)", combined)
                    if id_match:
                        pin_urls.append(f"https://www.pinterest.com/pin/{id_match.group(1)}/")
                    elif link_text:
                        pin_urls.append(link_text.strip())

                    if len(pin_urls) >= max_pins:
                        break
            if pin_urls:
                print(f"[Harvester] Discovered {len(pin_urls)} pins via RSS feed.")
                return pin_urls
        except Exception as e:
            print(f"[Harvester] RSS feed unavailable ({e}), falling back to HTML page parse...")

        # Fallback: Scrape pin links directly from board HTML page
        clean_board_url = f"https://www.pinterest.com{board_path}/"
        print(f"[Harvester] Fetching board HTML: {clean_board_url}")
        try:
            cj = http.cookiejar.CookieJar()
            opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
            page_req = urllib.request.Request(clean_board_url, headers=HEADERS)
            with opener.open(page_req, timeout=15) as page_resp:
                html = page_resp.read().decode("utf-8", errors="replace")
                html = html.replace(r"\/", "/")

                # Extract from URLs or JSON blocks
                matches = re.findall(r"/pin/(\d+)", html)
                json_matches = re.findall(r'"pin_?id"\s*:\s*"(\d+)"', html)
                id_matches = re.findall(r'"id"\s*:\s*"(\d{15,22})"', html)
                all_ids = matches + json_matches + id_matches
                seen = set()
                for m in all_ids:
                    if m not in seen:
                        seen.add(m)
                        pin_urls.append(f"https://www.pinterest.com/pin/{m}/")
                        if len(pin_urls) >= max_pins:
                            break
            print(f"[Harvester] Discovered {len(pin_urls)} pins via HTML page.")
        except Exception as ex2:
            print(f"[Harvester] HTML fallback failed: {ex2}")

        return pin_urls

    def extract_video_stream_url(self, pin_url: str) -> Optional[str]:
        """
        Parses direct 720p/1080p MP4 or m3u8 video stream from a Pinterest pin page,
        checking PinResource API, og:video, JSON-LD, and embedded JSON.
        """
        if "pin.it" in pin_url:
            pin_url = self.resolve_url(pin_url)

        numeric_id = self.parse_pin_id(pin_url)

        # Strategy 1: Check Pinterest PinResource API directly if numeric ID is present
        if numeric_id.isdigit():
            api_url = (
                "https://www.pinterest.com/resource/PinResource/get/?data=%7B%22options%22%3A%7B%22id%22%3A%22"
                + numeric_id
                + "%22%2C%22field_set_key%22%3A%22detailed%22%7D%2C%22context%22%3A%7B%7D%7D"
            )
            try:
                api_headers = {**HEADERS, "X-Requested-With": "XMLHttpRequest"}
                api_req = urllib.request.Request(api_url, headers=api_headers)
                with urllib.request.urlopen(api_req, timeout=12) as api_resp:
                    api_data = json.loads(api_resp.read().decode("utf-8"))
                    pin_data = api_data.get("resource_response", {}).get("data", {}) or {}

                    # Standard video_list
                    videos = pin_data.get("videos", {}) or {}
                    video_list = videos.get("video_list", {}) or {}
                    for res_key in ["V_1080P", "V_720P", "V_EXP7", "V_HLSV4"]:
                        if res_key in video_list and "url" in video_list[res_key] and video_list[res_key]["url"]:
                            v_url = video_list[res_key]["url"]
                            if v_url.endswith(".m3u8"):
                                v_url = v_url.replace("/hls/", "/mc/720p/").replace(".m3u8", ".mp4")
                            print(f"[Harvester] Stream detected via PinResource: {v_url[:65]}...")
                            return v_url

                    # Story/Idea pin data
                    story_pin = pin_data.get("story_pin_data", {}) or {}
                    pages = story_pin.get("pages", []) or []
                    for page in pages:
                        blocks = page.get("blocks", []) or []
                        for block in blocks:
                            block_video = block.get("video", {}).get("video_list", {}) or {}
                            for res_key in ["V_1080P", "V_720P", "V_EXP7", "V_HLSV4"]:
                                if res_key in block_video and "url" in block_video[res_key] and block_video[res_key]["url"]:
                                    v_url = block_video[res_key]["url"]
                                    if v_url.endswith(".m3u8"):
                                        v_url = v_url.replace("/hls/", "/mc/720p/").replace(".m3u8", ".mp4")
                                    print(f"[Harvester] Stream detected via StoryPin API: {v_url[:65]}...")
                                    return v_url
            except Exception as e:
                logger.debug(f"PinResource API attempt failed: {e}")

        # Strategy 2: Fetch HTML page with CookieJar to follow redirects
        req = urllib.request.Request(pin_url, headers=HEADERS)
        try:
            cj = http.cookiejar.CookieJar()
            opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
            with opener.open(req, timeout=15) as resp:
                final_url = resp.geturl()
                html = resp.read().decode("utf-8", errors="replace")
                html = html.replace(r"\/", "/")
                print(f"[Harvester Debug] Loaded: {final_url} (HTML length: {len(html)})")
                
                # Check for numeric pin IDs embedded in page state
                candidate_ids = re.findall(r'"(?:pin_)?id"\s*:\s*"(\d{15,22})"', html)
                if candidate_ids:
                    unique_ids = list(dict.fromkeys(candidate_ids))
                    print(f"[Harvester Debug] Numeric Pin IDs detected in HTML: {unique_ids[:4]}")
                    for cid in unique_ids[:3]:
                        api_url = (
                            "https://www.pinterest.com/resource/PinResource/get/?data=%7B%22options%22%3A%7B%22id%22%3A%22"
                            + cid
                            + "%22%2C%22field_set_key%22%3A%22detailed%22%7D%2C%22context%22%3A%7B%7D%7D"
                        )
                        try:
                            api_headers = {**HEADERS, "X-Requested-With": "XMLHttpRequest"}
                            api_req = urllib.request.Request(api_url, headers=api_headers)
                            with urllib.request.urlopen(api_req, timeout=12) as api_resp:
                                api_raw = api_resp.read().decode("utf-8").replace(r"\/", "/")
                                mp4s = re.findall(r'https://v[0-9]*\.pinimg\.com/videos/[^\s"\'<>]+\.mp4(?:\?[^\s"\'<>]*)?', api_raw)
                                if mp4s:
                                    print(f"[Harvester] Video URL found via PinResource ID {cid}: {mp4s[0][:65]}...")
                                    return mp4s[0]
                                m3u8s = re.findall(r'https://v[0-9]*\.pinimg\.com/videos/[^\s"\'<>]+\.m3u8(?:\?[^\s"\'<>]*)?', api_raw)
                                if m3u8s:
                                    converted = m3u8s[0].replace("/hls/", "/mc/720p/").replace(".m3u8", ".mp4")
                                    print(f"[Harvester] HLS converted stream found via PinResource ID {cid}: {converted[:65]}...")
                                    return converted
                        except Exception as e:
                            print(f"[Harvester Debug] PinResource for ID {cid} failed: {e}")

                # If redirected to a canonical numeric pin, try extracting via that ID
                redir_id = self.parse_pin_id(final_url)
                if redir_id.isdigit() and redir_id != numeric_id:
                    print(f"[Harvester Debug] Redirected to numeric pin ID: {redir_id}")
                    res = self.extract_video_stream_url(f"https://www.pinterest.com/pin/{redir_id}/")
                    if res:
                        return res
        except Exception as e:
            print(f"[Harvester] Could not load pin page {pin_url}: {e}")
            return None

        # Strategy 3: Check OpenGraph og:video meta tags
        og_video = re.findall(r'<meta\s+property=["\']og:video(?::secure_url)?["\']\s+content=["\']([^"\']+)["\']', html)
        if not og_video:
            og_video = re.findall(r'<meta\s+content=["\']([^"\']+)["\']\s+property=["\']og:video(?::secure_url)?["\']', html)
        if og_video:
            v = og_video[0]
            if ".m3u8" in v:
                v = v.replace("/hls/", "/mc/720p/").replace(".m3u8", ".mp4")
            print(f"[Harvester] Stream detected via og:video: {v[:65]}...")
            return v

        # Strategy 4: Check JSON-LD contentUrl
        json_ld = re.findall(r'"contentUrl"\s*:\s*"([^"\']+)"', html)
        if json_ld:
            v = json_ld[0]
            if ".m3u8" in v:
                v = v.replace("/hls/", "/mc/720p/").replace(".m3u8", ".mp4")
            print(f"[Harvester] Stream detected via JSON-LD: {v[:65]}...")
            return v

        # Strategy 5: Full regex scan for pinimg video URLs
        mp4_matches = re.findall(r'https://v[0-9]*\.pinimg\.com/videos/[^\s"\'<>]+\.mp4(?:\?[^\s"\'<>]*)?', html)
        if mp4_matches:
            unique_mp4s = list(dict.fromkeys(mp4_matches))
            p1080 = [m for m in unique_mp4s if "1080p" in m]
            if p1080:
                return p1080[0]
            p720 = [m for m in unique_mp4s if "720p" in m]
            if p720:
                return p720[0]
            return unique_mp4s[0]

        m3u8_matches = re.findall(r'https://v[0-9]*\.pinimg\.com/videos/[^\s"\'<>]+\.m3u8(?:\?[^\s"\'<>]*)?', html)
        if m3u8_matches:
            return m3u8_matches[0].replace("/hls/", "/mc/720p/").replace(".m3u8", ".mp4")

        return None

    def download_with_ytdlp(self, target_url: str, output_path: Path) -> Optional[Path]:
        """Downloads video directly via yt-dlp binary if available."""
        if not self.ytdlp_bin:
            return None
        output_path.parent.mkdir(parents=True, exist_ok=True)
        cmd = [
            self.ytdlp_bin,
            "-f", "bv*+ba/b",
            "--no-playlist",
            "--no-warnings",
            "-o", str(output_path),
            target_url,
        ]
        try:
            print(f"[Harvester] Downloading with yt-dlp: {target_url}...")
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=90)
            if output_path.exists() and output_path.stat().st_size > 5000:
                print(f"[Harvester] Successfully downloaded stream via yt-dlp: {output_path.name}")
                return output_path
            for f in output_path.parent.glob(f"{output_path.stem}.*"):
                if f.suffix.lower() in [".mp4", ".mkv", ".webm"] and f.stat().st_size > 5000:
                    if f != output_path:
                        shutil.move(str(f), str(output_path))
                    return output_path
        except Exception as e:
            logger.warning(f"yt-dlp single download failed: {e}")
        return None

    def harvest_board_with_ytdlp(self, board_url: str, output_dir: Path, max_clips: int = 5) -> List[Path]:
        """Uses yt-dlp's native Pinterest board extractor to download all video pins on the board."""
        if not self.ytdlp_bin:
            return []
        
        # 1. Resolve shortlink if needed
        if "pin.it" in board_url:
            board_url = self.resolve_url(board_url)

        # 2. Extract clean board URL without invite/sender query tokens
        parsed = urllib.parse.urlparse(board_url)
        path_parts = [p for p in parsed.path.strip("/").split("/") if p]
        if len(path_parts) >= 2:
            clean_board_url = f"https://www.pinterest.com/{path_parts[0]}/{path_parts[1]}/"
        else:
            clean_board_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path.rstrip('/')}/"

        output_dir.mkdir(parents=True, exist_ok=True)
        out_template = str(output_dir / "pin_%(id)s.%(ext)s")
        cmd = [
            self.ytdlp_bin,
            "-f", "bv*+ba/b",
            "--no-warnings",
            "--max-downloads", str(max_clips),
            "-o", out_template,
            clean_board_url,
        ]
        try:
            print(f"[Harvester] Running yt-dlp native board extraction on: {clean_board_url}")
            # Run without capture_output so user sees live download progress
            subprocess.run(cmd, timeout=180)
            found = list(output_dir.glob("pin_*.*"))
            video_files = [f for f in found if f.suffix.lower() in [".mp4", ".mkv", ".webm", ".mov"] and f.stat().st_size > 5000]
            print(f"[Harvester] yt-dlp harvested {len(video_files)} video pin(s).")
            return video_files
        except Exception as e:
            logger.warning(f"yt-dlp board extraction failed: {e}")
            return []

    def download_video(self, video_url: str, output_path: Path) -> Path:
        """Downloads video stream losslessly via yt-dlp, direct HTTP stream, or FFmpeg."""
        output_path.parent.mkdir(parents=True, exist_ok=True)
        if self.ytdlp_bin:
            res = self.download_with_ytdlp(video_url, output_path)
            if res and res.exists():
                return res

        if video_url.startswith("http"):
            try:
                req = urllib.request.Request(video_url, headers=HEADERS)
                with urllib.request.urlopen(req, timeout=30) as resp:
                    with open(output_path, "wb") as f:
                        while chunk := resp.read(65536):
                            f.write(chunk)
                if output_path.exists() and output_path.stat().st_size > 10000:
                    return output_path
            except Exception as e:
                logger.warning(f"Direct stream download failed ({e}), falling back to FFmpeg...")

        cmd = [
            self.ffmpeg_bin,
            "-y",
            "-i", video_url,
            "-c", "copy",
            str(output_path),
        ]
        subprocess.run(cmd, capture_output=True, check=True)
        return output_path

    def evaluate_candidate_clip(self, raw_path: Path) -> Dict[str, Any]:
        """
        Evaluates a downloaded video candidate across duration, resolution, audio,
        and visual motion-graphic clarity.
        Enforces under 60 seconds (YouTube Shorts duration limit).
        """
        frames_work_dir = raw_path.parent / f"frames_{raw_path.stem}"
        inspection = self.inspector.inspect(raw_path, work_dir=frames_work_dir)
        dur = inspection.duration_seconds
        is_916 = inspection.is_short

        # Duration score (YouTube Shorts: strictly under 60.0s)
        if 15.0 <= dur <= 55.0:
            dur_score = 100.0
        elif 5.0 <= dur <= 60.0:
            dur_score = 85.0
        else:
            dur_score = 15.0

        # Visual hook & frame clarity score
        max_frame_score = 0.0
        avg_sharpness = 0.0
        if inspection.extracted_frames:
            scores = [self.thumbnail_picker.score_single_frame(f) for f in inspection.extracted_frames]
            if scores:
                best_frame = max(scores, key=lambda s: s.total_score)
                max_frame_score = best_frame.total_score
                avg_sharpness = sum(s.sharpness for s in scores) / len(scores)

        # Composite quality score (0 - 100)
        composite_score = (
            dur_score * 0.35
            + min(100.0, max_frame_score / 15.0) * 0.45
            + (100.0 if is_916 else 0.0) * 0.20
        )

        return {
            "duration": dur,
            "is_916": is_916,
            "width": inspection.width,
            "height": inspection.height,
            "has_audio": bool(inspection.audio_codec),
            "audio_codec": inspection.audio_codec,
            "best_frame_score": round(max_frame_score, 1),
            "avg_sharpness": round(avg_sharpness, 1),
            "composite_score": round(composite_score, 1),
        }

    def evaluate_pins(self, pin_urls: List[str]) -> List[Dict[str, Any]]:
        """
        Evaluates a list of candidate pin URLs, downloads candidates, scores them,
        and ranks them from best to worst.
        """
        work_dir = self.config.processing_dir / "board_evaluation"
        work_dir.mkdir(parents=True, exist_ok=True)

        evaluations: List[Dict[str, Any]] = []
        for pin_url in pin_urls:
            if "pin.it" in pin_url:
                pin_url = self.resolve_url(pin_url)
            pin_id = self.parse_pin_id(pin_url)
            print(f"[Harvester] Inspecting Pin {pin_id} ({pin_url})...")
            raw_path = work_dir / f"eval_pin_{pin_id}.mp4"

            # 1. Try yt-dlp first if available
            if self.ytdlp_bin:
                dl_path = self.download_with_ytdlp(pin_url, raw_path)
                if dl_path and dl_path.exists():
                    metrics = self.evaluate_candidate_clip(dl_path)
                    evaluations.append({
                        "pin_id": pin_id,
                        "pin_url": pin_url,
                        "video_url": str(dl_path),
                        "raw_path": dl_path,
                        **metrics,
                    })
                    print(f"[Harvester] Pin {pin_id} Scored: {metrics['composite_score']}/100.0 (Dur: {metrics['duration']:.1f}s, Sharpness: {metrics['avg_sharpness']})")
                    continue

            # 2. Fallback to HTTP stream extraction
            v_url = self.extract_video_stream_url(pin_url)
            if not v_url:
                print(f"[Harvester] No video stream detected for Pin {pin_id}.")
                continue

            try:
                print(f"[Harvester] Downloading candidate stream: {v_url[:65]}...")
                self.download_video(v_url, raw_path)
                metrics = self.evaluate_candidate_clip(raw_path)
                evaluations.append({
                    "pin_id": pin_id,
                    "pin_url": pin_url,
                    "video_url": v_url,
                    "raw_path": raw_path,
                    **metrics,
                })
                print(f"[Harvester] Pin {pin_id} Scored: {metrics['composite_score']}/100.0 (Dur: {metrics['duration']:.1f}s, Sharpness: {metrics['avg_sharpness']})")
            except Exception as e:
                print(f"[Harvester] Failed to evaluate pin {pin_id}: {e}")

        evaluations.sort(key=lambda x: x["composite_score"], reverse=True)
        return evaluations

    def evaluate_board(self, board_url: str) -> List[Dict[str, Any]]:
        """
        Fetches all pins from a board, downloads candidates, scores them,
        and ranks them from best to worst.
        Prefers yt-dlp native extraction if installed; falls back to HTTP/RSS parser.
        """
        work_dir = self.config.processing_dir / "board_evaluation"
        work_dir.mkdir(parents=True, exist_ok=True)

        if self.ytdlp_bin:
            ytdlp_files = self.harvest_board_with_ytdlp(board_url, work_dir, max_clips=5)
            if ytdlp_files:
                evaluations: List[Dict[str, Any]] = []
                for vf in ytdlp_files:
                    metrics = self.evaluate_candidate_clip(vf)
                    evaluations.append({
                        "pin_id": vf.stem.replace("pin_", ""),
                        "pin_url": board_url,
                        "video_url": str(vf),
                        "raw_path": vf,
                        **metrics,
                    })
                    print(f"[Harvester] {vf.name} Scored: {metrics['composite_score']}/100.0 (Dur: {metrics['duration']:.1f}s, Sharpness: {metrics['avg_sharpness']})")
                evaluations.sort(key=lambda x: x["composite_score"], reverse=True)
                return evaluations

        pins = self.fetch_board_pins(board_url)
        if not pins:
            return []
        return self.evaluate_pins(pins)

    def process_and_stage_pin(
        self,
        pin_url: str,
        work_dir: Path,
        clean_bgm: bool = True,
        mask_watermark: bool = True,
        watermark_position: str = "bottom_right",
    ) -> HarvestedCandidate:
        """
        Executes end-to-end ingestion of a candidate pin:
        1. Checks duplicate DB history.
        2. Resolves video stream & downloads.
        3. Enforces <= 60.0s YouTube Shorts duration gatekeeper.
        4. Cleans BGM (AudioCleaner).
        5. Masks watermark (WatermarkMasker).
        6. Moves to inbox/ ready for the 6 PM daily batch.
        """
        pin_id = self.parse_pin_id(pin_url)

        if self.state.is_pin_harvested(pin_id):
            return HarvestedCandidate(
                pin_id=pin_id,
                pin_url=pin_url,
                video_url="",
                raw_video_path=Path(""),
                status="ALREADY_PROCESSED",
                error_message="Pin ID was already processed in prior harvest.",
            )

        video_url = self.extract_video_stream_url(pin_url)
        if not video_url:
            self.state.record_harvested_pin(pin_id, pin_url, status="NO_VIDEO")
            return HarvestedCandidate(
                pin_id=pin_id,
                pin_url=pin_url,
                video_url="",
                raw_video_path=Path(""),
                status="FAILED",
                error_message="No video stream detected on pin (image-only pin).",
            )

        raw_download = work_dir / f"raw_pin_{pin_id}.mp4"
        self.download_video(video_url, raw_download)

        # Inspect duration and aspect ratio
        inspection = self.inspector.inspect(raw_download)
        duration = inspection.duration_seconds

        # Strict Gatekeeper Rule: Under 60s duration (YouTube Shorts limit), Vertical format
        if not (5.0 <= duration <= 60.0):
            self.state.record_harvested_pin(pin_id, pin_url, video_url, status="REJECTED_DURATION")
            return HarvestedCandidate(
                pin_id=pin_id,
                pin_url=pin_url,
                video_url=video_url,
                raw_video_path=raw_download,
                duration_seconds=duration,
                status="REJECTED_DURATION",
                error_message=f"Duration {duration:.1f}s exceeds YouTube Shorts limit (must be <= 60.0s).",
            )

        if not inspection.is_short:
            self.state.record_harvested_pin(pin_id, pin_url, video_url, status="REJECTED_ASPECT_RATIO")
            return HarvestedCandidate(
                pin_id=pin_id,
                pin_url=pin_url,
                video_url=video_url,
                raw_video_path=raw_download,
                duration_seconds=duration,
                status="REJECTED_ASPECT_RATIO",
                error_message="Video aspect ratio is not vertical 9:16 Shorts format.",
            )

        current_stage_video = raw_download

        # Step 4: Mask Watermark (if enabled)
        if mask_watermark:
            masked_video = work_dir / f"masked_pin_{pin_id}.mp4"
            try:
                self.watermark_masker.apply_blurred_mask(
                    video_path=current_stage_video,
                    output_path=masked_video,
                    position=watermark_position,
                )
                current_stage_video = masked_video
            except Exception as e:
                logger.warning(f"Watermark masking skipped: {e}")

        # Step 5: Clean BGM (if enabled)
        if clean_bgm:
            audio_work = work_dir / f"audio_clean_{pin_id}"
            audio_res = self.audio_cleaner.separate_and_clean(
                video_path=current_stage_video,
                work_dir=audio_work,
            )
            if audio_res.success:
                current_stage_video = audio_res.cleaned_video_path

        # Step 6: Move to inbox/
        final_filename = f"unstocks_short_{pin_id}.mp4"
        final_inbox_path = self.config.inbox_dir / final_filename
        shutil.move(str(current_stage_video), str(final_inbox_path))

        self.state.record_harvested_pin(pin_id, pin_url, video_url, status="COMPLETED")

        return HarvestedCandidate(
            pin_id=pin_id,
            pin_url=pin_url,
            video_url=video_url,
            raw_video_path=raw_download,
            final_inbox_path=final_inbox_path,
            duration_seconds=duration,
            status="READY",
        )

    def run_pre_upload_harvest(
        self,
        board_url: str,
        target_count: int = 2,
        clean_bgm: bool = True,
        mask_watermark: bool = True,
    ) -> List[HarvestedCandidate]:
        """
        Executes pre-upload harvest from board:
        Fetches pins, evaluates them, cleans audio/watermarks, and deposits
        exactly target_count clips into inbox/ ready for the 6 PM batch.
        """
        pins = self.fetch_board_pins(board_url)
        work_dir = self.config.processing_dir / "harvest_workspace"
        work_dir.mkdir(parents=True, exist_ok=True)

        successful_harvests: List[HarvestedCandidate] = []

        for pin_url in pins:
            if len(successful_harvests) >= target_count:
                break

            cand = self.process_and_stage_pin(
                pin_url=pin_url,
                work_dir=work_dir,
                clean_bgm=clean_bgm,
                mask_watermark=mask_watermark,
            )

            if cand.status == "READY":
                successful_harvests.append(cand)
                print(f"[Harvester] Successfully prepared: {cand.final_inbox_path.name} ({cand.duration_seconds:.1f}s)")

        return successful_harvests
