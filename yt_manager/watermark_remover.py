"""
YT Manager Localized Watermark Masker & Delogo Engine
Removes third-party handles, watermarks, and corner badges without over-scaling,
cropping, or clipping any original text/content margins.
"""
from __future__ import annotations

import logging
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Tuple

logger = logging.getLogger("YTManager.WatermarkMasker")


@dataclass
class WatermarkRegion:
    crop_x: str  # e.g., "in_w-224"
    crop_y: str  # e.g., "in_h-100"
    overlay_x: str  # e.g., "W-224"
    overlay_y: str  # e.g., "H-100"
    w: int  # width of mask box
    h: int  # height of mask box


# Standard preset locations for common social/pin watermarks in 9:16 videos
PRESET_REGIONS = {
    "bottom_right": WatermarkRegion(
        crop_x="in_w-224", crop_y="in_h-100", overlay_x="W-224", overlay_y="H-100", w=200, h=64
    ),
    "bottom_left": WatermarkRegion(
        crop_x="24", crop_y="in_h-100", overlay_x="24", overlay_y="H-100", w=200, h=64
    ),
    "top_right": WatermarkRegion(
        crop_x="in_w-224", crop_y="36", overlay_x="W-224", overlay_y="36", w=200, h=64
    ),
    "top_left": WatermarkRegion(
        crop_x="24", crop_y="36", overlay_x="24", overlay_y="36", w=200, h=64
    ),
}


class WatermarkMasker:
    def __init__(self, ffmpeg_bin: str = "ffmpeg"):
        self.ffmpeg_bin = shutil.which(ffmpeg_bin) or ffmpeg_bin

    def apply_blurred_mask(
        self,
        video_path: Path,
        output_path: Path,
        position: str = "bottom_right",
        custom_region: Optional[WatermarkRegion] = None,
        blur_strength: int = 12,
    ) -> Path:
        """
        Applies a localized frosted glass / Gaussian box-blur strictly to the watermark region.
        The remaining 98% of the video stays 100% untouched and uncropped.
        """
        output_path.parent.mkdir(parents=True, exist_ok=True)
        region = custom_region or PRESET_REGIONS.get(position, PRESET_REGIONS["bottom_right"])

        # Filter complex: crop small patch -> boxblur it -> overlay it back exactly on coordinates
        filter_str = (
            f"[0:v]split=2[base][crop_in]; "
            f"[crop_in]crop={region.w}:{region.h}:{region.crop_x}:{region.crop_y},"
            f"boxblur={blur_strength}:{blur_strength // 2}[blurred]; "
            f"[base][blurred]overlay={region.overlay_x}:{region.overlay_y}:enable='between(t,0,3600)'[outv]"
        )

        cmd = [
            self.ffmpeg_bin,
            "-y",
            "-i", str(video_path),
            "-filter_complex", filter_str,
            "-map", "[outv]",
            "-map", "0:a?",
            "-c:v", "libx264",
            "-crf", "18",
            "-preset", "fast",
            "-c:a", "copy",
            str(output_path),
        ]

        subprocess.run(cmd, capture_output=True, check=True)
        return output_path

    def apply_delogo(
        self,
        video_path: Path,
        output_path: Path,
        x: int,
        y: int,
        w: int,
        h: int,
    ) -> Path:
        """
        Uses FFmpeg's native delogo inpainting algorithm to interpolate surrounding pixels.
        """
        output_path.parent.mkdir(parents=True, exist_ok=True)
        cmd = [
            self.ffmpeg_bin,
            "-y",
            "-i", str(video_path),
            "-vf", f"delogo=x={x}:y={y}:w={w}:h={h}",
            "-c:v", "libx264",
            "-crf", "18",
            "-preset", "fast",
            "-c:a", "copy",
            str(output_path),
        ]
        subprocess.run(cmd, capture_output=True, check=True)
        return output_path
