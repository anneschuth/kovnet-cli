"""Tests for kovnet.helpers."""

from __future__ import annotations

from kovnet.helpers import extract_csrf_token, scrape_invoices_table


class TestExtractCsrfToken:
    def test_meta_tag(self):
        html = '<meta name="csrf-token" content="abc123token">'
        assert extract_csrf_token(html) == "abc123token"

    def test_input_name_before_value(self):
        html = '<input type="hidden" name="authenticity_token" value="token456">'
        assert extract_csrf_token(html) == "token456"

    def test_input_value_before_name(self):
        html = '<input type="hidden" value="token789" name="authenticity_token">'
        assert extract_csrf_token(html) == "token789"

    def test_meta_takes_priority(self):
        html = (
            '<meta name="csrf-token" content="meta_token">'
            '<input name="authenticity_token" value="input_token">'
        )
        assert extract_csrf_token(html) == "meta_token"

    def test_no_token_returns_none(self):
        html = "<html><body>No token here</body></html>"
        assert extract_csrf_token(html) is None

    def test_empty_string(self):
        assert extract_csrf_token("") is None

    def test_full_page_with_meta(self):
        html = """
        <html>
        <head>
            <meta name="csrf-param" content="authenticity_token">
            <meta name="csrf-token" content="RailsCSRFToken123+abc==">
        </head>
        <body>
            <form>
                <input type="text" name="email">
            </form>
        </body>
        </html>
        """
        assert extract_csrf_token(html) == "RailsCSRFToken123+abc=="

    def test_input_with_extra_attributes(self):
        html = '<input type="hidden" id="csrf" name="authenticity_token" class="x" value="tok">'
        assert extract_csrf_token(html) == "tok"


class TestScrapeInvoicesTable:
    def test_basic_table(self):
        html = """
        <table>
        <tbody>
            <tr>
                <td>001</td>
                <td>15-01-2024</td>
                <td>Januari</td>
                <td>2024</td>
                <td>€ 1.234,56</td>
                <td><a href="/invoices/001.pdf">PDF</a></td>
            </tr>
        </tbody>
        </table>
        """
        result = scrape_invoices_table(html)
        assert len(result) == 1
        assert result[0]["nr"] == "001"
        assert result[0]["datum"] == "15-01-2024"
        assert result[0]["maand"] == "Januari"
        assert result[0]["jaar"] == "2024"
        assert result[0]["bedrag"] == "€ 1.234,56"
        assert result[0]["pdf_url"] == "/invoices/001.pdf"

    def test_multiple_rows(self):
        html = """
        <table>
        <tbody>
            <tr><td>001</td><td>Jan</td><td>Jan</td><td>2024</td><td>100</td><td></td></tr>
            <tr><td>002</td><td>Feb</td><td>Feb</td><td>2024</td><td>200</td><td></td></tr>
        </tbody>
        </table>
        """
        result = scrape_invoices_table(html)
        assert len(result) == 2
        assert result[0]["nr"] == "001"
        assert result[1]["nr"] == "002"

    def test_no_tbody(self):
        html = "<table><tr><td>data</td></tr></table>"
        assert scrape_invoices_table(html) == []

    def test_empty_html(self):
        assert scrape_invoices_table("") == []

    def test_row_with_too_few_cells(self):
        html = """
        <table>
        <tbody>
            <tr><td>only</td><td>two</td></tr>
        </tbody>
        </table>
        """
        assert scrape_invoices_table(html) == []

    def test_no_pdf_link(self):
        html = """
        <table>
        <tbody>
            <tr>
                <td>001</td><td>Jan</td><td>Jan</td><td>2024</td><td>100</td>
                <td>Geen PDF</td>
            </tr>
        </tbody>
        </table>
        """
        result = scrape_invoices_table(html)
        assert len(result) == 1
        assert result[0]["pdf_url"] == ""
