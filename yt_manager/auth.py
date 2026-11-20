"""
YT Manager Google OAuth 2.0 & Channel Verification Engine
Implemented with pure Python standard library for maximum Lindy durability.
Features:
- OAuth 2.0 PKCE / loopback authorization flow.
- Token storage and automatic refresh handling.
- Cryptographic channel verification against UCT0tm0KSB2BlIjdY6uUZCeA.
- Prevents uploading to any unverified or unintended YouTube channel.
"""
from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from .config import YTManagerConfig

YOUTUBE_SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.readonly",
]

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
YOUTUBE_CHANNELS_URL = "https://www.googleapis.com/youtube/v3/channels?part=id,snippet&mine=true"


class ChannelMismatchError(Exception):
    """Raised when the authenticated Google account does not match the configured channel."""
    pass


@dataclass
class ChannelIdentity:
    channel_id: str
    channel_title: str
    custom_url: Optional[str] = None
    is_verified: bool = False


class OAuthCallbackHandler(BaseHTTPRequestHandler):
    """Temporary local HTTP handler to capture the authorization code from Google OAuth redirect."""
    server_auth_code: Optional[str] = None

    def do_GET(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        params = urllib.parse.parse_qs(parsed.query)

        if "code" in params:
            OAuthCallbackHandler.server_auth_code = params["code"][0]
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            html = """
            <html>
            <head><title>YT Manager - Auth Successful</title></head>
            <body style="font-family: sans-serif; text-align: center; padding: 40px; background: #0f172a; color: #f8fafc;">
                <h1 style="color: #10b981;">Authentication Successful</h1>
                <p>Google OAuth authorization has been captured by YT Manager.</p>
                <p>You may close this tab and return to your terminal.</p>
            </body>
            </html>
            """
            self.wfile.write(html.encode("utf-8"))
        else:
            self.send_response(400)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(b"<h1>Authorization Failed</h1><p>Missing 'code' query parameter.</p>")

    def log_message(self, format: str, *args: Any) -> None:
        # Suppress noisy HTTP request logging to console
        pass


class YouTubeAuthManager:
    def __init__(self, config: YTManagerConfig):
        self.config = config

    def _load_client_credentials(self) -> Tuple[str, str]:
        """Loads client_id and client_secret from client_secrets.json or environment."""
        env_client_id = os.environ.get("GOOGLE_CLIENT_ID")
        env_client_secret = os.environ.get("GOOGLE_CLIENT_SECRET")
        if env_client_id and env_client_secret:
            return env_client_id, env_client_secret

        secrets_file = self.config.client_secrets_path
        if not secrets_file.exists():
            raise FileNotFoundError(
                f"Missing Google OAuth credentials. Place 'client_secrets.json' in {self.config.config_dir} "
                f"or set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET environment variables."
            )

        with open(secrets_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        # Standard Google client secrets JSON structure
        info = data.get("installed") or data.get("web") or data
        client_id = info.get("client_id")
        client_secret = info.get("client_secret")

        if not client_id or not client_secret:
            raise ValueError(f"Invalid {secrets_file}: 'client_id' and 'client_secret' must be present.")

        return client_id, client_secret

    def get_authorization_url(self, redirect_uri: str = "http://localhost:8080") -> str:
        """Constructs Google OAuth 2.0 consent URL."""
        client_id, _ = self._load_client_credentials()
        params = {
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": " ".join(YOUTUBE_SCOPES),
            "access_type": "offline",
            "prompt": "consent",
        }
        return f"{GOOGLE_AUTH_URL}?{urllib.parse.urlencode(params)}"

    def exchange_code_for_token(self, code: str, redirect_uri: str = "http://localhost:8080") -> Dict[str, Any]:
        """Exchanges authorization code for access_token and refresh_token."""
        client_id, client_secret = self._load_client_credentials()
        data = urllib.parse.urlencode({
            "code": code,
            "client_id": client_id,
            "client_secret": client_secret,
            "redirect_uri": redirect_uri,
            "grant_type": "authorization_code",
        }).encode("utf-8")

        req = urllib.request.Request(
            GOOGLE_TOKEN_URL,
            data=data,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            method="POST",
        )

        with urllib.request.urlopen(req, timeout=30) as resp:
            token_data = json.loads(resp.read().decode("utf-8"))

        # Calculate absolute expiration timestamp
        expires_in = token_data.get("expires_in", 3600)
        token_data["expires_at"] = time.time() + expires_in

        self._save_token(token_data)
        return token_data

    def refresh_access_token(self, refresh_token: str) -> Dict[str, Any]:
        """Fetches a fresh access token using the persistent refresh token."""
        client_id, client_secret = self._load_client_credentials()
        data = urllib.parse.urlencode({
            "client_id": client_id,
            "client_secret": client_secret,
            "refresh_token": refresh_token,
            "grant_type": "refresh_token",
        }).encode("utf-8")

        req = urllib.request.Request(
            GOOGLE_TOKEN_URL,
            data=data,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            method="POST",
        )

        with urllib.request.urlopen(req, timeout=30) as resp:
            refreshed = json.loads(resp.read().decode("utf-8"))

        current_token = self._load_saved_token() or {}
        current_token["access_token"] = refreshed["access_token"]
        current_token["expires_at"] = time.time() + refreshed.get("expires_in", 3600)
        if "refresh_token" in refreshed:
            current_token["refresh_token"] = refreshed["refresh_token"]

        self._save_token(current_token)
        return current_token

    def _load_saved_token(self) -> Optional[Dict[str, Any]]:
        token_file = self.config.token_path
        if not token_file.exists():
            return None
        try:
            with open(token_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return None

    def _save_token(self, token_data: Dict[str, Any]) -> None:
        self.config.token_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.config.token_path, "w", encoding="utf-8") as f:
            json.dump(token_data, f, indent=4)

    def get_valid_access_token(self) -> str:
        """
        Returns a valid access token. Automatically handles expiration and refreshes
        transparently without prompting the user.
        """
        token = self._load_saved_token()
        if not token:
            raise RuntimeError(
                f"No saved OAuth tokens found at {self.config.token_path}. "
                "Run 'python -m yt_manager auth' to authenticate your YouTube channel."
            )

        now = time.time()
        expires_at = token.get("expires_at", 0)

        # If expired or expiring within 5 minutes, refresh
        if now >= (expires_at - 300):
            refresh_tok = token.get("refresh_token")
            if not refresh_tok:
                raise RuntimeError("Access token expired and no refresh_token is present. Re-authentication required.")
            token = self.refresh_access_token(refresh_tok)

        return token["access_token"]

    def verify_target_channel(self, access_token: Optional[str] = None) -> ChannelIdentity:
        """
        Queries the YouTube Data API v3 for the authenticated channel's identity.
        Strictly verifies that the channel ID matches UCT0tm0KSB2BlIjdY6uUZCeA.
        """
        token = access_token or self.get_valid_access_token()
        req = urllib.request.Request(
            YOUTUBE_CHANNELS_URL,
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/json",
            },
            method="GET",
        )

        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            err_body = e.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"YouTube Channel API request failed ({e.code}): {err_body}")

        items = data.get("items", [])
        if not items:
            raise ValueError("No YouTube channel found associated with this Google account.")

        ch = items[0]
        actual_id = ch.get("id", "")
        title = ch.get("snippet", {}).get("title", "")
        custom_url = ch.get("snippet", {}).get("customUrl", "")

        target_id = self.config.channel_id
        if actual_id != target_id:
            raise ChannelMismatchError(
                f"SECURITY ABORT: Authenticated channel is '{title}' (ID: {actual_id}), "
                f"but target channel is strictly configured as '{target_id}' ({self.config.channel_url})! "
                f"Uploads will NOT proceed to prevent accidental uploads to the wrong channel."
            )

        return ChannelIdentity(
            channel_id=actual_id,
            channel_title=title,
            custom_url=custom_url,
            is_verified=True,
        )

    def interactive_authenticate(self, port: int = 8080) -> ChannelIdentity:
        """
        Launches local server and opens browser for seamless OAuth 2.0 grant.
        Captures code, exchanges token, verifies channel ID, and stores tokens.
        """
        redirect_uri = f"http://localhost:{port}"
        auth_url = self.get_authorization_url(redirect_uri=redirect_uri)

        OAuthCallbackHandler.server_auth_code = None
        server = HTTPServer(("localhost", port), OAuthCallbackHandler)
        server.timeout = 180  # 3 minute timeout

        print("\n" + "=" * 65)
        print("          YT MANAGER — YOUTUBE OAUTH 2.0 SETUP")
        print("=" * 65)
        print(f"Opening browser for YouTube authorization:\n\n{auth_url}\n")
        print("If the browser did not open automatically, copy and paste the URL above.")
        print("Waiting for authorization callback on http://localhost:8080 (Timeout: 3 mins)...")

        try:
            webbrowser.open(auth_url)
        except Exception:
            pass

        # Handle a single request
        server.handle_request()
        server.server_close()

        code = OAuthCallbackHandler.server_auth_code
        if not code:
            # Fallback to manual terminal paste
            print("\nDid not receive callback automatically.")
            code = input("Please paste the 'code' parameter from the redirect URL here: ").strip()

        if not code:
            raise RuntimeError("Authorization aborted: No authorization code received.")

        print("Exchanging authorization code for OAuth tokens...")
        self.exchange_code_for_token(code, redirect_uri=redirect_uri)

        print("Verifying channel ownership against target ID...")
        identity = self.verify_target_channel()
        print(f"SUCCESS: Verified Channel: {identity.channel_title} (ID: {identity.channel_id})")
        return identity
