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
