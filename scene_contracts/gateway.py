"""Local Hafnia gateway transport and v0.1 parsing helpers."""
from __future__ import annotations

from datetime import datetime, timezone
import getpass
import json
import os
import re
import ssl
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, build_opener, HTTPSHandler, HTTPRedirectHandler

BASE = "https://localhost:15443"
DECISIONS = {"H26_DAMAGE_EVENT", "H26_NO_DAMAGE_EVENT", "H26_UNCERTAIN"}


class GatewayError(Exception):
    pass


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise GatewayError("Gateway redirect refused; credentials must stay on the local gateway")


def extract_decision(text: str) -> str | None:
    """Accept only an explicit decision on its own line, never substring matches."""
    matches = re.findall(r"(?mi)^DECISION:\s*(H26_[A-Z_]+)\s*$", text)
    return matches[0] if len(matches) == 1 and matches[0] in DECISIONS else None


def summary_response_text(item: dict) -> str:
    """The gateway currently documents Response as text, but preserve unknown shapes."""
    response = item.get("Response", "")
    if isinstance(response, str):
        return response
    if isinstance(response, dict):
        return json.dumps(response, ensure_ascii=False, indent=2)
    return str(response or "")


def format_utc(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def video_uri(camera_id: str, start: datetime, end: datetime) -> str:
    if not re.fullmatch(r"[0-9a-fA-F-]{36}", camera_id):
        raise ValueError("Expected a camera GUID from Get-VmsCamera; do not use a camera name here")
    if not start < end:
        raise ValueError("Start must precede end")
    return f"xprotect://localhost/cameras/{camera_id}?StartTime={format_utc(start)}&EndTime={format_utc(end)}"


class Gateway:
    def __init__(self, base: str = BASE):
        parts = urlsplit(base)
        if (parts.hostname not in {"localhost", "127.0.0.1"} or parts.scheme != "https"
                or parts.username or parts.password or parts.path not in {"", "/"}
                or parts.query or parts.fragment):
            raise GatewayError("This client only supports the local Hafnia gateway")
        self.base = base.rstrip("/")
        self.session: str | None = None
        # VM gateway uses a self-signed certificate. No other HTTPS hosts are used.
        self.ssl_context = ssl._create_unverified_context()
        self.opener = build_opener(NoRedirect(), HTTPSHandler(context=self.ssl_context))

    def request(self, method: str, path: str, payload: dict | None = None, login: bool = False):
        headers = {"Accept": "application/json"}
        if self.session and not login:
            headers["X-Session-Id"] = self.session
        data = None if payload is None else json.dumps(payload).encode("utf-8")
        if data is not None:
            headers["Content-Type"] = "application/json"
        req = Request(self.base + path, data=data, headers=headers, method=method)
        try:
            with self.opener.open(req, timeout=30) as resp:
                body = resp.read()
                return json.loads(body) if body else None
        except HTTPError as exc:
            # Never echo response content during login: it may reflect credentials.
            if login:
                raise GatewayError(f"Gateway login failed (HTTP {exc.code})") from None
            raise GatewayError(f"{method} {path.split('?')[0]} failed (HTTP {exc.code})") from None
        except (URLError, TimeoutError):
            raise GatewayError("Cannot reach local Hafnia gateway") from None

    def authenticate(self):
        password = os.getenv("HAFNIA_GW_PASSWORD") or getpass.getpass("Gateway administrator password: ")
        response = self.request("POST", "/api/Sessions/Login", {"Name": "administrator", "Password": password}, login=True)
        self.session = response.get("Id") if isinstance(response, dict) else None
        if not self.session:
            raise GatewayError("Login returned no session ID")

    def items(self, path: str) -> list:
        value = self.request("GET", path)
        if isinstance(value, list):
            return value
        if isinstance(value, dict):
            return value.get("PageContent") or value.get("Items") or []
        return []

    def exact_item(self, collection: str, title_field: str, expected: str) -> dict | None:
        path = f"/api/{collection}?{urlencode({'SearchString': expected, 'Limit': 100})}"
        matches = [it for it in self.items(path) if it.get(title_field) == expected]
        if len(matches) > 1:
            raise GatewayError(f"Multiple {collection} called {expected!r}; resolve duplicates first")
        return matches[0] if matches else None

