from app import app
from flask import render_template, url_for
from modules.admin.routes import load_print_templates
from models.inventory import Handover
from utils.weasy_pdf import generate_pdf_from_html_weasy
import os

OUTPUT = '/app/tmp/protocol_48_weasy.pdf'
HANDOVER_ID = 48

app.config['SERVER_NAME'] = 'localhost:5000'
app.config['PREFERRED_URL_SCHEME'] = 'http'
with app.test_request_context('/', base_url='http://localhost:5000'):
    h = Handover.query.get(HANDOVER_ID)
    if not h:
        print(f'Handover {HANDOVER_ID} not found')
        raise SystemExit(2)

    templates = load_print_templates() or []
    selected = templates[0] if templates else None
    header_url = None
    footer_url = None
    header_height = 30
    footer_height = 30
    header_width = None
    footer_width = None
    header_position = 'center'
    footer_position = 'center'
    header_is_background = True
    footer_is_background = True
    header_constrain = True
    footer_constrain = True
    if selected:
        header_url = selected.get('header_url')
        footer_url = selected.get('footer_url')
        header_height = selected.get('header_height_mm', 30)
        footer_height = selected.get('footer_height_mm', 30)
        header_width = selected.get('header_width_mm')
        footer_width = selected.get('footer_width_mm')
        header_position = selected.get('header_position', 'center')
        footer_position = selected.get('footer_position', 'center')
        header_is_background = selected.get('header_is_background', True)
        footer_is_background = selected.get('footer_is_background', True)
        header_constrain = selected.get('header_constrain', True)
        footer_constrain = selected.get('footer_constrain', True)

    html = render_template('inventory_admin/protocol.html', handover=h, is_return=False, header_url=header_url, footer_url=footer_url, templates=templates,
                           header_height=header_height, footer_height=footer_height, header_width=header_width, footer_width=footer_width,
                           header_position=header_position, footer_position=footer_position, header_is_background=header_is_background, footer_is_background=footer_is_background,
                           header_constrain=header_constrain, footer_constrain=footer_constrain)

    # inject base -- use localhost since this runs inside container
    if '<head>' in html:
        html = html.replace('<head>', f"<head><base href='http://localhost:5000/'>")

    pdf = generate_pdf_from_html_weasy(html, base_url='http://localhost:5000/', margins={"top":"40mm","right":"12mm","bottom":"40mm","left":"12mm"})
    os.makedirs(os.path.dirname(OUTPUT), exist_ok=True)
    with open(OUTPUT, 'wb') as f:
        f.write(pdf)
    print('Wrote PDF to', OUTPUT)
