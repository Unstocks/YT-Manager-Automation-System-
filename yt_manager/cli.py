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
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .auth import YouTubeAuthManager
from .config import YTManagerConfig
from .orchestrator import WorkflowOrchestrator
from .reporter import ReportGenerator
from .scheduler import TaskSchedulerManager


def cmd_run(args: argparse.Namespace, config: YTManagerConfig) -> int:
    mock_mode = getattr(args, "mock", False)
    force = getattr(args, "force", False)
    orchestrator = WorkflowOrchestrator(config, mock_mode=mock_mode)
    print("\n[YT Manager] Starting daily batch execution...")
    report = orchestrator.run_daily_batch(force=force)
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
    tz = timezone(timedelta(hours=config.utc_offset_hours))
    today_str = datetime.now(tz).strftime("%Y-%m-%d")
    active_batch = orchestrator.state.get_batch_for_date(today_str)
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
    pin_status = config.pinterest_board_url if config.pinterest_board_url else "Not Configured (Optional Mobile Source)"
    print(f"Pinterest Board     : {pin_status}")
    comment_status = "ENABLED (Dynamic SEO & CTA Question)" if config.enable_creator_comment else "DISABLED"
    print(f"Creator First-Comment: {comment_status}")
    print(f"Inbox Directory     : {config.inbox_dir}")
    print(f"Clips in Inbox      : {len(inbox_files)} / {config.daily_clip_count} required")
    for f in inbox_files:
        print(f"  - {f.name} ({f.stat().st_size} bytes)")
    print("=" * 60 + "\n")
    return 0


def cmd_schedule(args: argparse.Namespace, config: YTManagerConfig) -> int:
    mgr = TaskSchedulerManager(config)
    if getattr(args, "record_test_fire", False):
        mgr.record_test_trigger_event()
        return 0
    elif getattr(args, "test", False):
        wait_min = getattr(args, "minutes", 2)
        success = mgr.test_trigger_execution(wait_minutes=wait_min)
        return 0 if success else 1
    elif args.install:
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

    # Query database for incomplete/failed daily batch clips
    with orchestrator.state._get_connection() as conn:
        cursor = conn.execute(
            """
            SELECT * FROM clips 
            WHERE status NOT IN ('VERIFIED', 'UPLOADED', 'ARCHIVED') 
              AND batch_id LIKE 'batch_%'
            ORDER BY created_at DESC LIMIT 2
            """
        )
        failed_clips = [dict(r) for r in cursor.fetchall()]

    if not failed_clips:
        print("[Retry] No failed daily clips requiring retry. Today's batch is fully verified on YouTube.")
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

            # Finalize parent batch status if all clips are now verified
            all_batch_clips = orchestrator.state.get_clips_for_batch(batch_id)
            if all_batch_clips and all(bc["status"] in ("VERIFIED", "UPLOADED") for bc in all_batch_clips):
                orchestrator.state.update_batch_status(batch_id, status="COMPLETED")

    print(f"\n[Retry] Completed: {recovered}/{len(failed_clips)} clip(s) recovered and verified on YouTube.")
    return 0 if recovered == len(failed_clips) else 1


def cmd_harvest(args: argparse.Namespace, config: YTManagerConfig) -> int:
    from .pinterest_harvester import PinterestHarvester
    from .state import StateManager

    state = StateManager(config.db_path)
    harvester = PinterestHarvester(config, state)

    # 1. Local Files / Inbox Evaluation Mode
    if getattr(args, "local", False) or getattr(args, "files", None):
        if getattr(args, "files", None):
            local_files = [Path(f) for f in args.files]
        else:
            local_files = (
                list(config.inbox_dir.glob("*.mp4"))
                + list(config.inbox_dir.glob("*.mov"))
                + list(config.inbox_dir.glob("*.mkv"))
            )
        
        if not local_files:
            print(f"[Harvester] No video clips found. Drop candidate clips into {config.inbox_dir} or pass --files <path1> <path2>.")
            return 1

        print(f"\n[Harvester] Evaluating {len(local_files)} Candidate Clip(s)...")
        evals = []
        for f in local_files:
            if not f.exists():
                print(f"[Harvester] Warning: File not found: {f}")
                continue
            metrics = harvester.evaluate_candidate_clip(f)
            evals.append({
                "pin_id": f.stem,
                "raw_path": f,
                **metrics,
            })
        
        if not evals:
            print("[Harvester] Could not evaluate any of the provided files.")
            return 1

        evals.sort(key=lambda x: x["composite_score"], reverse=True)

        print("\n" + "=" * 75)
        print(" " * 22 + "CANDIDATE EVALUATION MATRIX")
        print("=" * 75)
        for idx, ev in enumerate(evals, 1):
            dur_label = "Optimal (<2 min)" if 15 <= ev['duration'] <= 90 else "Valid (<2 min)" if ev['duration'] <= 120.0 else "Exceeds 2 min (>120s)"
            aspect_label = "9:16 Shorts" if ev['is_916'] else "Non-Short/Landscape"
            audio_label = f"Present ({ev['audio_codec']})" if ev['has_audio'] else "None"
            print(f"\nCandidate #{idx}: {ev['pin_id']}")
            print(f"  File:            {ev['raw_path'].name}")
            print(f"  Duration:        {ev['duration']:.1f}s ({dur_label})")
            print(f"  Resolution:      {ev['width']}x{ev['height']} ({aspect_label})")
            print(f"  Audio Track:     {audio_label}")
            print(f"  Frame Sharpness: {ev['avg_sharpness']}")
            print(f"  Best Hook Score: {ev['best_frame_score']}")
            print(f"  COMPOSITE SCORE: {ev['composite_score']}/100.0")

        winner = evals[0]
        print("\n" + "-" * 75)
        print(f"RECOMMENDED WINNER: Candidate #1 ({winner['raw_path'].name})")
        print(f"Reason: Highest composite visual quality ({winner['composite_score']}/100.0) with {winner['duration']:.1f}s retention profile.")
        print("-" * 75)

        if args.select_best or args.test_upload:
            print(f"\n[Harvester] Processing Winner: {winner['raw_path'].name} (BGM cleaner + Watermark mask)...")
            work_dir = config.processing_dir / "winner_processing"
            work_dir.mkdir(parents=True, exist_ok=True)
            current_vid = winner["raw_path"]

            # Step 1: Watermark
            if not args.no_mask:
                masked_vid = work_dir / f"masked_{winner['raw_path'].stem}.mp4"
                try:
                    harvester.watermark_masker.apply_blurred_mask(current_vid, masked_vid, "bottom_right")
                    current_vid = masked_vid
                    print(f"[Harvester] Applied localized frosted-glass watermark blur.")
                except Exception as e:
                    print(f"[Harvester] Watermark mask warning: {e}")

            # Step 2: BGM Removal
            if not args.no_clean_bgm:
                audio_work = work_dir / "audio_clean"
                clean_res = harvester.audio_cleaner.separate_and_clean(current_vid, audio_work)
                if clean_res.success:
                    current_vid = clean_res.cleaned_video_path
                    print(f"[Harvester] Attenuated BGM while preserving vocals & SFX.")

            print(f"[Harvester] Successfully prepared clean video: {current_vid.name}")

            if args.test_upload:
                print("\n[Harvester] Launching immediate test-upload to YouTube Channel @unstocks...")
                orch = WorkflowOrchestrator(config, mock_mode=args.mock)
                test_res = orch.run_single_clip_test(current_vid)
                return 0 if test_res.upload_status == "SUCCESS" else 1

        return 0

    if args.evaluate:
        evals = []
        if args.board:
            print(f"\n[Harvester] Evaluating Candidate Pins on Board: {args.board}")
            evals = harvester.evaluate_board(args.board)
        elif getattr(args, "pins", None):
            print(f"\n[Harvester] Evaluating {len(args.pins)} Candidate Pin(s)...")
            evals = harvester.evaluate_pins(args.pins)
        elif args.pin:
            print(f"\n[Harvester] Evaluating Single Pin: {args.pin}...")
            evals = harvester.evaluate_pins([args.pin])

        if not evals:
            print("[Harvester] Could not extract video streams from candidate pin(s) or board.")
            print("[Harvester] TIP: If using a private board, pass direct Pin URLs with --pins <url1> <url2>.")
            return 1

        print("\n" + "=" * 75)
        print(" " * 22 + "BOARD CANDIDATE EVALUATION MATRIX")
        print("=" * 75)
        for idx, ev in enumerate(evals, 1):
            dur_label = "Optimal (<2 min)" if 15 <= ev['duration'] <= 90 else "Valid (<2 min)" if ev['duration'] <= 120.0 else "Exceeds 2 min (>120s)"
            aspect_label = "9:16 Shorts" if ev['is_916'] else "Non-Short/Landscape"
            audio_label = f"Present ({ev['audio_codec']})" if ev['has_audio'] else "None"
            print(f"\nCandidate #{idx}: Pin ID {ev['pin_id']}")
            print(f"  URL:             {ev['pin_url']}")
            print(f"  Duration:        {ev['duration']:.1f}s ({dur_label})")
            print(f"  Resolution:      {ev['width']}x{ev['height']} ({aspect_label})")
            print(f"  Audio Track:     {audio_label}")
            print(f"  Frame Sharpness: {ev['avg_sharpness']}")
            print(f"  Best Hook Score: {ev['best_frame_score']}")
            print(f"  COMPOSITE SCORE: {ev['composite_score']}/100.0")

        winner = evals[0]
        print("\n" + "-" * 75)
        print(f"RECOMMENDED WINNER: Candidate #1 (Pin ID: {winner['pin_id']})")
        print(f"Reason: Highest composite visual quality ({winner['composite_score']}/100.0) with {winner['duration']:.1f}s retention profile.")
        print("-" * 75)

        if args.select_best:
            pin_id = winner['pin_id']
            print(f"\n[Harvester] Processing & Staging Winner: {pin_id}...")
            work_dir = config.processing_dir / "winner_processing"
            work_dir.mkdir(parents=True, exist_ok=True)
            current_video = winner["raw_path"]

            # Step 1: Watermark Masking
            if not args.no_mask:
                masked_video = work_dir / f"masked_{pin_id[:16]}.mp4"
                try:
                    harvester.watermark_masker.apply_blurred_mask(
                        video_path=current_video,
                        output_path=masked_video,
                        position="bottom_right",
                    )
                    current_video = masked_video
                    print(f"[Harvester] Applied localized frosted-glass watermark blur.")
                except Exception as e:
                    print(f"[Harvester] Watermark mask warning: {e}")

            # Step 2: BGM Removal
            if not args.no_clean_bgm:
                audio_work = work_dir / f"audio_clean_{pin_id[:16]}"
                audio_res = harvester.audio_cleaner.separate_and_clean(
                    video_path=current_video,
                    work_dir=audio_work,
                )
                if audio_res.success:
                    current_video = audio_res.cleaned_video_path
                    print(f"[Harvester] Attenuated BGM while preserving voice and sound effects.")

            # Step 3: Move to inbox/
            final_filename = f"unstocks_short_{pin_id[:16]}.mp4"
            final_inbox_path = config.inbox_dir / final_filename
            shutil.copy2(str(current_video), str(final_inbox_path))
            print(f"[Harvester] SUCCESS: Staged clean video to: {final_inbox_path.name}")

            # Step 4: Test Upload
            if args.test_upload:
                print(f"\n[Harvester] Launching immediate test-upload to YouTube Channel @unstocks...")
                orch = WorkflowOrchestrator(config, mock_mode=args.mock)
                test_res = orch.run_single_clip_test(final_inbox_path)
                return 0 if test_res.upload_status == "SUCCESS" else 1

            return 0
        return 0

    if args.pin:
        print(f"\n[Harvester] Ingesting single pin: {args.pin}")
        work_dir = config.processing_dir / "single_harvest_test"
        res = harvester.process_and_stage_pin(
            pin_url=args.pin,
            work_dir=work_dir,
            clean_bgm=not args.no_clean_bgm,
            mask_watermark=not args.no_mask,
        )
        if res.status == "READY":
            print(f"[Harvester] SUCCESS: Staged clean video to: {res.final_inbox_path.name}")
            if args.test_upload:
                print("\n[Harvester] Triggering immediate test-upload for staged pin...")
                orch = WorkflowOrchestrator(config, mock_mode=args.mock)
                test_res = orch.run_single_clip_test(res.final_inbox_path)
                return 0 if test_res.upload_status == "SUCCESS" else 1
            return 0
        else:
            print(f"[Harvester] FAILED: {res.error_message}")
            return 1

    target_board = args.board or config.pinterest_board_url
    if target_board:
        print(f"\n[Harvester] Harvesting from curated board: {target_board}")
        harvested = harvester.run_pre_upload_harvest(
            board_url=target_board,
            target_count=args.count,
            clean_bgm=not args.no_clean_bgm,
            mask_watermark=not args.no_mask,
        )
        print(f"\n[Harvester] Completed: Deposited {len(harvested)} clips into {config.inbox_dir}")
        return 0 if len(harvested) > 0 else 1

    else:
        print("[Harvester] Please provide either --pin <url> or --board <url> (or configure 'pinterest_board_url' in config/settings.json).")
        return 1


def cmd_test_ai(args: argparse.Namespace, config: YTManagerConfig) -> int:
    """Tests AI content understanding on a video clip and displays extracted text, topic, and metadata."""
    from .inspector import MediaInspector
    from .understanding import VideoUnderstandingEngine
    from .metadata import SEOMetadataGenerator

    target_clip = None
    if getattr(args, "clip", None):
        target_clip = Path(args.clip)
    else:
        inbox_clips = list(config.inbox_dir.glob("*.mp4"))
        if inbox_clips:
            target_clip = inbox_clips[0]
        else:
            uploaded_clips = list(config.uploaded_dir.rglob("*.mp4"))
            if uploaded_clips:
                target_clip = uploaded_clips[0]

    if not target_clip or not target_clip.exists():
        print("\n[AI Test] Error: No video clip found to test. Provide --clip <path_to_video.mp4>.\n")
        return 1

    print("\n" + "=" * 65)
    print("             YT MANAGER — AI VIDEO UNDERSTANDING TEST")
    print("=" * 65)
    print(f"Target Video Clip  : {target_clip.name}")
    print(f"File Path          : {target_clip}")
    key_preview = f"{config.gemini_api_key[:10]}...{config.gemini_api_key[-4:]}" if config.gemini_api_key else "NOT CONFIGURED"
    print(f"Gemini API Key     : {key_preview}")
    print("-" * 65)

    inspector = MediaInspector()
    temp_work = config.base_dir / "processing" / "test_ai_work"
    temp_work.mkdir(parents=True, exist_ok=True)

    print("[1/3] Extracting keyframes and media inspection via FFmpeg...")
    inspection = inspector.inspect(target_clip, work_dir=temp_work)
    print(f"      Duration: {inspection.duration_seconds:.1f}s | Resolution: {inspection.width}x{inspection.height}")
    print(f"      Keyframes Extracted: {len(inspection.extracted_frames)}")

    print("[2/3] Calling Multimodal AI Vision Engine (Gemini)...")
    engine = VideoUnderstandingEngine(config.gemini_api_key)
    understanding = engine.analyze(inspection)

    print("\n" + "-" * 65)
    print("                AI RECOGNITION OUTPUT")
    print("-" * 65)
    status_label = "✅ LIVE AI VISION (SUCCESS)" if not understanding.is_fallback else "⚠️ LOCAL FALLBACK (CIRCUIT BREAKER WOULD BLOCK UPLOAD)"
    print(f"Status             : {status_label}")
    print(f"Confidence Score   : {understanding.confidence:.2f}")
    print(f"Subject            : {understanding.subject}")
    print(f"Central Topic      : {understanding.central_topic}")
    print(f"Featured Brand     : {understanding.featured_brand or 'General Business'}")
    print(f"Strategic Moat     : {understanding.strategic_moat}")
    print(f"Main Takeaway      : {understanding.main_takeaway}")
    print("On-Screen Text     :")
    if understanding.on_screen_text:
        for t in understanding.on_screen_text:
            print(f"  • \"{t}\"")
    else:
        print("  • (None detected or offline fallback)")

    print("\n[3/3] Generating SEO Metadata Preview...")
    meta_gen = SEOMetadataGenerator(config)
    metadata = meta_gen.generate(
        batch_id="test_ai_batch",
        clip_id="test_ai_clip",
        original_filename=target_clip.name,
        understanding=understanding,
    )

    print("-" * 65)
    print("            PROPOSED YOUTUBE METADATA PREVIEW")
    print("-" * 65)
    print(f"Title ({len(metadata.title)} chars) : {metadata.title}")
    print(f"Hashtags            : {' '.join('#' + h for h in metadata.hashtags[:6])}")
    print("Description Snippet :")
    for line in metadata.description.splitlines()[:6]:
        print(f"  {line}")
    print("=" * 65 + "\n")

    import shutil
    shutil.rmtree(temp_work, ignore_errors=True)
    return 0


def cmd_setup_ytdlp(args: argparse.Namespace, config: YTManagerConfig) -> int:
    """Downloads the official standalone yt-dlp.exe binary into scripts/yt-dlp.exe."""
    import urllib.request

    scripts_dir = config.base_dir / "scripts"
    scripts_dir.mkdir(parents=True, exist_ok=True)
    target_exe = scripts_dir / "yt-dlp.exe"

    url = "https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp.exe"
    print(f"\n[Setup] Downloading portable yt-dlp.exe from {url}...")
    print(f"[Setup] Target destination: {target_exe}")

    try:
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=120) as resp:
            total_bytes = int(resp.headers.get("Content-Length", 0))
            downloaded = 0
            with open(target_exe, "wb") as f:
                while chunk := resp.read(65536):
                    f.write(chunk)
                    downloaded += len(chunk)
                    if total_bytes > 0:
                        pct = (downloaded / total_bytes) * 100
                        print(f"\r[Setup] Progress: {pct:.1f}% ({downloaded / 1024 / 1024:.1f} MB / {total_bytes / 1024 / 1024:.1f} MB)", end="", flush=True)
        print(f"\n[Setup] SUCCESS: yt-dlp.exe installed at {target_exe}\n")
        return 0
    except Exception as e:
        print(f"\n[Setup] ERROR: Could not download yt-dlp.exe: {e}\n")
        return 1


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
    run_parser.add_argument("--force", action="store_true", help="Force batch execution regardless of daily schedule window")

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
    sched_parser.add_argument("--test", action="store_true", help="Run 2-minute real-clock verification test of Windows Task Scheduler")
    sched_parser.add_argument("--minutes", type=int, default=2, help="Minutes ahead for test trigger (default: 2)")
    sched_parser.add_argument("--record-test-fire", action="store_true", help="Internal callback to record test trigger fire")

    # daemon
    daemon_parser = subparsers.add_parser("daemon", help="Run background scheduler daemon")
    daemon_parser.add_argument("--mock", action="store_true", help="Run daemon with mock uploads")

    # harvest
    harvest_parser = subparsers.add_parser("harvest", help="Harvest, clean & stage Pinterest motion-graphic clips")
    harvest_parser.add_argument("--board", type=str, default="", help="Pinterest Board URL to harvest")
    harvest_parser.add_argument("--pin", type=str, default="", help="Single Pinterest Pin URL to harvest")
    harvest_parser.add_argument("--pins", nargs="+", default=[], help="Multiple Pinterest Pin URLs to evaluate or stage")
    harvest_parser.add_argument("--count", type=int, default=2, help="Target number of clips to stage (default 2)")
    harvest_parser.add_argument("--local", action="store_true", help="Evaluate/stage candidate video clips from local inbox/ directory")
    harvest_parser.add_argument("--files", nargs="+", default=[], help="Evaluate/stage specific local video file paths")
    harvest_parser.add_argument("--evaluate", action="store_true", help="Evaluate and rank all candidate clips")
    harvest_parser.add_argument("--select-best", action="store_true", help="Select and stage only the top-ranked candidate")
    harvest_parser.add_argument("--test-upload", action="store_true", help="Immediately test-upload staged video to YouTube")
    harvest_parser.add_argument("--mock", action="store_true", help="Run upload in mock mode without live YouTube calls")
    harvest_parser.add_argument("--no-clean-bgm", action="store_true", help="Skip BGM removal")
    harvest_parser.add_argument("--no-mask", action="store_true", help="Skip watermark masking")

    # setup-ytdlp
    subparsers.add_parser("setup-ytdlp", help="Download official standalone yt-dlp.exe into scripts/")

    # test-ai
    test_ai_parser = subparsers.add_parser("test-ai", help="Test AI Vision content understanding & on-screen text extraction on a video")
    test_ai_parser.add_argument("--clip", type=str, default="", help="Path to video file to inspect with AI")

    args = parser.parse_args()

    dispatch = {
        "run": cmd_run,
        "retry": cmd_retry,
        "auth": cmd_auth,
        "test-upload": cmd_test_upload,
        "status": cmd_status,
        "schedule": cmd_schedule,
        "daemon": cmd_daemon,
        "harvest": cmd_harvest,
        "setup-ytdlp": cmd_setup_ytdlp,
        "test-ai": cmd_test_ai,
    }

    handler = dispatch.get(args.command)
    if handler:
        sys.exit(handler(args, config))
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
