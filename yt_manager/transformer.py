"""
YT Manager High-Fidelity Anti-Copyright Media Transformer Module
Transforms video and audio to neutralize Content ID fingerprinting while preserving
studio-grade 1080p visual sharpness and punchy -14 LUFS broadcast audio dynamics.

Key Transformations:
1. Micro-Speed Adjustment (1.04x) via setpts and pitch-preserved atempo (breaks temporal hashes).
2. Lanczos-Interpolated Micro-Zoom (103%) and Edge Crop (breaks spatial coordinate hashes).
3. Subtle Color Histogram Shift (contrast +4%, brightness +1%, saturation +6%).
4. Audio Enhancement: Highpass rumble cut (75Hz), dynamic leveling (dynaudnorm), and -14 LUFS loudness.
5. Auto-Detection of Silent/Audio-less clips to prevent FFmpeg filter pad errors.
6. Fail-Safe Auto-Fallback to original media if FFmpeg encounters an unexpected codec.
"""
from __future__ import annotations

import logging
import os
import shutil
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from .config import YTManagerConfig

logger = logging.getLogger("YTManager.Transformer")


@dataclass
class TransformationResult:
    success: bool
    input_path: Path
    output_path: Path
    transformed: bool
    has_audio: bool
    duration_seconds: float = 0.0
    processing_time_seconds: float = 0.0
    error_message: Optional[str] = None


class MediaTransformer:
    def __init__(
        self,
        config: YTManagerConfig,
        ffmpeg_bin: str = "ffmpeg",
        ffprobe_bin: str = "ffprobe",
    ):
        self.config = config
        self.ffmpeg_bin = shutil.which(ffmpeg_bin) or ffmpeg_bin
        self.ffprobe_bin = shutil.which(ffprobe_bin) or ffprobe_bin

    def has_audio_stream(self, video_path: Path) -> bool:
        """Determines whether a video file contains at least one audio stream."""
        cmd = [
            self.ffprobe_bin,
            "-v", "error",
            "-select_streams", "a:0",
            "-show_entries", "stream=codec_name",
            "-of", "default=noprint_wrappers=1:nokey=1",
            str(video_path),
        ]
        try:
            res = subprocess.run(cmd, capture_output=True, text=True, check=True)
            return bool(res.stdout.strip())
        except Exception as e:
            logger.debug(f"Audio stream probe failed for {video_path.name}: {e}")
            return False

    def transform_clip(
        self,
        input_path: Path,
        output_path: Path,
        override_speed: Optional[float] = None,
        override_crop: Optional[float] = None,
    ) -> TransformationResult:
        """
        Executes studio-grade, near-lossless anti-copyright transformation on a video clip.
        Guarantees zero pipeline failure by falling back to the original file if needed.
        """
        start_time = time.time()
        output_path.parent.mkdir(parents=True, exist_ok=True)

        if not self.config.enable_video_transformer:
            logger.info("Video transformer disabled via config; passing original media.")
            if input_path.resolve() != output_path.resolve():
                shutil.copy2(str(input_path), str(output_path))
            return TransformationResult(
                success=True,
                input_path=input_path,
                output_path=output_path,
                transformed=False,
                has_audio=self.has_audio_stream(input_path),
                processing_time_seconds=time.time() - start_time,
            )

        speed_factor = override_speed or self.config.transform_speed_factor
        crop_percent = override_crop or self.config.transform_crop_percent
        zoom_factor = round(1.0 + (crop_percent / 100.0), 3)

        contrast = getattr(self.config, "transform_contrast", 1.04)
        brightness = getattr(self.config, "transform_brightness", 0.01)
        saturation = getattr(self.config, "transform_saturation", 1.06)
        crf = getattr(self.config, "transform_crf", 17)
        preset = getattr(self.config, "transform_preset", "fast")

        # Video Filter Chain:
        # 1. Temporal speedup (setpts=PTS/factor)
        # 2. Lanczos-interpolated high-fidelity zoom
        # 3. 3% crop around perimeter
        # 4. Color grading equation pop
        video_filters = [
            f"setpts=PTS/{speed_factor:.3f}",
            f"scale=iw*{zoom_factor:.3f}:ih*{zoom_factor:.3f}:flags=lanczos",
            f"crop=iw/{zoom_factor:.3f}:ih/{zoom_factor:.3f}",
            f"eq=contrast={contrast:.2f}:brightness={brightness:.2f}:saturation={saturation:.2f}",
        ]
        vf_string = ",".join(video_filters)

        # Audio Stream Detection & Filter Chain
        has_audio = self.has_audio_stream(input_path)
        af_string = ""
        if has_audio and self.config.enable_audio_enhancer:
            # 1. Pitch-preserved tempo adjustment (exact lip/visual sync)
            # 2. Rumble cut at 75Hz (protects human vocal warmth)
            # 3. Dynamic audio normalizer (balances quiet & loud passages)
            # 4. EBU R128 YouTube broadcast target (-14 LUFS)
            audio_filters = [
                f"atempo={speed_factor:.3f}",
                "highpass=f=75",
                "dynaudnorm=f=125:g=15:p=0.95:m=10.0:r=0.9",
                "loudnorm=I=-14:TP=-1.5:LRA=11",
            ]
            af_string = ",".join(audio_filters)

        cmd = [
            self.ffmpeg_bin,
            "-y",
            "-i", str(input_path),
            "-vf", vf_string,
        ]

        if af_string:
            cmd.extend([
                "-af", af_string,
                "-c:a", "aac",
                "-b:a", "256k",
                "-ar", "48000",
            ])
        elif has_audio:
            cmd.extend([
                "-af", f"atempo={speed_factor:.3f}",
                "-c:a", "aac",
                "-b:a", "256k",
            ])
        else:
            cmd.append("-an")

        cmd.extend([
            "-c:v", "libx264",
            "-crf", str(crf),
            "-preset", preset,
            "-pix_fmt", "yuv420p",
            str(output_path),
        ])

        try:
            logger.info(
                f"Transforming clip '{input_path.name}' -> '{output_path.name}' "
                f"(Speed: {speed_factor}x, Zoom/Crop: {zoom_factor}x, Audio: {'Enhanced' if af_string else 'Silent/Passthrough'})"
            )
            res = subprocess.run(cmd, capture_output=True, text=True, check=True)
            elapsed = time.time() - start_time
            return TransformationResult(
                success=True,
                input_path=input_path,
                output_path=output_path,
                transformed=True,
                has_audio=has_audio,
                processing_time_seconds=elapsed,
            )

        except Exception as e:
            logger.warning(
                f"Media transformation failed for '{input_path.name}': {e}. "
                "Executing fail-safe fallback: using original un-transformed clip."
            )
            try:
                if input_path.resolve() != output_path.resolve():
                    shutil.copy2(str(input_path), str(output_path))
            except Exception as copy_err:
                logger.error(f"Fallback copy error: {copy_err}")

            return TransformationResult(
                success=False,
                input_path=input_path,
                output_path=output_path if output_path.exists() else input_path,
                transformed=False,
                has_audio=has_audio,
                processing_time_seconds=time.time() - start_time,
                error_message=str(e),
            )
