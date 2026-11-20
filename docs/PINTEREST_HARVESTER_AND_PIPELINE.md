# PINTEREST MOTION-GRAPHIC HARVESTER & AUTOMATED STAGING PIPELINE

**System:** YT Manager (`@unstocks`)  
**Purpose:** Autonomously discover, download, clean, and stage the highest quality 3D motion-graphic explanation clips from a curated Pinterest Board directly into the 6:00 PM IST upload pipeline.

---

## 1. End-to-End Architectural Pipeline

```
[ User Saves Pins to Pinterest Board (e.g. "Unstocks Curated") ]
                              │
                              ▼ (Runs at 5:00 PM IST)
            ┌───────────────────────────────────┐
            │ 1. Pinterest Board RSS Ingestion  │
            │    https://pinterest.com/user/    │
            │    board.rss                      │
            └─────────────────┬─────────────────┘
                              │
                              ▼
            ┌───────────────────────────────────┐
            │ 2. Direct Stream Extraction       │
            │    Resolves highest-res 720p/1080p│
            │    MP4 video streams              │
            └─────────────────┬─────────────────┘
                              │
                              ▼
            ┌───────────────────────────────────┐
            │ 3. Quality & Sweet-Spot Gate      │
            │    - Duration: 10s – 35s          │
            │    - Aspect Ratio: 9:16 Vertical  │
            │    - Drops static & blurry pins   │
            └─────────────────┬─────────────────┘
                              │
                              ▼
            ┌───────────────────────────────────┐
            │ 4. Watermark Masker               │
            │    Localized frosted glass blur   │
            │    over third-party handles/logos │
            └─────────────────┬─────────────────┘
                              │
                              ▼
            ┌───────────────────────────────────┐
            │ 5. Audio Cleaner & BGM Remover    │
            │    Strips copyrighted background  │
            │    music; preserves voice & SFX   │
            └─────────────────┬─────────────────┘
                              │
                              ▼
            ┌───────────────────────────────────┐
            │ 6. Staged in YT-Manager/inbox/    │
            │    Exactly 2 pristine, un-uploaded│
            │    clips ready for 6:00 PM batch  │
            └─────────────────┬─────────────────┘
                              │
                              ▼ (Runs at 6:00 PM IST)
            ┌───────────────────────────────────┐
            │ 7. YT Manager Daily Automation    │
            │    AI Content Understanding       │
            │    SEO Title & Description        │
            │    High-CTR Thumbnail Applied     │
            │    Uploaded to @unstocks          │
            └───────────────────────────────────┘
```

---

## 2. CLI Usage & Operations

### A. Harvest from a Curated Board:
```powershell
python -m yt_manager harvest --board "https://www.pinterest.com/YOUR_USERNAME/YOUR_BOARD_NAME" --count 2
```

### B. Ingest a Single Specific Pin URL:
```powershell
python -m yt_manager harvest --pin "https://www.pinterest.com/pin/766456430382366110/"
```

### C. Options:
- `--count N`: Target number of clips to stage into `inbox/` (default: 2).
- `--no-clean-bgm`: Skip background music removal if the original audio is already licensed.
- `--no-mask`: Skip watermark masking if the video has no logo.
