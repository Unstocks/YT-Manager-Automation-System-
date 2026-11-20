"""
YT Manager Daily Execution Report Generator
Constructs concise, audit-ready daily execution reports matching Section 8 requirements.
Saves reports in logs/reports/daily_report_YYYY-MM-DD.txt and .md.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from .config import YTManagerConfig


@dataclass
class ClipExecutionReport:
    index: int
    original_filename: str
    generated_title: str
    description_status: str
    metadata_status: str
    upload_status: str  # SUCCESS, FAILED, SKIPPED
    youtube_video_id: str
    youtube_url: str
    error_message: Optional[str] = None


@dataclass
class DailyBatchReport:
    execution_date: str
    scheduled_time: str
    clips_received: int
    metadata_generated: int
    successfully_uploaded: int
    failed: int
    execution_status: str  # COMPLETED, PARTIAL, FAILED, INCOMPLETE_INPUT
    clips: List[ClipExecutionReport] = field(default_factory=list)
    failure_details: Optional[str] = None
    required_action: Optional[str] = None


class ReportGenerator:
    def __init__(self, config: YTManagerConfig):
        self.config = config

    def format_text_report(self, report: DailyBatchReport) -> str:
        lines = [
            "=" * 60,
            "YT MANAGER — DAILY REPORT",
            "=" * 60,
            f"Date: {report.execution_date}",
            f"Scheduled Time: {report.scheduled_time}",
            "",
        ]

        for clip in report.clips:
            lines.extend([
                f"VIDEO {clip.index}",
                f"Original File: {clip.original_filename}",
                f"Generated Title: {clip.generated_title}",
                f"Description: {clip.description_status}",
                f"SEO Metadata: {clip.metadata_status}",
                f"Upload Status: {clip.upload_status}",
                f"YouTube Video ID: {clip.youtube_video_id if clip.youtube_video_id else 'N/A'}",
                f"YouTube URL: {clip.youtube_url if clip.youtube_url else 'N/A'}",
            ])
            if clip.error_message:
                lines.append(f"Error: {clip.error_message}")
            lines.append("")

        lines.extend([
            "DAILY SUMMARY",
            f"Clips Received: {report.clips_received}",
            f"Metadata Generated: {report.metadata_generated}",
            f"Successfully Uploaded: {report.successfully_uploaded}",
            f"Failed: {report.failed}",
            f"Execution Status: {report.execution_status}",
        ])

        if report.failure_details:
            lines.extend([
                "",
                f"FAILURE DETAILS: {report.failure_details}",
            ])

        if report.required_action:
            lines.extend([
                f"REQUIRED ACTION: {report.required_action}",
            ])

        lines.append("=" * 60)
        return "\n".join(lines)

    def save_report(self, report: DailyBatchReport, custom_dir: Optional[Path] = None) -> Path:
        """Saves text and markdown report files."""
        out_dir = custom_dir or self.config.reports_dir
        out_dir.mkdir(parents=True, exist_ok=True)

        txt_content = self.format_text_report(report)
        date_slug = report.execution_date.replace(" ", "_").replace(",", "")
        file_path = out_dir / f"daily_report_{date_slug}.txt"

        with open(file_path, "w", encoding="utf-8") as f:
            f.write(txt_content)

        # Also save as markdown
        md_path = out_dir / f"daily_report_{date_slug}.md"
        with open(md_path, "w", encoding="utf-8") as f:
            f.write(f"```text\n{txt_content}\n```\n")

        return file_path
