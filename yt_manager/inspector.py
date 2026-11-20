"""
YT Manager Media Inspector Module
Executes deep media inspection using ffprobe & ffmpeg:
- Extracts technical metadata (dimensions, aspect ratio, duration, codecs, FPS).
- Detects whether video qualifies as YouTube Short (aspect ratio < 1.0 and <= 60s).
- Extracts keyframes (1 fps, up to 25 frames max) for visual/text understanding.
- Extracts normalized 16kHz mono audio for transcription / speech analysis.
"""
from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class MediaInspection:
    file_path: Path
    duration_seconds: float
    width: int
    height: int
    aspect_ratio: float
    is_short: bool
    video_codec: str
    audio_codec: Optional[str]
    has_audio: bool
    fps: float
    bitrate: int
    extracted_frames: List[Path] = field(default_factory=list)
    extracted_audio_path: Optional[Path] = None
    raw_probe: Dict[str, Any] = field(default_factory=dict)


class MediaInspector:
    def __init__(self, ffmpeg_bin: str = "ffmpeg", ffprobe_bin: str = "ffprobe"):
        self.ffmpeg_bin = shutil.which(ffmpeg_bin) or ffmpeg_bin
        self.ffprobe_bin = shutil.which(ffprobe_bin) or ffprobe_bin

    def probe(self, video_path: Path) -> Dict[str, Any]:
        """Runs ffprobe on the target media file and returns structured JSON."""
        cmd = [
            self.ffprobe_bin,
            "-v", "error",
            "-show_entries", "format=duration,size,bit_rate",
            "-show_entries", "stream=codec_name,codec_type,width,height,channels,sample_rate,r_frame_rate,bit_rate",
            "-of", "json",
            str(video_path),
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return json.loads(result.stdout)

    def extract_keyframes(
        self, video_path: Path, output_dir: Path, fps: float = 1.0, max_frames: int = 25
    ) -> List[Path]:
        """Extracts evenly spaced frames or 1 fps frames up to max_frames."""
        output_dir.mkdir(parents=True, exist_ok=True)
        # Clear existing images in output dir if any
        for old in output_dir.glob("frame_*.jpg"):
            try:
                old.unlink()
            except OSError:
                pass

        pattern = str(output_dir / "frame_%03d.jpg")
        cmd = [
            self.ffmpeg_bin,
            "-y",
            "-i", str(video_path),
            "-vf", f"fps={fps}",
            "-vframes", str(max_frames),
            "-q:v", "3",
            pattern,
        ]
        subprocess.run(cmd, capture_output=True, check=True)
        frames = sorted(list(output_dir.glob("frame_*.jpg")), key=lambda p: p.name)
        return frames

    def extract_audio(self, video_path: Path, output_audio_path: Path) -> Optional[Path]:
        """Extracts mono 16kHz PCM audio stream for speech/transcription processing."""
        output_audio_path.parent.mkdir(parents=True, exist_ok=True)
        cmd = [
            self.ffmpeg_bin,
            "-y",
            "-i", str(video_path),
            "-vn",
            "-acodec", "pcm_s16le",
            "-ar", "16000",
            "-ac", "1",
            str(output_audio_path),
        ]
        try:
            res = subprocess.run(cmd, capture_output=True, text=True)
            if res.returncode == 0 and output_audio_path.exists() and output_audio_path.stat().st_size > 0:
                return output_audio_path
        except Exception:
            pass
        return None

    def inspect(self, video_path: Path, work_dir: Optional[Path] = None) -> MediaInspection:
        """Performs full media inspection, frame extraction, and audio extraction."""
        probe_data = self.probe(video_path)

        streams = probe_data.get("streams", [])
        fmt = probe_data.get("format", {})

        video_stream = next((s for s in streams if s.get("codec_type") == "video"), None)
        audio_stream = next((s for s in streams if s.get("codec_type") == "audio"), None)

        if not video_stream:
            raise ValueError(f"No video stream detected in {video_path}")

        width = int(video_stream.get("width", 0))
        height = int(video_stream.get("height", 0))
        aspect_ratio = (width / height) if height > 0 else 1.0

        duration_sec = float(fmt.get("duration", 0.0))
        bitrate = int(fmt.get("bit_rate", 0)) if fmt.get("bit_rate") else 0
        video_codec = video_stream.get("codec_name", "unknown")
        audio_codec = audio_stream.get("codec_name") if audio_stream else None
        has_audio = audio_stream is not None

        # Calculate FPS
        r_fps = video_stream.get("r_frame_rate", "30/1")
        try:
            num, den = map(int, r_fps.split("/"))
            fps = num / den if den > 0 else 30.0
        except Exception:
            fps = 30.0

        # YouTube Shorts criteria: Vertical/Square (aspect ratio <= 1.0) and duration <= 60 seconds
        is_short = (aspect_ratio <= 1.05) and (duration_sec <= 60.5)

        frames: List[Path] = []
        audio_path: Optional[Path] = None

        if work_dir:
            frames_dir = work_dir / "frames"
            audio_out = work_dir / "audio.wav"

            # Determine frame extraction rate: for short videos <= 25s, 1 fps. For longer videos, up to 20 frames total.
            fps_rate = 1.0 if duration_sec <= 25 else (20.0 / duration_sec)
            frames = self.extract_keyframes(video_path, frames_dir, fps=fps_rate, max_frames=25)
            if has_audio:
                audio_path = self.extract_audio(video_path, audio_out)

        return MediaInspection(
            file_path=video_path,
            duration_seconds=duration_sec,
            width=width,
            height=height,
            aspect_ratio=aspect_ratio,
            is_short=is_short,
            video_codec=video_codec,
            audio_codec=audio_codec,
            has_audio=has_audio,
            fps=fps,
            bitrate=bitrate,
            extracted_frames=frames,
            extracted_audio_path=audio_path,
            raw_probe=probe_data,
        )
