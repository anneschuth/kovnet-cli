"""KovNet API client - session-cookie auth against app.kovnet.nl (Rails).

Authentication uses a 3-step flow:
1. GET /signin to obtain CSRF token + cookies
2. POST /check_users to verify credentials
3. POST /signin to complete login

Session cookies are stored locally and revalidated on use.
"""

from __future__ import annotations

import getpass
import json
import os
import re
from pathlib import Path
from types import TracebackType
from typing import Any

import httpx

from .helpers import (
    extract_csrf_token,
    scrape_chat_messages,
    scrape_chats_list,
    scrape_invoices_table,
)

# Endpoints
AUTH_BASE = "https://auth.kovnet.nl"
APP_BASE = "https://app.kovnet.nl"

# Session storage
SESSION_PATH = Path("~/.config/kovnet/session.json").expanduser()


def _save_session(data: dict[str, Any]) -> None:
    SESSION_PATH.parent.mkdir(parents=True, exist_ok=True)
    SESSION_PATH.write_text(json.dumps(data, indent=2))
    SESSION_PATH.chmod(0o600)


def _load_session() -> dict[str, Any] | None:
    if SESSION_PATH.exists():
        try:
            return json.loads(SESSION_PATH.read_text())
        except (json.JSONDecodeError, OSError):
            pass
    return None


class KovNetAuth:
    """Handle session-cookie authentication for KovNet."""

    @staticmethod
    def login(
        username: str | None = None,
        password: str | None = None,
        location_id: str | None = None,
        twofa_code: str | None = None,
    ) -> dict[str, Any]:
        """Log in to KovNet via the 3-step Rails auth flow.

        Returns a dict with cookies and location info for session persistence.
        """
        if not username:
            username = input("KovNet email: ")
        if not password:
            password = getpass.getpass("KovNet wachtwoord: ")

        with httpx.Client(
            follow_redirects=False,
            timeout=30,
            headers={"User-Agent": "Mozilla/5.0 (Macintosh) KovNet-CLI/0.1"},
        ) as client:
            # Step 1: GET /signin to get CSRF token + cookies
            resp = client.get(f"{AUTH_BASE}/signin")
            if resp.status_code in (301, 302, 303, 307, 308):
                location = resp.headers.get("location", "")
                if not location.startswith("http"):
                    location = f"{AUTH_BASE}{location}"
                resp = client.get(location)

            html = resp.text
            csrf_token = extract_csrf_token(html)
            if not csrf_token:
                raise RuntimeError(
                    "Kon geen CSRF token vinden. Mogelijk is de login pagina veranderd."
                )

            # Step 2: POST /check_users to verify credentials
            check_resp = client.post(
                f"{AUTH_BASE}/check_users",
                data={
                    "session[email]": username,
                    "session[password]": password,
                },
                headers={
                    "Content-Type": "application/x-www-form-urlencoded",
                    "X-CSRF-Token": csrf_token,
                    "X-Requested-With": "XMLHttpRequest",
                },
            )
            check_resp.raise_for_status()

            result = check_resp.text.strip().strip('"')

            if result == "none":
                raise RuntimeError("Login mislukt: onjuist wachtwoord of e-mailadres.")
            if result == "2fa_error":
                raise RuntimeError("Login mislukt: 2FA fout.")
            if result == "2fa_blocked":
                raise RuntimeError("Login mislukt: 2FA geblokkeerd.")

            if result == "2fa" and not twofa_code:
                twofa_code = input("Voer de 2FA code in (check je email): ")

            if result == "many" and not location_id:
                # Need to handle location selection
                raise RuntimeError(
                    "Meerdere locaties gevonden. Gebruik --location om een locatie te kiezen."
                )

            # Step 3: POST /signin to complete login
            signin_data: dict[str, str] = {
                "utf8": "✓",
                "authenticity_token": csrf_token,
                "session[email]": username,
                "session[password]": password,
            }
            if location_id:
                signin_data["location_id"] = location_id
            if twofa_code:
                signin_data["code"] = twofa_code

            signin_resp = client.post(
                f"{AUTH_BASE}/signin",
                data=signin_data,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )

            # Follow redirects to app.kovnet.nl
            max_redirects = 10
            for _ in range(max_redirects):
                if signin_resp.status_code not in (301, 302, 303, 307, 308):
                    break
                redirect_url = signin_resp.headers.get("location", "")
                if not redirect_url.startswith("http"):
                    redirect_url = f"{AUTH_BASE}{redirect_url}"
                signin_resp = client.get(redirect_url)

            # Extract cookies for session persistence
            cookies = dict(client.cookies)

            if not cookies:
                raise RuntimeError(
                    "Login mislukt: geen sessie cookies ontvangen. Controleer je inloggegevens."
                )

            # Try to extract location_id from redirect URL, page content, or sidebar
            detected_location = location_id
            if not detected_location:
                loc_match = re.search(r"/locations/(\d+)", str(signin_resp.url))
                if loc_match:
                    detected_location = loc_match.group(1)
                else:
                    loc_match = re.search(r"/locations/(\d+)", signin_resp.text)
                    if loc_match:
                        detected_location = loc_match.group(1)

            # If still no location, try fetching /chats which has sidebar links
            if not detected_location:
                try:
                    chats_resp = client.get(f"{APP_BASE}/chats", follow_redirects=True)
                    loc_match = re.search(r"/locations/(\d+)", chats_resp.text)
                    if loc_match:
                        detected_location = loc_match.group(1)
                except Exception:
                    pass

            session_data: dict[str, Any] = {
                "cookies": cookies,
                "location_id": detected_location,
                "username": username,
            }
            _save_session(session_data)
            return session_data

    @staticmethod
    def get_session() -> dict[str, Any] | None:
        """Get a valid session, validating cookies still work."""
        session = _load_session()
        if not session or not session.get("cookies"):
            return None

        cookies = session["cookies"]
        try:
            resp = httpx.get(
                f"{APP_BASE}/home",
                cookies=cookies,
                timeout=10,
                follow_redirects=False,
            )
            # If we get redirected to login, session is expired
            if resp.status_code in (301, 302, 303, 307, 308):
                location = resp.headers.get("location", "")
                if "signin" in location or "sign_in" in location or "auth" in location:
                    return KovNetAuth._try_auto_relogin()
            if resp.status_code == 200:
                return session
        except httpx.HTTPError:
            pass

        return KovNetAuth._try_auto_relogin()

    @staticmethod
    def _try_auto_relogin() -> dict[str, Any] | None:
        """Try to re-login using stored .env credentials."""
        from dotenv import load_dotenv

        env_path = SESSION_PATH.parent / ".env"
        load_dotenv(env_path)
        load_dotenv()

        username = os.environ.get("KOVNET_USERNAME", "")
        password = os.environ.get("KOVNET_PASSWORD", "")

        if username and password:
            try:
                return KovNetAuth.login(username=username, password=password)
            except Exception:
                pass
        return None


class KovNetClient:
    """Synchronous KovNet API client using session cookies."""

    def __init__(self, session: dict[str, Any] | None = None):
        self.session = session
        self._client: httpx.Client | None = None

    def __enter__(self) -> KovNetClient:
        if not self.session:
            self.session = KovNetAuth.get_session()
        if not self.session:
            raise RuntimeError("Niet ingelogd. Run `kovnet login` eerst.")
        self._client = httpx.Client(
            base_url=APP_BASE,
            timeout=30,
            cookies=self.session.get("cookies", {}),
            headers={
                "Accept": "application/json",
            },
            follow_redirects=True,
        )
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        if self._client:
            self._client.close()

    @property
    def location_id(self) -> str | None:
        if self.session:
            return self.session.get("location_id")
        return None

    def _get(self, path: str, **params: Any) -> Any:
        assert self._client is not None
        resp = self._client.get(path, params=params or None)
        resp.raise_for_status()
        return resp.json()

    def _get_html(self, path: str, **params: Any) -> str:
        assert self._client is not None
        resp = self._client.get(
            path,
            params=params or None,
            headers={"Accept": "text/html"},
        )
        resp.raise_for_status()
        return resp.text

    def _get_bytes(self, path: str) -> bytes:
        assert self._client is not None
        resp = self._client.get(path)
        resp.raise_for_status()
        return resp.content

    def get_children(self, location_id: str | None = None) -> list[dict[str, Any]]:
        loc = location_id or self.location_id
        if not loc:
            raise RuntimeError("Geen locatie ID bekend. Gebruik --location of login opnieuw.")
        return self._get(f"/parents/locations/{loc}/children")

    def get_contracts(self, location_id: str | None = None) -> list[dict[str, Any]]:
        loc = location_id or self.location_id
        if not loc:
            raise RuntimeError("Geen locatie ID bekend. Gebruik --location of login opnieuw.")
        contracts = self._get(f"/parents/locations/{loc}/contracts.json")

        # JSON endpoint doesn't include contract IDs — scrape them from the HTML page
        if contracts and not contracts[0].get("id"):
            html = self._get_html(f"/parents/locations/{loc}/contracts")
            contract_ids = re.findall(r"/contracts/(\d+)", html)
            # Deduplicate while preserving order
            seen: set[str] = set()
            unique_ids: list[str] = []
            for cid in contract_ids:
                if cid not in seen:
                    seen.add(cid)
                    unique_ids.append(cid)
            for i, contract in enumerate(contracts):
                if i < len(unique_ids):
                    contract["id"] = unique_ids[i]

        return contracts

    def get_holidays(
        self, contract_id: str, location_id: str | None = None
    ) -> list[dict[str, Any]]:
        loc = location_id or self.location_id
        if not loc:
            raise RuntimeError("Geen locatie ID bekend. Gebruik --location of login opnieuw.")
        return self._get(f"/parents/locations/{loc}/contracts/{contract_id}/holidays.json")

    def get_invoices(self, contract_id: str) -> list[dict[str, str]]:
        html = self._get_html(f"/parents/contracts/{contract_id}/invoices")
        return scrape_invoices_table(html)

    def get_newsletters(self, location_id: str | None = None) -> str:
        loc = location_id or self.location_id
        if not loc:
            raise RuntimeError("Geen locatie ID bekend. Gebruik --location of login opnieuw.")
        return self._get_html(f"/locations/{loc}/newsletters/parent_newsletters")

    def get_invoice_pdf(self, contract_id: str, invoice_id: str) -> bytes:
        return self._get_bytes(f"/parents/contracts/{contract_id}/invoices/{invoice_id}.pdf")

    def get_chats(self) -> list[dict[str, str]]:
        html = self._get_html("/chats")
        return scrape_chats_list(html)

    def get_chat_messages(self, chat_key: str) -> list[dict[str, str]]:
        """Get all messages for a chat (older + today)."""
        from concurrent.futures import ThreadPoolExecutor

        with ThreadPoolExecutor(max_workers=2) as pool:
            older_fut = pool.submit(self._get_html, f"/chat_older_messages/{chat_key}")
            today_fut = pool.submit(self._get_html, f"/chat_messages/{chat_key}")
            older = scrape_chat_messages(older_fut.result())
            today = scrape_chat_messages(today_fut.result())
        return older + today

    def get_all_chat_messages(self, chat_keys: list[str]) -> dict[str, list[dict[str, str]]]:
        """Get messages for multiple chats in parallel."""
        from concurrent.futures import ThreadPoolExecutor

        with ThreadPoolExecutor(max_workers=6) as pool:
            futures = {key: pool.submit(self.get_chat_messages, key) for key in chat_keys}
            return {key: fut.result() for key, fut in futures.items()}

    def explore(self, path: str) -> httpx.Response:
        """Fetch an arbitrary path with session cookies. For exploration."""
        assert self._client is not None
        resp = self._client.get(path)
        resp.raise_for_status()
        return resp
