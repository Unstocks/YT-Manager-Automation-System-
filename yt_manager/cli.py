"""
YT Manager Command Line Interface (CLI)
Provides unified control commands:
- run         : Execute the daily batch upload workflow
- auth        : Interactive Google OAuth 2.0 channel verification
- test-upload : Upload a single clip for end-to-end test verification
- status      : View system status, inbox clips, channel auth & task status
- schedule    : Install/uninstall/check Windows Scheduled Task
- daemon      : Run persistent background daemon
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .auth import YouTubeAuthManager
from .config import YTManagerConfig
from .orchestrator import WorkflowOrchestrator
from .reporter import ReportGenerator
from .scheduler import TaskSchedulerManager


def cmd_run(args: argparse.Namespace, config: YTManagerConfig) -> int:
    mock_mode = getattr(args, "mock", False)
    orchestrator = WorkflowOrchestrator(config, mock_mode=mock_mode)
    print("\n[YT Manager] Starting daily batch execution...")
    report = orchestrator.run_daily_batch()
    text_report = orchestrator.reporter.format_text_report(report)
    print("\n" + text_report)
    return 0 if report.execution_status == "COMPLETED" else 1


def cmd_auth(args: argparse.Namespace, config: YTManagerConfig) -> int:
    auth_manager = YouTubeAuthManager(config)
    try:
        code = getattr(args, "code", None)
        if code:
            print("[Auth] Exchanging provided authorization code for tokens...")
            auth_manager.exchange_code_for_token(code, redirect_uri="http://localhost:8080")
            identity = auth_manager.verify_target_channel()
        else:
            identity = auth_manager.interactive_authenticate(port=args.port)

        print(f"\n[Auth] Channel Authenticated & Verified: {identity.channel_title}")
        print(f"       Channel ID: {identity.channel_id}")
        print(f"       Target Match: CONFIRMED ({config.channel_url})\n")
        return 0
    except Exception as e:
        print(f"\n[Auth] ERROR: {e}\n", file=sys.stderr)
        return 1


def cmd_test_upload(args: argparse.Namespace, config: YTManagerConfig) -> int:
    clip_path = Path(args.clip).resolve()
    if not clip_path.exists():
        print(f"[Error] Video clip not found: {clip_path}", file=sys.stderr)
        return 1

    mock_mode = getattr(args, "mock", False)
    orchestrator = WorkflowOrchestrator(config, mock_mode=mock_mode)
    print(f"\n[YT Manager] Starting single-clip test upload for: {clip_path.name}")
    print(f"Mode: {'MOCK SIMULATION' if mock_mode else 'LIVE PRODUCTION UPLOAD'}")

    res = orchestrator.run_single_clip_test(clip_path)

    print("\n" + "=" * 50)
    print("TEST UPLOAD SUMMARY")
    print("=" * 50)
    print(f"File            : {res.original_filename}")
    print(f"Generated Title : {res.generated_title}")
    print(f"Status          : {res.upload_status}")
    print(f"Video ID        : {res.youtube_video_id}")
    print(f"YouTube URL     : {res.youtube_url}")
    if res.error_message:
        print(f"Error           : {res.error_message}")
    print("=" * 50 + "\n")
    return 0 if res.upload_status == "SUCCESS" else 1


def cmd_status(args: argparse.Namespace, config: YTManagerConfig) -> int:
    orchestrator = WorkflowOrchestrator(config)
    scheduler_mgr = TaskSchedulerManager(config)

    inbox_files = orchestrator.detector.scan_inbox()
    active_batch = orchestrator.state.get_batch_for_date("2026-11-20")
    task_status = scheduler_mgr.check_task_status()

    # Check OAuth Token
    token_status = "NOT CONNECTED"
    channel_info = "None"
    try:
        identity = orchestrator.auth.verify_target_channel()
        token_status = "CONNECTED & VERIFIED"
        channel_info = f"{identity.channel_title} ({identity.channel_id})"
    except Exception as e:
        token_status = f"ERROR / EXPIRED ({e})"

    print("\n" + "=" * 60)
    print("             YT MANAGER — SYSTEM STATUS")
    print("=" * 60)
    print(f"Target Channel      : {config.channel_name} ({config.channel_id})")
    print(f"Channel URL         : {config.channel_url}")
    print(f"OAuth 2.0 Auth      : {token_status}")
    print(f"Channel Match       : {channel_info}")
    print(f"Schedule Time       : {config.schedule_time} {config.timezone} Daily")
    print(f"Windows Task Status : {task_status}")
    print(f"Inbox Directory     : {config.inbox_dir}")
    print(f"Clips in Inbox      : {len(inbox_files)} / {config.daily_clip_count} required")
    for f in inbox_files:
        print(f"  - {f.name} ({f.stat().st_size} bytes)")
    print("=" * 60 + "\n")
    return 0


def cmd_schedule(args: argparse.Namespace, config: YTManagerConfig) -> int:
    mgr = TaskSchedulerManager(config)
    if args.install:
        success = mgr.install_windows_task()
        return 0 if success else 1
    elif args.uninstall:
        success = mgr.uninstall_windows_task()
        return 0 if success else 1
    else:
        status = mgr.check_task_status()
        print(f"Windows Task 'YT-Manager-Daily' Status: {status}")
        return 0


def cmd_daemon(args: argparse.Namespace, config: YTManagerConfig) -> int:
    mgr = TaskSchedulerManager(config)
    mock_mode = getattr(args, "mock", False)
    mgr.run_daemon(mock_mode=mock_mode)
    return 0


def cmd_retry(args: argparse.Namespace, config: YTManagerConfig) -> int:
    mock_mode = getattr(args, "mock", False)
    orchestrator = WorkflowOrchestrator(config, mock_mode=mock_mode)
    print("\n[YT Manager] Retrying incomplete/failed daily uploads...")

    # Query database for incomplete/failed clips
    with orchestrator.state._get_connection() as conn:
        cursor = conn.execute(
            "SELECT * FROM clips WHERE status NOT IN ('VERIFIED', 'UPLOADED') ORDER BY created_at DESC LIMIT 2"
        )
        failed_clips = [dict(r) for r in cursor.fetchall()]

    if not failed_clips:
        print("[Retry] No failed clips requiring retry. System state is clean.")
        return 0

    print(f"[Retry] Found {len(failed_clips)} clip(s) to retry:")
    for c in failed_clips:
        print(f"  - Clip ID: {c['id']} | Filename: {c['original_filename']} | Status: {c['status']}")

    recovered = 0
    for c in failed_clips:
        batch_id = c["batch_id"]
        # Search for file in processing or failed directory
        cand_processing = config.processing_dir / batch_id / c["original_filename"]
        cand_failed = config.failed_dir / batch_id / c["original_filename"]
        cand_inbox = config.inbox_dir / c["original_filename"]

        target_file = None
        if cand_processing.exists():
            target_file = cand_processing
        elif cand_failed.exists():
            # Move back to processing
            cand_processing.parent.mkdir(parents=True, exist_ok=True)
            import shutil
            shutil.move(str(cand_failed), str(cand_processing))
            target_file = cand_processing
        elif cand_inbox.exists():
            target_file = cand_inbox

        if not target_file or not target_file.exists():
            print(f"[Retry] Error: Source video file not found for clip {c['id']}.")
            continue

        res = orchestrator._process_single_clip(
            batch_id=batch_id,
            clip_id=c["id"],
            index=1,
            video_path=target_file,
        )
        if res.upload_status == "SUCCESS":
            recovered += 1

    print(f"\n[Retry] Completed: {recovered}/{len(failed_clips)} clip(s) recovered and verified on YouTube.")
    return 0 if recovered == len(failed_clips) else 1


def main() -> None:
    config = YTManagerConfig.load()
    config.save_default_settings()

    parser = argparse.ArgumentParser(
        prog="yt_manager",
        description="YT Manager - Autonomous YouTube Metadata & Daily Upload Automation",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # run
    run_parser = subparsers.add_parser("run", help="Run the daily 6:00 PM IST upload batch")
    run_parser.add_argument("--mock", action="store_true", help="Run in mock mode without live YouTube calls")

    # retry
    retry_parser = subparsers.add_parser("retry", help="Retry failed or incomplete uploads from recent batches")
    retry_parser.add_argument("--mock", action="store_true", help="Run retry in mock mode without live YouTube calls")

    # auth
    auth_parser = subparsers.add_parser("auth", help="Authenticate with Google OAuth 2.0 and verify channel")
    auth_parser.add_argument("--port", type=int, default=8080, help="Local port for OAuth callback (default 8080)")
    auth_parser.add_argument("--code", type=str, default="", help="Pass authorization code directly")

    # test-upload
    test_parser = subparsers.add_parser("test-upload", help="Upload a single video clip to test the pipeline")
    test_parser.add_argument("clip", type=str, help="Path to video file")
    test_parser.add_argument("--mock", action="store_true", help="Run mock upload without API calls")

    # status
    subparsers.add_parser("status", help="Inspect current inbox, auth, and system state")

    # schedule
    sched_parser = subparsers.add_parser("schedule", help="Manage Windows Scheduled Task")
    sched_parser.add_argument("--install", action="store_true", help="Install Windows Scheduled Task")
    sched_parser.add_argument("--uninstall", action="store_true", help="Uninstall Windows Scheduled Task")

    # daemon
    daemon_parser = subparsers.add_parser("daemon", help="Run background scheduler daemon")
    daemon_parser.add_argument("--mock", action="store_true", help="Run daemon with mock uploads")

    args = parser.parse_args()

    dispatch = {
        "run": cmd_run,
        "retry": cmd_retry,
        "auth": cmd_auth,
        "test-upload": cmd_test_upload,
        "status": cmd_status,
        "schedule": cmd_schedule,
        "daemon": cmd_daemon,
    }

    handler = dispatch.get(args.command)
    if handler:
        sys.exit(handler(args, config))
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
