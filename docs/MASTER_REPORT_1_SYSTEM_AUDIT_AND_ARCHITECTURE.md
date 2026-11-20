# MASTER REPORT 1 — SYSTEM AUDIT & ARCHITECTURE

**Project:** YT Manager  
**Channel:** Unstocks (`https://youtube.com/@unstocks`)  
**Channel ID:** `UCT0tm0KSB2BlIjdY6uUZCeA`  
**Execution Target:** Daily at 6:00 PM IST (`Asia/Kolkata`)  
**Architect:** Antigravity AI Systems Architect  
**Architecture Grade:** Lindy-Durable, Local-First, Zero-Wrapper  

---

## 1. Existing Environment Audit

A comprehensive hardware, software, and dependency audit was performed directly on the host system prior to scaffolding the system:

| Resource / Tool | System Audit Result | Architectural Suitability |
| :--- | :--- | :--- |
| **Operating System** | Windows 11 (64-bit) | Native host platform for the daily scheduler and filesystem inbox. |
| **Python Runtime** | Python 3.14.10 (`C:\Users\sanja\AppData\Local\Programs\Python\Python314\python.exe`) | Modern Python runtime. To prevent binary wheel incompatibility on 3.14, the architecture is engineered with zero third-party dependencies (built entirely on Python standard library: `urllib`, `sqlite3`, `http.server`, `hashlib`, `subprocess`). |
| **Media Processing** | FFmpeg 9.0.2-full (`Gyan.FFmpeg`) & FFprobe | Pre-installed and verified in system PATH. Capable of frame extraction, stream probing, audio demuxing, and aspect-ratio detection. |
| **GPU Acceleration** | NVIDIA GeForce RTX 3050 Laptop GPU (6 GB VRAM, Driver 576.93, CUDA 12.9) | Local hardware available for accelerated local ML inference / transcription. |
| **Scheduler Host** | Windows Task Scheduler (`schtasks` / `Register-ScheduledTask`) | Native Windows daemon capable of surviving system reboots and waking the machine for daily 18:00 IST trigger. |
| **Test Video Clip** | `media_1795143017068_2d97bbe8.mp4` | 17.89s, 720x1280 (9:16 vertical YouTube Shorts format), H.264 video, AAC audio, 1.25 MB. Focus: Cognitive load, 35,000 daily decisions, and structured problem-solving skills. |

---

## 2. Final Architecture Overview

YT Manager follows a **Decoupled Modular Pipeline** designed for Lindy durability: it runs locally, requires no cloud middleman, uses standard protocols, and maintains ACID-compliant persistent state.

```
                              [ 6:00 PM IST Daily Trigger ]
                                           │
                                           ▼
                     ┌───────────────────────────────────────────┐
                     │         Task Scheduler / Daemon           │
                     └─────────────────────┬─────────────────────┘
                                           │
                                           ▼
                     ┌───────────────────────────────────────────┐
                     │        Detector & Batch Gatekeeper        │
                     │  - Scans YT-Manager/inbox/                │
                     │  - Computes SHA-256 Checksums             │
                     │  - Checks upload_history (Deduplication)  │
                     │  - Enforces STRICT 2-Clip Batch Rule      │
                     └─────────────────────┬─────────────────────┘
                                           │ (Exactly 2 Valid Clips)
                                           ▼
                     ┌───────────────────────────────────────────┐
                     │          Media Inspector Engine           │
                     │  - ffprobe: Dimensions, Bitrate, Duration │
                     │  - ffmpeg: 1 fps Frame Extraction         │
                     │  - ffmpeg: 16kHz Mono Audio Demuxing      │
                     └─────────────────────┬─────────────────────┘
                                           │
                                           ▼
                     ┌───────────────────────────────────────────┐
                     │        AI Video Understanding Engine      │
                     │  - Visual Frame & On-Screen Text Reading  │
                     │  - Subject, Entity & Hook Identification  │
                     │  - Factual Verification (Zero Inventions) │
                     └─────────────────────┬─────────────────────┘
                                           │
                                           ▼
                     ┌───────────────────────────────────────────┐
                     │        SEO Metadata Generator             │
                     │  - Search-Optimized Titles (<70 chars)    │
                     │  - 6-Part Structured Descriptions         │
                     │  - Channel-Aligned Tags (<500 chars)      │
                     │  - Saves JSON: metadata/clip_xxx.json     │
                     └─────────────────────┬─────────────────────┘
                                           │
                                           ▼
                     ┌───────────────────────────────────────────┐
                     │      YouTube Resumable Upload Engine      │
                     │  - Official YouTube Data API v3           │
                     │  - Channel ID Guard (UCT0tm0KSB2BlIjdY6uUZ)│
                     │  - 256KB-Multiple Resumable Chunking      │
                     │  - HTTP 308 Auto-Resume on Connection Drop│
                     └─────────────────────┬─────────────────────┘
                                           │
                                           ▼
                     ┌───────────────────────────────────────────┐
                     │        Post-Upload Verifier Engine        │
                     │  - Queries processing & rejection status  │
                     │  - Confirms Public Privacy Status         │
                     └─────────────────────┬─────────────────────┘
                                           │
                                           ▼
                     ┌───────────────────────────────────────────┐
                     │        Archival, Reports & Alerts         │
                     │  - Move to uploaded/ or failed/           │
                     │  - ACID Record in SQLite State DB         │
                     │  - Daily Text & Markdown Reports          │
                     │  - Native Windows Toast Notifications     │
                     └───────────────────────────────────────────┘
```

---

## 3. Component Selection & Responsibilities

| Component | Module | Core Implementation & Rationale |
| :--- | :--- | :--- |
| **Config Loader** | `yt_manager/config.py` | Central typed dataclass loading `config/settings.json` with environment variable overrides. Ensures strict separation of config and code. |
| **State Persistence** | `yt_manager/state.py` | Transactional SQLite engine (`data/yt_manager.db`) with automatic connection closing, connection pooling context manager, and schema migrations. Tracks batches, clip stages, and an irreversible `upload_history` table keyed on SHA-256. |
| **Input Gatekeeper** | `yt_manager/detector.py` | Enforces the strict daily rule: requires **exactly two valid, un-uploaded video files**. Rejects partial batches (<2) with alerts; rejects ambiguous batches (>2) to prevent accidental uploads; computes SHA-256 to stop duplicate uploads. |
| **Media Inspector** | `yt_manager/inspector.py` | Invokes `ffprobe` and `ffmpeg` via standard library `subprocess`. Extracts technical metrics (resolution, duration, aspect ratio, audio presence) and detects YouTube Shorts formatting (aspect ratio ≤ 1.05 and duration ≤ 60s). |
| **Video Understanding** | `yt_manager/understanding.py` | Multi-tier understanding engine extracting subjects, entities, and on-screen text without hallucinating. Supports Gemini Vision REST API via pure `urllib` or deterministic local heuristic inspection. |
| **SEO Metadata** | `yt_manager/metadata.py` | Generates high-click-through YouTube titles, structured 6-tier descriptions (hook, summary, context, brand context, call to action, hashtags), and focused search tags. Saves standalone JSON artifacts in `metadata/clip_xxx.json`. |
| **OAuth 2.0 Engine** | `yt_manager/auth.py` | Standards-compliant Google OAuth 2.0 loopback receiver on `http://localhost:8080`. Handles automated refresh-token renewal and token persistence in `config/token.json`. |
| **Channel Guard** | `yt_manager/auth.py` | Cryptographically queries `channels.list?mine=true` before any upload and verifies `id == "UCT0tm0KSB2BlIjdY6uUZCeA"`. If any other channel is authenticated, immediately throws `ChannelMismatchError` and aborts execution. |
| **Resumable Uploader** | `yt_manager/uploader.py` | Pure Python implementation of Google's Resumable Upload protocol. Streams in multiples of 256 KB, queries byte offset via HTTP 308 on drops, applies exponential backoff, and validates response payloads. |
| **Post-Upload Verifier** | `yt_manager/verifier.py` | Polls YouTube API post-upload to confirm catalog entry, processing status, and public accessibility. Reports exact rejection reasons if rejected. |
| **Notifier** | `yt_manager/notifier.py` | Dispatches Windows Native Toast notifications via PowerShell WinRT, structured console logs, and optional outbound webhooks. |
| **Daily Reporter** | `yt_manager/reporter.py` | Formats and outputs the exact daily execution report mandated in Section 8. Generates both `.txt` and `.md` reports in `logs/reports/`. |
| **Persistent Scheduler** | `yt_manager/scheduler.py` | Installs and manages native Windows Scheduled Task `YT-Manager-Daily` at 18:00 IST. Includes standalone Python daemon mode with retry intervals. |

---

## 4. Scheduling Strategy

- **Trigger Window:** 6:00 PM IST (Asia/Kolkata, UTC+05:30).
- **Execution Mechanism:** Native Windows Task Scheduler (`Register-ScheduledTask`) with:
  - `AllowStartIfOnBatteries: True`
  - `DontStopIfGoingOnBatteries: True`
  - `StartWhenAvailable: True` (catches up if the PC was powered off at 6:00 PM and runs immediately upon power-on).
  - `ExecutionTimeLimit: 2 Hours`
- **Duplicate Run Protection:** The `state.py` database records the daily execution date in `batches`. If triggered twice on the same day, the orchestrator detects the completed batch and exits safely without re-processing.
- **Retry Mechanism:** If fewer than 2 clips are detected at 6:00 PM, the scheduler logs an `INCOMPLETE_INPUT` event, notifies the user via desktop toast, and retries every 15 minutes until the daily cutoff time (23:59 IST).

---

## 5. Security & Risk Analysis

| Risk | Mitigation Architecture |
| :--- | :--- |
| **Uploading to Wrong Channel** | Mandatory pre-upload verification. The system matches the authenticated channel ID against `UCT0tm0KSB2BlIjdY6uUZCeA`. Upload is blocked if IDs do not match. |
| **Credential Leakage** | All credentials (`client_secrets.json`, `token.json`, `.env`) are excluded in `.gitignore`. Example files (`settings.example.json`, `client_secrets.example.json`) contain only placeholder templates. |
| **Duplicate Video Uploads** | Every video file is hashed with SHA-256 before staging. Hashes are permanently recorded in the SQLite `upload_history` table. If the same file is placed in inbox weeks later, it is rejected before staging. |
| **Network Interruption During Upload** | The upload engine adheres to the Google Resumable Upload specification. If internet disconnects at byte 8,000,000 of 10,000,000, the uploader reconnects, queries the HTTP 308 status, and resumes from byte 8,000,001. |
| **Data Loss on Failure** | Original files are never deleted. Successfully uploaded videos are moved to `uploaded/<batch_id>/`. Failed videos are kept in `failed/<batch_id>/` with full failure logs for one-command recovery (`python -m yt_manager retry`). |
