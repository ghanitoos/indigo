"""Utility to render HTML to PDF using Playwright.
Provides a small wrapper so routes remain clean.
"""
from typing import Optional, Dict
import traceback
from flask import current_app

try:
    from playwright.sync_api import sync_playwright
except Exception:
    sync_playwright = None


def generate_pdf_from_html(html: str, base_url: Optional[str] = None, margins: Optional[Dict[str, str]] = None) -> bytes:
    """Render the given HTML string to PDF bytes using Playwright Chromium.

    Args:
        html: full HTML string to render
        base_url: optional base URL to resolve relative assets
        margins: dict of top/bottom/left/right string values (e.g. '20mm')

    Returns:
        PDF bytes

    Raises:
        RuntimeError if Playwright not available or rendering fails.
    """
    if sync_playwright is None:
        raise RuntimeError("Playwright is not installed in this environment")

    try:
        with sync_playwright() as p:
            # Launch without sandbox to improve compatibility inside containers
            browser = p.chromium.launch(args=['--no-sandbox'])
            page = browser.new_page()
            if base_url:
                # ensure relative URLs resolve
                page.set_content(html, wait_until='networkidle', base_url=base_url)
            else:
                page.set_content(html, wait_until='networkidle')

            pdf_opts = { 'format': 'A4', 'print_background': True }
            if margins:
                pdf_opts['margin'] = margins

            pdf_bytes = page.pdf(**pdf_opts)
            browser.close()
            return pdf_bytes
    except Exception as e:
        current_app.logger.error('PDF generation failed: %s', traceback.format_exc())
        raise RuntimeError('PDF generation failed') from e
