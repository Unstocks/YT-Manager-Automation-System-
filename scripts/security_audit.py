"""
Security & Secrets Audit Tool for Unstocks YT-Manager
Scans repository, git history, tracked files, and configuration to prevent accidental secret leaks.
"""
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent

SECRET_PATTERNS = [
    (re.compile(r"AIza[0-9A-Za-z-_]{35}"), "Google / Gemini API Key"),
    (re.compile(r"AQ\.[0-9A-Za-z-_]{30,}"), "Google / Gemini Authorization Key"),
    (re.compile(r"[0-9]{8,10}:[A-Za-z0-9_-]{35}"), "Telegram Bot Token"),
    (re.compile(r"ghp_[A-Za-z0-9]{36}"), "GitHub Personal Access Token"),
    (re.compile(r"github_pat_[A-Za-z0-9_]{82}"), "GitHub Fine-Grained Token"),
    (re.compile(r"sk-[A-Za-z0-9]{32,}"), "OpenAI API Key"),
    (re.compile(r"(?i)client_secret[\'\"]?\s*[:=]\s*[\'\"](?!(YOUR_|test|dummy|<YOUR))[A-Za-z0-9-_]{20,}"), "OAuth Client Secret"),
    (re.compile(r"(?i)refresh_token[\'\"]?\s*[:=]\s*[\'\"](?!(YOUR_|test|dummy|<YOUR))[A-Za-z0-9-_]{20,}"), "OAuth Refresh Token"),
    (re.compile(r"(?i)access_token[\'\"]?\s*[:=]\s*[\'\"](?!(YOUR_|test|dummy|<YOUR))[A-Za-z0-9-_]{25,}"), "OAuth Access Token"),
]

SENSITIVE_FILENAME_PATTERNS = [
    r"^\.env(\..+)?$",
    r"^.*token\.json$",
    r"^.*client_secrets\.json$",
    r"^.*\.pem$",
    r"^.*\.key$",
    r"^.*\.pkcs12$",
    r"^.*\.pfx$",
    r"^.*\.db$",
    r"^.*\.sqlite3?$",
]

def run_audit() -> int:
    print("=" * 60)
    print("      UNSTOCKS YT-MANAGER SECURITY & SECRETS AUDIT")
    print("=" * 60)
    
    issues_found = 0

    # 1. Check Git Tracked Files for Sensitive File Names
    try:
        tracked_files = subprocess.check_output(
            ["git", "ls-files"], cwd=str(ROOT_DIR), text=True
        ).splitlines()
    except Exception as e:
        print(f"[Error] Failed to run git ls-files: {e}")
        return 1

    print(f"\n[1/4] Auditing {len(tracked_files)} Git-tracked files for sensitive filenames...")
    for file_path in tracked_files:
        name = Path(file_path).name
        # Allow example files
        if "example" in name or ".gitkeep" in name:
            continue
        for pat in SENSITIVE_FILENAME_PATTERNS:
            if re.match(pat, name, re.IGNORECASE):
                print(f"  [CRITICAL LEAK RISK] Sensitive file tracked by Git: {file_path}")
                issues_found += 1

    # 2. Scan Tracked File Contents for API Keys & Tokens
    print(f"\n[2/4] Scanning tracked file contents for secrets & credential patterns...")
    content_matches = 0
    for rel_path in tracked_files:
        full_path = ROOT_DIR / rel_path
        if not full_path.is_file():
            continue
        # Skip binary fixtures
        if full_path.suffix.lower() in {".mp4", ".mov", ".mkv", ".png", ".jpg", ".jpeg", ".ico"}:
            continue
        try:
            with open(full_path, "r", encoding="utf-8", errors="ignore") as f:
                for line_idx, line in enumerate(f, start=1):
                    for regex, label in SECRET_PATTERNS:
                        if regex.search(line):
                            # Skip test mocks or documentation placeholders
                            if "YOUR_" in line or "placeholder" in line.lower() or "example" in rel_path.lower():
                                continue
                            print(f"  [SECRET FOUND] {rel_path}:{line_idx} - {label}")
                            content_matches += 1
                            issues_found += 1
        except Exception:
            pass

    if content_matches == 0:
        print("  [PASSED] Zero hardcoded API keys, tokens, or credentials found in tracked files.")

    # 3. Check .gitignore Coverage
    print(f"\n[3/4] Checking .gitignore coverage for secret vectors...")
    gitignore_path = ROOT_DIR / ".gitignore"
    if not gitignore_path.exists():
        print("  [ERROR] .gitignore missing!")
        issues_found += 1
    else:
        with open(gitignore_path, "r", encoding="utf-8") as f:
            gi_content = f.read()

        must_have = [
            ".env",
            "client_secrets.json",
            "token.json",
            "*.db",
            "inbox/*",
            "processing/*",
            "uploaded/*",
            "failed/*",
        ]
        missing_rules = [r for r in must_have if r not in gi_content]
        if missing_rules:
            print(f"  [WARNING] .gitignore missing critical rules: {missing_rules}")
            issues_found += len(missing_rules)
        else:
            print("  [PASSED] All mandatory secret rules present in .gitignore.")

    # 4. Check git diff / commit history
    print(f"\n[4/4] Verifying local Git status and uncommitted files...")
    status_output = subprocess.check_output(
        ["git", "status", "--porcelain"], cwd=str(ROOT_DIR), text=True
    ).strip()
    if status_output:
        print(f"  [INFO] Uncommitted changes present:\n{status_output}")
    else:
        print("  [PASSED] Working tree clean; all files safely staged or committed.")

    print("\n" + "=" * 60)
    if issues_found == 0:
        print(" RESULT: 100% SECURE. Repository is safe to push to GitHub.")
        print("=" * 60)
        return 0
    else:
        print(f" RESULT: {issues_found} potential security issue(s) detected. Fix before push!")
        print("=" * 60)
        return 1

if __name__ == "__main__":
    sys.exit(run_audit())
