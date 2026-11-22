<#
.SYNOPSIS
    Connects YT Manager directly to your Microsoft OneDrive folder.
.DESCRIPTION
    1. Locates your local OneDrive path ($env:OneDrive).
    2. Creates 'YT-Inbox' inside OneDrive (C:\Users\<user>\OneDrive\YT-Inbox).
    3. Migrates any candidate clips from local inbox/ into the OneDrive folder.
    4. Configures YT Manager settings.json to read directly from OneDrive.
#>

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectDir = Split-Path -Parent $ScriptDir

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "     YT MANAGER — ONEDRIVE DIRECT INBOX SETUP" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan

# 1. Resolve OneDrive Path
$OneDrivePath = $env:OneDrive
if (-not $OneDrivePath -or -not (Test-Path $OneDrivePath)) {
    $OneDrivePath = "$env:USERPROFILE\OneDrive"
}

if (-not (Test-Path $OneDrivePath)) {
    Write-Error "Could not locate OneDrive folder at $OneDrivePath. Please ensure OneDrive is installed."
    exit 1
}

$TargetInbox = Join-Path $OneDrivePath "YT-Inbox"
Write-Host "OneDrive Directory : $OneDrivePath" -ForegroundColor Green
Write-Host "Direct Inbox Target : $TargetInbox" -ForegroundColor Green

# 2. Create the YT-Inbox folder
if (-not (Test-Path $TargetInbox)) {
    New-Item -ItemType Directory -Path $TargetInbox -Force | Out-Null
    Write-Host "`n[1/3] Created folder: $TargetInbox" -ForegroundColor Green
} else {
    Write-Host "`n[1/3] Folder already exists: $TargetInbox" -ForegroundColor Yellow
}

# 3. Migrate existing clips from local inbox/ to OneDrive YT-Inbox
$LocalInbox = Join-Path $ProjectDir "inbox"
if (Test-Path $LocalInbox) {
    $existing = Get-ChildItem -Path $LocalInbox -Include *.mp4,*.mov,*.mkv -Recurse -File
    if ($existing.Count -gt 0) {
        Write-Host "[2/3] Migrating $($existing.Count) clip(s) from local inbox into OneDrive..." -ForegroundColor Cyan
        foreach ($file in $existing) {
            $dest = Join-Path $TargetInbox $file.Name
            Copy-Item -Path $file.FullName -Destination $dest -Force
            Write-Host "  -> Copied: $($file.Name)" -ForegroundColor Gray
        }
    } else {
        Write-Host "[2/3] Local inbox clean; ready for mobile drops." -ForegroundColor Gray
    }
}

# 4. Update settings.json to point directly to OneDrive
$SettingsFile = Join-Path $ProjectDir "config\settings.json"
if (Test-Path $SettingsFile) {
    try {
        $json = Get-Content $SettingsFile -Raw | ConvertFrom-Json
        $normalizedInbox = $TargetInbox.Replace('\', '/')
        $json.inbox_dir = $normalizedInbox
        $json.allow_deterministic_excess = $true
        $json | ConvertTo-Json -Depth 5 | Set-Content $SettingsFile -Encoding utf8
        Write-Host "[3/3] Updated config/settings.json: inbox_dir -> $normalizedInbox" -ForegroundColor Green
    } catch {
        Write-Warning "Could not automatically write settings.json: $_"
    }
}

# 5. Inventory video files currently in OneDrive YT-Inbox
$videoExtensions = @("*.mp4", "*.mov", "*.mkv", "*.webm", "*.avi", "*.m4v")
$readyClips = @()
foreach ($ext in $videoExtensions) {
    $found = Get-ChildItem -Path $TargetInbox -Filter $ext -File -ErrorAction SilentlyContinue
    if ($found) { $readyClips += $found }
}

Write-Host "`n============================================================" -ForegroundColor Green
Write-Host " SUCCESS: YT Manager is now connected to OneDrive!" -ForegroundColor Green
Write-Host "============================================================" -ForegroundColor Green
Write-Host "Direct Upload Folder: $TargetInbox" -ForegroundColor Yellow

if ($readyClips.Count -gt 0) {
    Write-Host "`nDetected $($readyClips.Count) clip(s) ready in YT-Inbox:" -ForegroundColor Cyan
    $idx = 1
    foreach ($clip in $readyClips) {
        $sizeMb = [math]::Round($clip.Length / 1MB, 2)
        Write-Host "  [$idx] $($clip.Name) (${sizeMb} MB)" -ForegroundColor White
        $idx++
    }
} else {
    Write-Host "`nNo video clips detected in YT-Inbox yet." -ForegroundColor DarkYellow
}
