from weasyprint import HTML, CSS


def generate_pdf_from_html_weasy(html: str, base_url: str = None, margins: dict | None = None) -> bytes:
    """Generate a PDF from HTML using WeasyPrint.

    - `html`: rendered HTML string
    - `base_url`: base URL to resolve relative static assets
    - `margins`: dict with keys 'top','right','bottom','left' (e.g. '20mm')

    Returns PDF bytes or raises RuntimeError on failure.
    """
    try:
        if margins is None:
            margins = {"top": "20mm", "right": "12mm", "bottom": "20mm", "left": "12mm"}
        # Create a small stylesheet that sets the @page margin according to provided values
        css = CSS(string=f"@page {{ size: A4; margin: {margins.get('top')} {margins.get('right')} {margins.get('bottom')} {margins.get('left')}; }}")
        doc = HTML(string=html, base_url=base_url)
        pdf = doc.write_pdf(stylesheets=[css])
        return pdf
    except Exception as e:
        raise RuntimeError(f"WeasyPrint PDF generation failed: {e}")
