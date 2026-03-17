"""Reusable helpers for KovNet data structures.

Pure stdlib — no external dependencies.
"""

from __future__ import annotations

import re


def extract_csrf_token(html: str) -> str | None:
    """Extract Rails CSRF authenticity_token from HTML.

    Looks for both <meta name="csrf-token" content="..."> and
    <input type="hidden" name="authenticity_token" value="...">.
    """
    # Meta tag pattern
    match = re.search(
        r'<meta\s+name="csrf-token"\s+content="([^"]+)"',
        html,
        re.IGNORECASE,
    )
    if match:
        return match.group(1)

    # Input field pattern (name before value)
    match = re.search(
        r'<input[^>]*name="authenticity_token"[^>]*value="([^"]+)"',
        html,
        re.IGNORECASE,
    )
    if match:
        return match.group(1)

    # Input field pattern (value before name)
    match = re.search(
        r'<input[^>]*value="([^"]+)"[^>]*name="authenticity_token"',
        html,
        re.IGNORECASE,
    )
    if match:
        return match.group(1)

    return None


def scrape_invoices_table(html: str) -> list[dict[str, str]]:
    """Parse the KovNet invoices DataTables HTML into a list of dicts.

    Returns dicts with keys: nr, datum, maand, jaar, bedrag, pdf_url.
    """
    invoices: list[dict[str, str]] = []

    # Find all table rows in tbody
    tbody_match = re.search(r"<tbody[^>]*>(.*?)</tbody>", html, re.DOTALL | re.IGNORECASE)
    if not tbody_match:
        return invoices

    tbody = tbody_match.group(1)
    rows = re.findall(r"<tr[^>]*>(.*?)</tr>", tbody, re.DOTALL | re.IGNORECASE)

    for row in rows:
        cells = re.findall(r"<td[^>]*>(.*?)</td>", row, re.DOTALL | re.IGNORECASE)
        if len(cells) < 5:
            continue

        # Extract PDF link if present
        pdf_match = re.search(r'href="([^"]*)"', cells[-1], re.IGNORECASE)
        pdf_url = pdf_match.group(1) if pdf_match else ""

        invoice = {
            "nr": re.sub(r"<[^>]+>", "", cells[0]).strip(),
            "datum": re.sub(r"<[^>]+>", "", cells[1]).strip(),
            "maand": re.sub(r"<[^>]+>", "", cells[2]).strip(),
            "jaar": re.sub(r"<[^>]+>", "", cells[3]).strip(),
            "bedrag": re.sub(r"<[^>]+>", "", cells[4]).strip(),
            "pdf_url": pdf_url,
        }
        invoices.append(invoice)

    return invoices


def scrape_chats_list(html: str) -> list[dict[str, str]]:
    """Parse the KovNet chats list page into a list of dicts.

    Returns dicts with keys: chat_key, group, location, child, unread, today.
    """
    chats: list[dict[str, str]] = []

    # Pattern: [N] <a href='/chats/KEY'> Location / Group : Child
    pattern = (
        r"\[\s*(\d+)\s*\]\s*"
        r"<a\s+href='(/chats/(\w+))'>\s*"
        r"(.*?)\s*/\s*<strong>(.*?)</strong>\s*:\s*"
        r"<strong[^>]*>\s*(.*?)\s*</strong>\s*</a>"
    )
    for match in re.finditer(pattern, html, re.DOTALL | re.IGNORECASE):
        unread = match.group(1)
        chat_key = match.group(3)
        location_name = match.group(4).strip()
        group_name = match.group(5).strip()
        child_raw = match.group(6).strip()
        # Remove "(groep van vandaag)" suffix
        child = re.sub(r"\s*\(groep van vandaag\)\s*", "", child_raw).strip()
        today = "(groep van vandaag)" in child_raw

        chats.append(
            {
                "chat_key": chat_key,
                "group": group_name,
                "location": location_name,
                "child": child,
                "unread": unread,
                "today": "true" if today else "false",
            }
        )

    return chats


def scrape_chat_messages(html: str) -> list[dict[str, str]]:
    """Parse KovNet chat message HTML fragments into a list of dicts.

    Returns dicts with keys: text, datetime, sender, is_parent, is_read.
    """
    messages: list[dict[str, str]] = []

    # Each message is a div.chat-message
    pattern = (
        r"<div\s+class='chat-message\s+([^']*)'>\s*"
        r"<div\s+class='message-text'>\s*"
        r"<span[^>]*>(.*?)</span>\s*"
        r"</div>\s*"
        r"<div\s+class='message-title'>\s*"
        r"(.*?)\s*</div>"
    )
    for match in re.finditer(pattern, html, re.DOTALL | re.IGNORECASE):
        classes = match.group(1)
        text = match.group(2).strip()
        title_raw = match.group(3).strip()

        is_parent = "message-parent" in classes

        is_read = "message_readed_sign" in title_raw or "&#10004;" in title_raw

        # Parse title: "2025-01-20 07:07 - Jan Jansen ✔"
        # Strip HTML tags and normalize whitespace
        title_clean = re.sub(r"<[^>]+>", "", title_raw)
        title_clean = re.sub(r"&#\d+;", "", title_clean)
        title_clean = " ".join(title_clean.split()).strip()
        # Split on " - " separator
        parts = title_clean.split(" - ", 1)
        dt = parts[0].strip() if parts else ""
        sender = parts[1].strip() if len(parts) > 1 else ""

        messages.append(
            {
                "text": text,
                "datetime": dt,
                "sender": sender,
                "is_parent": "true" if is_parent else "false",
                "is_read": "true" if is_read else "false",
            }
        )

    return messages
