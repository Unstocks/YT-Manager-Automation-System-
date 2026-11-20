# MASTER REPORT 1 — SYSTEM AUDIT & ARCHITECTURE

**Project:** YT Manager  
**Project Owner:** Unstocks  
**Target YouTube Channel:** https://youtube.com/@unstocks  
**Channel ID:** `UCT0tm0KSB2BlIjdY6uUZCeA`  
**Automation Name:** YT Manager  
**Execution Schedule:** Every day at 6:00 PM IST (`Asia/Kolkata`)  
**Daily Input:** Exactly 2 video clips  
**Architect:** Antigravity AI Systems Architect  
**Architecture Classification:** Lindy-Durable, Local-First, Zero External Python Dependencies  

---

## 1. Existing Environment Audit

A comprehensive hardware, software, runtime, and dependency audit was performed directly on the host development environment prior to system design and scaffolding.

### Host Platform & Tooling Audit Matrix

| Resource / Tool | Host Inspection Result | Architectural Evaluation & Strategy |
| :--- | :--- | :--- |
| **Operating System** | Windows 11 Home / Pro (64-bit) | Native host platform for the daily automation scheduler, persistent SQLite database, and filesystem inbox. |
| **Python Runtime** | Python 3.14.10 (`C:\Users\sanja\AppData\Local\Programs\Python\Python314\python.exe`) | Modern Python runtime. Because Python 3.14 is very recent and third-party binary C-extensions frequently suffer build breakage or wheel absence, the entire YT Manager engine is engineered **strictly with zero external Python dependencies** using the Python standard library (`urllib`, `sqlite3`, `http.server`, `hashlib`, `subprocess`, `mimetypes`, `dataclasses`, `argparse`). |
| **Media Processing** | FFmpeg 9.0.2-full (`Gyan.FFmpeg`) & FFprobe | Pre-installed and verified in system PATH (`C:\Users\sanja\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-9.0.2-full_build\bin`). Provides hardware-accelerated media inspection, technical stream probing, keyframe extraction, and audio demuxing. Features built-in `whisper.cpp` filter support. |
| **GPU Acceleration** | NVIDIA GeForce RTX 3050 6GB Laptop GPU (6,144 MiB VRAM, 6,002 MiB Free) | Dedicated GPU available locally on the machine for video frame processing and local ML model execution. |
| **Scheduler Engine** | Windows Task Scheduler (`Register-ScheduledTask` / `schtasks.exe`) | Native OS scheduling engine capable of surviving system restarts and reboots, waking up the machine or executing upon user logon with battery-aware configurations. |
| **Persistent Storage** | Local NTFS File System | Persistent paths established at `C:\Users\sanja\.gemini\antigravity\scratch\YT-Manager`. ACID transactional state is maintained locally in SQLite3 (`data/yt_manager.db`). |
| **Authentication Infrastructure** | Google OAuth 2.0 PKCE / Loopback Receiver | Pure Python local HTTP server (`http.server`) bound to `localhost:8080` to capture authorization grant codes and exchange them for permanent refresh tokens. Cryptographic channel verification against `UCT0tm0KSB2BlIjdY6uUZCeA`. |

---

## 2. Final Architecture Overview

YT Manager adheres strictly to the single responsibility principle: **the user provides two pre-made video clips daily, and YT Manager handles understanding, metadata generation, upload, and verification without altering the video files.**

```
                                [ 6:00 PM IST Daily Trigger ]
                                              │
                                              ▼
                       ┌─────────────────────────────────────────────┐
                       │     Persistent Windows Task Scheduler       │
                       │    (survives restarts, wakes machine)       │
                       └──────────────────────┬──────────────────────┘
                                              │
                                              ▼
                       ┌─────────────────────────────────────────────┐
                       │          Clip Detector & Gatekeeper         │
                       │  - Ingests YT-Manager/inbox/                │
                       │  - Validates readability, format, size      │
                       │  - SHA-256 Deduplication check              │
                       │  - Strict 2-Clip Daily Batch Rule           │
                       └──────────────────────┬──────────────────────┘
                                              │ (Exactly 2 Valid Clips)
                                              ▼
                       ┌─────────────────────────────────────────────┐
                       │            Media Inspector Engine           │
                       │  - ffprobe stream inspection                │
                       │  - 9:16 Shorts detection (<=60s, aspect<=1) │
                       │  - Keyframe extraction for visual analysis  │
                       │  - Audio stream extraction                  │
                       └──────────────────────┬──────────────────────┘
                                              │
                                              ▼
                       ┌─────────────────────────────────────────────┐
                       │        AI Video Understanding Engine        │
                       │  - Ingests sidecars (<name>.json / .txt)    │
                       │  - Multimodal Gemini Vision API (if key)    │
                       │  - Content-grounded deterministic analysis  │
                       │  - Strict Accuracy Rule: Zero Inventions   │
                       └──────────────────────┬──────────────────────┘
                                              │
                                              ▼
                       ┌─────────────────────────────────────────────┐
                       │          SEO Metadata Generator             │
                       │  - Search-friendly title (<80 chars, #Shorts)│
                       │  - 6-part structured description            │
                       │  - Tags under 500 chars, niche keywords     │
                       │  - Saves metadata/clip_xxx.json             │
                       └──────────────────────┬──────────────────────┘
                                              │
                                              ▼
                       ┌─────────────────────────────────────────────┐
                       │       YouTube Resumable Upload Engine       │
                       │  - YouTube Data API v3 (Resumable Protocol) │
                       │  - Strict Channel ID Check (UCT0tm0KSB2BlI) │
                       │  - 256KB-Multiple chunk streaming           │
                       │  - HTTP 308 Auto-resume on disconnection    │
                       └──────────────────────┬──────────────────────┘
                                              │
                                              ▼
                       ┌─────────────────────────────────────────────┐
                       │         Post-Upload Verifier Engine         │
                       │  - Polls YouTube catalog registration       │
                       │  - Confirms uploadStatus & public privacy   │
                       │  - Reports exact rejection reason if failed │
                       └──────────────────────┬──────────────────────┘
                                              │
                                              ▼
                       ┌─────────────────────────────────────────────┐
                       │         Archival, Reports & Alerts          │
                       │  - Moves verified clips to uploaded/        │
                       │  - Writes ACID records to SQLite DB         │
                       │  - Emits Section 8 Daily Execution Report   │
                       │  - Dispatches Windows native toast alert    │
                       └─────────────────────────────────────────────┘
```

---

## 3. Component Selection & Responsibilities

| Component | Implementation File | Key Invariant & Responsibility |
| :--- | :--- | :--- |
| **Config Loader** | `yt_manager/config.py` | Central dataclass loading `config/settings.json` with environment variable overrides. Keeps configuration decoupled from application logic. |
| **State Persistence** | `yt_manager/state.py` | Transactional SQLite engine (`data/yt_manager.db`) using context managers and foreign keys. Maintains tables: `batches`, `clips`, `upload_history`, and `execution_logs`. |
| **Input Gatekeeper** | `yt_manager/detector.py` | Enforces the strict daily rule: requires **exactly two valid, un-uploaded video files**. Rejects partial batches (<2) with alerts; detects ambiguity if excess clips exist; computes SHA-256 to stop duplicate uploads. |
| **Media Inspector** | `yt_manager/inspector.py` | Invokes `ffprobe` and `ffmpeg` via standard library `subprocess`. Extracts technical metrics (resolution, duration, aspect ratio, audio presence) and detects YouTube Shorts formatting (aspect ratio ≤ 1.05 and duration ≤ 60s). |
| **Video Understanding** | `yt_manager/understanding.py` | Multi-tier understanding engine extracting subjects, entities, and themes without hallucinating. Supports sidecar context files, Gemini Vision REST API via pure `urllib`, and deterministic local heuristic inspection. |
| **SEO Metadata** | `yt_manager/metadata.py` | Generates high-click-through YouTube titles, structured 6-tier descriptions (hook, summary, context, brand context, call to action, hashtags), and focused search tags. Saves standalone JSON artifacts in `metadata/clip_xxx.json`. |
| **OAuth 2.0 Engine** | `yt_manager/auth.py` | Standards-compliant Google OAuth 2.0 loopback receiver on `http://localhost:8080`. Handles automated refresh-token renewal and token persistence in `config/token.json`. |
| **Channel Guard** | `yt_manager/auth.py` | Cryptographically queries `channels.list?mine=true` before any upload and verifies `id == "UCT0tm0KSB2BlIjdY6uUZCeA"`. If any other channel is authenticated, immediately throws `ChannelMismatchError` and aborts execution. |
| **Resumable Uploader** | `yt_manager/uploader.py` | Pure Python implementation of Google's Resumable Upload protocol. Streams in multiples of 256 KB, queries byte offset via HTTP 308 on drops, applies exponential backoff, and validates response payloads. |
| **Post-Upload Verifier** | `yt_manager/verifier.py` | Polls YouTube API post-upload to confirm catalog entry, processing status, and public accessibility. Reports exact rejection reasons if rejected. |
| **Notifier** | `yt_manager/notifier.py` | Dispatches Windows Native Toast notifications via PowerShell WinRT, structured console logs, and optional outbound webhooks. |
| **Daily Reporter** | `yt_manager/reporter.py` | Formats and outputs the exact daily execution report mandated in Section 8. Generates both `.txt` and `.md` reports in `logs/reports/`. |
| **Persistent Scheduler** | `yt_manager/scheduler.py` | Installs and manages native Windows Scheduled Task `YT-Manager-Daily` at 18:00 IST. Includes standalone Python daemon mode with retry intervals. |

---

## 4. Scheduling & Timezone Strategy

- **Trigger Window:** 6:00 PM IST (`Asia/Kolkata`, UTC+05:30).
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
| **Network Interruption During Upload** | The upload engine adheres to the Google Resumable Upload specification. If internet disconnects during an upload, the uploader reconnects, queries the HTTP 308 status, and resumes from the exact byte offset. |
| **Data Loss on Failure** | Original files are never deleted. Successfully uploaded videos are moved to `uploaded/<batch_id>/`. Failed videos are kept in `failed/<batch_id>/` with full failure logs for one-command recovery (`python -m yt_manager retry`). |
