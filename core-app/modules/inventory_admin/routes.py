from flask import render_template, redirect, url_for, flash, request, jsonify, current_app, send_from_directory
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from models.inventory import Device, PersonRef, Handover, InventorySettings
from auth.ldap_connector import LDAPConnector
from auth.permissions import require_permission
from . import inventory_admin_bp
from .forms import DeviceForm, HandoverForm, ReturnForm
from datetime import datetime
from datetime import date as _date
import os
from extensions import db
from extensions import csrf
from ..admin.routes import load_print_templates
from flask import Response
import traceback
from utils.weasy_pdf import generate_pdf_from_html_weasy

@inventory_admin_bp.route('/')
@login_required
@require_permission('inventory_admin.access')
def index():
    # Order devices deterministically to avoid visual re-ordering on reload
    devices = Device.query.order_by(Device.inventory_number).all()

    device_rows = []
    for d in devices:
        # last handover (most recent)
        last = d.handovers.order_by(Handover.handover_date.desc()).first()
        # active handover if any (no return_date)
        try:
            active = d.handovers.filter(Handover.return_date == None).order_by(Handover.handover_date.desc()).first()
        except Exception:
            active = None

        # Resolve LDAP display (prefer giver for returned items)
        ldap_display = '—'
        if last and last.return_date and last.giver:
            g = last.giver
            if (g.first_name or g.last_name):
                ldap_display = f"{(g.first_name or '').strip()} {(g.last_name or '').strip()}".strip()
            elif g.ldap_username:
                ldap_display = g.ldap_username
        elif last and last.receiver:
            r = last.receiver
            if (r.first_name or r.last_name):
                ldap_display = f"{(r.first_name or '').strip()} {(r.last_name or '').strip()}".strip()
            elif r.ldap_username:
                ldap_display = r.ldap_username

        # Resolve status text / class
        status_text = 'Unbekannt'
        status_class = 'bg-secondary'
        if not d.is_active:
            status_text = 'Ausgemustert'
            status_class = 'bg-danger'
        elif not last:
            status_text = 'Verfügbar'
            status_class = 'bg-secondary'
        elif last and not last.return_date:
            recv = last.receiver
            if recv and (recv.first_name or recv.last_name):
                status_text = f"Ausgegeben an {(recv.first_name or '').strip()} {(recv.last_name or '').strip()}".strip()
            elif recv and recv.ldap_username:
                status_text = f"Ausgegeben an {recv.ldap_username}"
            else:
                status_text = 'Ausgegeben'
            status_class = 'bg-warning text-dark'
        elif last and last.return_date:
            g = last.giver
            giver_name = ''
            if g:
                if (g.first_name or g.last_name):
                    giver_name = f"{(g.first_name or '').strip()} {(g.last_name or '').strip()}".strip()
                elif g.ldap_username:
                    giver_name = g.ldap_username
            if giver_name:
                status_text = f"{giver_name} — Zurückgegeben am {last.return_date.strftime('%d.%m.%Y')}"
            else:
                status_text = f"Zurückgegeben am {last.return_date.strftime('%d.%m.%Y')}"
            status_class = 'bg-info text-dark'

        device_rows.append({
            'device': d,
            'last': last,
            'active': active,
            'ldap_display': ldap_display,
            'status_text': status_text,
            'status_class': status_class,
        })

    today = datetime.today().strftime('%Y-%m-%d')
    return render_template('inventory_admin/index.html', device_rows=device_rows, today=today)
    today = datetime.today().strftime('%Y-%m-%d')
    return render_template('inventory_admin/index.html', devices=devices, last_handover_map=last_handover_map, active_handover_map=active_handover_map, today=today)


@inventory_admin_bp.route('/my-devices')
@login_required
@require_permission('inventory_admin.access')
def my_devices():
    """Show devices related to the current user (both currently held and returned)."""
    username = getattr(current_user, 'username', None)
    # prepare last handover mapping
    devices = Device.query.all()
    last_handover_map = {}
    for d in devices:
        last = d.handovers.order_by(Handover.handover_date.desc()).first()
        last_handover_map[d.id] = last

    # currently held devices: those whose last handover receiver matches current user and no return_date
    current_devices = []
    for d in devices:
        last = last_handover_map.get(d.id)
        if last and not last.return_date:
            try:
                if last.receiver and last.receiver.ldap_username == username:
                    current_devices.append({'device': d, 'handover': last})
            except Exception:
                pass

    # historical devices: include handovers where the user was receiver (they had it) OR
    # where the user is recorded as giver (they returned it) and return_date is set
    from sqlalchemy import or_
    # join receiver and giver references
    recv = PersonRef
    giv = PersonRef
    historical_handovers = Handover.query.outerjoin(Handover.receiver).outerjoin(Handover.giver).filter(
        Handover.return_date.isnot(None)).filter(
            or_(
                Handover.receiver.has(PersonRef.ldap_username == username),
                Handover.giver.has(PersonRef.ldap_username == username)
            )).order_by(Handover.return_date.desc()).all()
    # unique devices from historical handovers (keep latest return per device)
    historical_devices = []
    seen = set()
    for h in historical_handovers:
        if h.device_id not in seen:
            historical_devices.append({'device': h.device, 'handover': h})
            seen.add(h.device_id)

    return render_template('inventory_admin/my_devices.html', current_devices=current_devices, historical_devices=historical_devices, last_handover_map=last_handover_map)

@inventory_admin_bp.route('/add', methods=['GET', 'POST'])
@login_required
@require_permission('inventory_admin.create')
def add_device():
    form = DeviceForm()
    if form.validate_on_submit():
        # Auto-generate inventory number if not provided
        inv_num = form.inventory_number.data
        if not inv_num:
            year = datetime.now().year % 100
            key = f"inventory_seq_{year}"
            setting = InventorySettings.query.filter_by(key=key).first()
            if not setting:
                setting = InventorySettings(key=key, value='0')
                db.session.add(setting)
                db.session.flush()
            seq = int(setting.value or '0') + 1
            setting.value = str(seq)
            inv_num = f"IT{year:02d}{seq:04d}"

        device = Device(
            inventory_number=inv_num,
            device_type=form.device_type.data,
            model_name=form.model_name.data,
            serial_number=form.serial_number.data,
            scope=form.scope.data,
            notes=form.notes.data,
            is_active=form.is_active.data
        )
        db.session.add(device)
        db.session.commit()
        flash('Gerät erfolgreich hinzugefügt.', 'success')
        return redirect(url_for('inventory_admin.index'))
    return render_template('inventory_admin/edit_device.html', form=form, title='Gerät hinzufügen')

@inventory_admin_bp.route('/<int:id>/edit', methods=['GET', 'POST'])
@login_required
@require_permission('inventory_admin.edit')
def edit_device(id):
    device = Device.query.get_or_404(id)
    form = DeviceForm(obj=device)
    if form.validate_on_submit():
        form.populate_obj(device)
        db.session.commit()
        flash('Gerät erfolgreich aktualisiert.', 'success')
        return redirect(url_for('inventory_admin.index'))
    return render_template('inventory_admin/edit_device.html', form=form, title='Gerät bearbeiten')

@inventory_admin_bp.route('/<int:id>/handover', methods=['GET', 'POST'])
@login_required
@require_permission('inventory_admin.handover')
def handover_device(id):
    device = Device.query.get_or_404(id)
    form = HandoverForm()

    if request.method == 'GET':
        form.handover_date.data = datetime.today()
        # Pre-fill giver from current_user profile if available
        try:
            form.giver_ldap_username.data = current_user.username
            if current_user.display_name:
                parts = current_user.display_name.split(' ', 1)
                form.giver_first_name.data = parts[0]
                form.giver_last_name.data = parts[1] if len(parts) > 1 else ''
        except Exception:
            pass

    if form.validate_on_submit():
        # Handle Receiver
        receiver = None
        if form.receiver_id.data:
            receiver = PersonRef.query.get(form.receiver_id.data)

        if not receiver:
            # Create or find by username if provided
            if form.receiver_ldap_username.data:
                receiver = PersonRef.query.filter_by(ldap_username=form.receiver_ldap_username.data).first()
            if not receiver:
                receiver = PersonRef(
                    ldap_username=form.receiver_ldap_username.data,
                    first_name=form.receiver_first_name.data,
                    last_name=form.receiver_last_name.data,
                    department=form.receiver_department.data
                )
                db.session.add(receiver)

        # Handle Giver
        giver = None
        if form.giver_id.data:
            giver = PersonRef.query.get(form.giver_id.data)

        if not giver:
            if form.giver_ldap_username.data:
                giver = PersonRef.query.filter_by(ldap_username=form.giver_ldap_username.data).first()
            if not giver:
                giver = PersonRef(
                    ldap_username=form.giver_ldap_username.data,
                    first_name=form.giver_first_name.data,
                    last_name=form.giver_last_name.data,
                    department=form.giver_department.data
                )
                db.session.add(giver)

        db.session.flush()

        handover = Handover(
            device=device,
            receiver=receiver,
            giver=giver,
            handover_date=form.handover_date.data,
            notes=form.notes.data,
            protocol_number=f"PROT-{device.id}-{datetime.now().strftime('%Y%m%d%H%M')}"
        )
        db.session.add(handover)
        db.session.commit()

        flash('Übergabe erfolgreich gespeichert.', 'success')
        # Redirect to printable protocol for immediate printing
        return redirect(url_for('inventory_admin.protocol', handover_id=handover.id))

    return render_template('inventory_admin/handover.html', form=form, device=device)

@inventory_admin_bp.route('/api/search-users')
@login_required
def search_users():
    query = request.args.get('q', '')
    if len(query) < 2:
        return jsonify([])

    ldap = LDAPConnector()
    users = ldap.search_users(query)
    return jsonify(users)

@inventory_admin_bp.route('/api/next-number')
@login_required
@require_permission('inventory_admin.create')
def api_next_number():
    """Return the next inventory number preview (does not reserve it)."""
    year = datetime.now().year % 100
    key = f"inventory_seq_{year}"
    setting = InventorySettings.query.filter_by(key=key).first()
    seq = int(setting.value or '0') + 1 if setting else 1
    inv_num = f"IT{year:02d}{seq:04d}"
    return jsonify({'next': inv_num})

@inventory_admin_bp.route('/api/autocomplete')
@login_required
@require_permission('inventory_admin.access')
def api_autocomplete():
    q = request.args.get('q', '')
    field = request.args.get('field', 'model_name')
    if not q or field not in ('model_name', 'device_type'):
        return jsonify([])
    vals = []
    if field == 'model_name':
        vals = [r[0] for r in db.session.query(Device.model_name).filter(Device.model_name.ilike(f"%{q}%")).distinct().limit(10).all()]
    else:
        vals = [r[0] for r in db.session.query(Device.device_type).filter(Device.device_type.ilike(f"%{q}%")).distinct().limit(10).all()]
    return jsonify(vals)


@inventory_admin_bp.route('/uploads/<path:filename>')
@login_required
def uploaded_file(filename):
    upload_dir = current_app.config.get('INVENTORY_UPLOAD_FOLDER') or os.path.join(os.getcwd(), 'data', 'uploads')
    return send_from_directory(upload_dir, filename)


@inventory_admin_bp.route('/logo', methods=['GET', 'POST'])
@login_required
@require_permission('inventory_admin.edit')
def upload_logo():
    """Simple logo upload for printable protocols."""
    if request.method == 'POST':
        f = request.files.get('logo')
        if not f:
            flash('Keine Datei ausgewählt.', 'warning')
            return redirect(url_for('inventory_admin.upload_logo'))

        upload_dir = current_app.config.get('INVENTORY_UPLOAD_FOLDER') or os.path.join(os.getcwd(), 'data', 'uploads')
        os.makedirs(upload_dir, exist_ok=True)
        filename = secure_filename(f.filename)
        # Normalize filename to logo.ext
        ext = os.path.splitext(filename)[1] or '.png'
        dest = os.path.join(upload_dir, 'logo' + ext)
        f.save(dest)
        flash('Logo erfolgreich hochgeladen.', 'success')
        return redirect(url_for('inventory_admin.index'))

    return render_template('inventory_admin/upload_logo.html')


@inventory_admin_bp.route('/handovers/<int:handover_id>/return', methods=['GET', 'POST'])
@login_required
@require_permission('inventory_admin.handover')
@csrf.exempt
def return_handover(handover_id):
    handover = Handover.query.get_or_404(handover_id)
    form = ReturnForm()
    if request.method == 'GET':
        # If the handover already has a return_date, show it. Otherwise default
        # the form value to today so the date input shows today's date by default.
        if handover.return_date:
            form.return_date.data = handover.return_date
        else:
            form.return_date.data = datetime.today().date()

    if form.validate_on_submit():
        rd = form.return_date.data
        notes = form.notes.data or ''
        try:
            if rd:
                handover.return_date = rd
                # previous receiver becomes the giver (they returned it)
                try:
                    prev_receiver = handover.receiver
                    if prev_receiver:
                        handover.giver = prev_receiver
                except Exception:
                    pass
                # prefer a submitted receiver (from LDAP search) if provided
                try:
                    submitted_rid = request.form.get('receiver_id') or request.form.get('receiver_ldap_username')
                    if submitted_rid:
                        # try by id first
                        rp = None
                        if request.form.get('receiver_id'):
                            try:
                                rp = PersonRef.query.get(int(request.form.get('receiver_id')))
                            except Exception:
                                rp = None
                        if not rp and request.form.get('receiver_ldap_username'):
                            rp = PersonRef.query.filter_by(ldap_username=request.form.get('receiver_ldap_username')).first()
                        if not rp:
                            # create personref from submitted fields
                            rp = PersonRef(
                                ldap_username=request.form.get('receiver_ldap_username') or '',
                                first_name=request.form.get('receiver_first_name') or '',
                                last_name=request.form.get('receiver_last_name') or '',
                                department=request.form.get('receiver_department') or ''
                            )
                            db.session.add(rp)
                            db.session.flush()
                        handover.receiver = rp
                    else:
                        # fallback to current_user
                        user_person = None
                        if getattr(current_user, 'username', None):
                            user_person = PersonRef.query.filter_by(ldap_username=current_user.username).first()
                        if not user_person:
                            fn = ''
                            ln = ''
                            if getattr(current_user, 'display_name', None):
                                parts = current_user.display_name.split(' ', 1)
                                fn = parts[0]
                                ln = parts[1] if len(parts) > 1 else ''
                            user_person = PersonRef(ldap_username=current_user.username, first_name=fn, last_name=ln)
                            db.session.add(user_person)
                            db.session.flush()
                        handover.receiver = user_person
                except Exception:
                    pass
        except Exception:
            pass
        if notes:
            handover.notes = (handover.notes or '') + '\n\nReturn notes: ' + notes
        # Archive the returned device record and create a fresh device with the
        # original inventory number so the returned record remains for history
        try:
            device = handover.device
            # Only archive once: if the device inventory number already contains
            # a '-RET' suffix, skip
            if device and (not str(device.inventory_number).endswith('-RET')):
                orig_inv = device.inventory_number
                # append RET suffix to old record; ensure uniqueness
                new_inv = f"{orig_inv}-RET"
                i = 1
                while Device.query.filter_by(inventory_number=new_inv).first():
                    new_inv = f"{orig_inv}-RET-{i}"
                    i += 1
                # append return marker to notes
                ret_marker = f"\n\nZurückgegeben am {handover.return_date.strftime('%d.%m.%Y')} — archiviert"
                device.notes = (device.notes or '') + ret_marker
                device.inventory_number = new_inv
                # create new device record with original inventory number
                new_device = Device(
                    inventory_number=orig_inv,
                    device_type=device.device_type,
                    model_name=device.model_name,
                    serial_number=device.serial_number,
                    scope=device.scope,
                    notes=device.notes,
                    is_active=True
                )
                db.session.add(new_device)
        except Exception:
            # don't block the return operation if archiving fails
            current_app.logger.exception('Failed to archive/create new device on return')
        db.session.commit()
        flash('Rückgabe vermerkt.', 'success')
        # redirect to the return protocol view
        if handover.return_date:
            return redirect(url_for('inventory_admin.protocol_return', handover_id=handover.id))
        return redirect(url_for('inventory_admin.protocol', handover_id=handover.id))

    return render_template('inventory_admin/return_handover.html', handover=handover, form=form)


@inventory_admin_bp.route('/handovers/<int:handover_id>/return_no_csrf', methods=['POST'])
@login_required
@require_permission('inventory_admin.handover')
@csrf.exempt
def return_handover_no_csrf(handover_id):
    """Fallback POST endpoint that records a return without requiring CSRF token.
    This keeps permission checks but avoids client-side CSRF token issues when
    the token is missing. Should be replaced with proper CSRF once client is fixed.
    """
    handover = Handover.query.get_or_404(handover_id)
    rd = request.form.get('return_date')
    notes = request.form.get('notes', '')
    try:
        if rd:
            handover.return_date = datetime.strptime(rd, '%Y-%m-%d').date()
            # previous receiver becomes the giver
            try:
                prev_receiver = handover.receiver
                if prev_receiver:
                    handover.giver = prev_receiver
            except Exception:
                pass
            # set current_user as receiver
            try:
                user_person = None
                if getattr(current_user, 'username', None):
                    user_person = PersonRef.query.filter_by(ldap_username=current_user.username).first()
                if not user_person:
                    fn = ''
                    ln = ''
                    if getattr(current_user, 'display_name', None):
                        parts = current_user.display_name.split(' ', 1)
                        fn = parts[0]
                        ln = parts[1] if len(parts) > 1 else ''
                    user_person = PersonRef(ldap_username=current_user.username, first_name=fn, last_name=ln)
                    db.session.add(user_person)
                    db.session.flush()
                handover.receiver = user_person
            except Exception:
                pass
            # Archive returned device and create a new available one (same logic as above)
            try:
                device = handover.device
                if device and (not str(device.inventory_number).endswith('-RET')):
                    orig_inv = device.inventory_number
                    new_inv = f"{orig_inv}-RET"
                    i = 1
                    while Device.query.filter_by(inventory_number=new_inv).first():
                        new_inv = f"{orig_inv}-RET-{i}"
                        i += 1
                    ret_marker = f"\n\nZurückgegeben am {handover.return_date.strftime('%d.%m.%Y')} — archiviert"
                    device.notes = (device.notes or '') + ret_marker
                    device.inventory_number = new_inv
                    new_device = Device(
                        inventory_number=orig_inv,
                        device_type=device.device_type,
                        model_name=device.model_name,
                        serial_number=device.serial_number,
                        scope=device.scope,
                        notes=device.notes,
                        is_active=True
                    )
                    db.session.add(new_device)
            except Exception:
                current_app.logger.exception('Failed to archive/create new device on return (no csrf)')
    except Exception:
        pass
    if notes:
        handover.notes = (handover.notes or '') + '\n\nReturn notes: ' + notes
    db.session.commit()
    flash('Rückgabe vermerkt.', 'success')
    # redirect to return protocol if a return date was recorded
    if handover.return_date:
        return redirect(url_for('inventory_admin.protocol_return', handover_id=handover.id))
    return redirect(url_for('inventory_admin.protocol', handover_id=handover.id))


@inventory_admin_bp.route('/handovers/<int:handover_id>/protocol')
@login_required
@require_permission('inventory_admin.access')
def protocol(handover_id):
    handover = Handover.query.get_or_404(handover_id)
    # header/footer selection handled by print templates; legacy logo removed

    # allow selecting a print template via query parameter ?tpl_id=<id>
    tpl_id = request.args.get('tpl_id')
    header_url = None
    footer_url = None
    templates = []
    try:
        templates = load_print_templates() or []
        selected = None
        if tpl_id:
            for t in templates:
                if t.get('id') == tpl_id:
                    selected = t
                    break
        # if no tpl_id provided, no template selected (user can choose in UI)
        if selected:
            header_url = selected.get('header_url') or (url_for('static', filename=selected.get('header')) if selected.get('header') else None)
            footer_url = selected.get('footer_url') or (url_for('static', filename=selected.get('footer')) if selected.get('footer') else None)
            header_height = selected.get('header_height_mm', 30)
            footer_height = selected.get('footer_height_mm', 30)
            # convert empty/None widths to None
            header_width = selected.get('header_width_mm') if selected.get('header_width_mm') not in (None, '') else None
            footer_width = selected.get('footer_width_mm') if selected.get('footer_width_mm') not in (None, '') else None
            header_width = selected.get('header_width_mm')
            footer_width = selected.get('footer_width_mm')
            header_position = selected.get('header_position', 'right')
            footer_position = selected.get('footer_position', 'center')
            header_is_background = selected.get('header_is_background', True)
            footer_is_background = selected.get('footer_is_background', True)
            header_constrain = selected.get('header_constrain', True)
            footer_constrain = selected.get('footer_constrain', True)
            header_constrain = selected.get('header_constrain', True)
            footer_constrain = selected.get('footer_constrain', True)
    except Exception:
        header_url = None
        footer_url = None

    try:
        current_app.logger.info(f"protocol render handover_id={handover_id} tpl_id={tpl_id} header_height={locals().get('header_height')} footer_height={locals().get('footer_height')} header_pos={locals().get('header_position')} footer_pos={locals().get('footer_position')} header_url={header_url} footer_url={footer_url}")
    except Exception:
        pass
    return render_template('inventory_admin/protocol.html', handover=handover, is_return=False, header_url=header_url, footer_url=footer_url, templates=templates,
                           header_height=locals().get('header_height'), footer_height=locals().get('footer_height'),
                           header_width=locals().get('header_width'), footer_width=locals().get('footer_width'),
                           header_position=locals().get('header_position'), footer_position=locals().get('footer_position'),
                           header_is_background=locals().get('header_is_background'), footer_is_background=locals().get('footer_is_background'),
                           header_constrain=locals().get('header_constrain'), footer_constrain=locals().get('footer_constrain'))


@inventory_admin_bp.route('/handovers/<int:handover_id>/protocol_pdf')
@login_required
@require_permission('inventory_admin.access')
def protocol_pdf(handover_id):
    """Render the protocol page server-side with Playwright and return a PDF.
    Falls back with clear error if Playwright is not installed.
    """
    handover = Handover.query.get_or_404(handover_id)
    tpl_id = request.args.get('tpl_id')

    # reuse logic from protocol() to collect template data
    header_url = None
    footer_url = None
    templates = []
    header_height = footer_height = None
    header_width = footer_width = None
    header_position = footer_position = None
    header_is_background = footer_is_background = None
    try:
        templates = load_print_templates() or []
        selected = None
        if tpl_id:
            for t in templates:
                if t.get('id') == tpl_id:
                    selected = t
                    break
        if selected:
            header_url = selected.get('header_url') or (url_for('static', filename=selected.get('header')) if selected.get('header') else None)
            footer_url = selected.get('footer_url') or (url_for('static', filename=selected.get('footer')) if selected.get('footer') else None)
            header_height = selected.get('header_height_mm', 30)
            footer_height = selected.get('footer_height_mm', 30)
            header_width = selected.get('header_width_mm') if selected.get('header_width_mm') not in (None, '') else None
            footer_width = selected.get('footer_width_mm') if selected.get('footer_width_mm') not in (None, '') else None
            header_position = selected.get('header_position', 'right')
            footer_position = selected.get('footer_position', 'center')
            header_is_background = selected.get('header_is_background', True)
            footer_is_background = selected.get('footer_is_background', True)
            header_constrain = selected.get('header_constrain', True)
            footer_constrain = selected.get('footer_constrain', True)
            header_constrain = selected.get('header_constrain', True)
            footer_constrain = selected.get('footer_constrain', True)
    except Exception:
        pass

    is_return = request.args.get('is_return') in ('1', 'true', 'True')
    # Render HTML string with proper absolute base URL so static assets resolve
    try:
        html = render_template('inventory_admin/protocol.html', handover=handover, is_return=is_return, header_url=header_url, footer_url=footer_url, templates=templates,
                       header_height=header_height, footer_height=footer_height,
                       header_width=header_width, footer_width=footer_width,
                       header_position=header_position, footer_position=footer_position,
                       header_is_background=header_is_background, footer_is_background=footer_is_background,
                       header_constrain=header_constrain, footer_constrain=footer_constrain)

        # inject a <base> tag so relative static URLs resolve when Playwright renders
        if '<head>' in html:
            html = html.replace('<head>', f"<head><base href='{request.host_url}'>")

        # Compute PDF margins from template header/footer sizes so fixed
        # header/footer elements are not clipped. Apply a small safety offset
        # similar to the template's print-time offsets.
        try:
            def _mm(v, default):
                if v is None:
                    return float(default)
                return float(v)
            safety_top = 12.0
            safety_bottom = 8.0
            top_mm = max(_mm(header_height, 30.0) + safety_top, 20.0)
            bottom_mm = max(_mm(footer_height, 30.0) + safety_bottom, 20.0)
        except Exception:
            top_mm = 20.0
            bottom_mm = 20.0

        margins = {"top": f"{top_mm}mm", "bottom": f"{bottom_mm}mm", "left": "12mm", "right": "12mm"}
        try:
            pdf_bytes = generate_pdf_from_html_weasy(html, base_url=request.host_url, margins=margins)
        except RuntimeError as re:
            current_app.logger.error('WeasyPrint/runtime PDF error: %s', str(re))
            return (f"PDF generation error: {str(re)}", 500)

        return Response(pdf_bytes, mimetype='application/pdf', headers={"Content-Disposition": f"inline; filename=protocol-{handover_id}.pdf"})
    except Exception:
        current_app.logger.error('Playwright PDF generation failed:\n' + traceback.format_exc())
        return ("PDF generation failed on server (check logs).", 500)


@inventory_admin_bp.route('/handovers/<int:handover_id>/protocol_return')
@login_required
@require_permission('inventory_admin.access')
def protocol_return(handover_id):
    """Render a distinct return protocol view for a handover that has been returned.
    Provides a separate route so the printed/visible title and contents can differ
    and be saved/printed with a different meaning.
    """
    handover = Handover.query.get_or_404(handover_id)
    # legacy logo handling removed

    tpl_id = request.args.get('tpl_id')
    header_url = None
    footer_url = None
    templates = []
    try:
        templates = load_print_templates() or []
        selected = None
        if tpl_id:
            for t in templates:
                if t.get('id') == tpl_id:
                    selected = t
                    break
        if selected:
            header_url = selected.get('header_url') or (url_for('static', filename=selected.get('header')) if selected.get('header') else None)
            footer_url = selected.get('footer_url') or (url_for('static', filename=selected.get('footer')) if selected.get('footer') else None)
            header_height = selected.get('header_height_mm', 30)
            footer_height = selected.get('footer_height_mm', 30)
            header_width = selected.get('header_width_mm') if selected.get('header_width_mm') not in (None, '') else None
            footer_width = selected.get('footer_width_mm') if selected.get('footer_width_mm') not in (None, '') else None
            header_position = selected.get('header_position', 'right')
            footer_position = selected.get('footer_position', 'center')
            header_is_background = selected.get('header_is_background', True)
            footer_is_background = selected.get('footer_is_background', True)
    except Exception:
        header_url = None
        footer_url = None

    try:
        current_app.logger.info(f"protocol_return render handover_id={handover_id} tpl_id={tpl_id} header_height={locals().get('header_height')} footer_height={locals().get('footer_height')} header_width={locals().get('header_width')} footer_width={locals().get('footer_width')} header_pos={locals().get('header_position')} footer_pos={locals().get('footer_position')} header_url={header_url} footer_url={footer_url}")
    except Exception:
        pass
    return render_template('inventory_admin/protocol.html', handover=handover, is_return=True, header_url=header_url, footer_url=footer_url, templates=templates,
                           header_height=locals().get('header_height'), footer_height=locals().get('footer_height'),
                           header_width=locals().get('header_width'), footer_width=locals().get('footer_width'),
                           header_position=locals().get('header_position'), footer_position=locals().get('footer_position'),
                           header_is_background=locals().get('header_is_background'), footer_is_background=locals().get('footer_is_background'),
                           header_constrain=locals().get('header_constrain'), footer_constrain=locals().get('footer_constrain'))


@inventory_admin_bp.route('/<int:id>/delete', methods=['POST'])
@login_required
@require_permission('inventory_admin.edit')
@csrf.exempt
def delete_device(id):
    """Delete a device and its handovers. POST only.
    This endpoint is CSRF-exempt temporarily to avoid client-side token issues;
    consider removing @csrf.exempt after fixing client tokens.
    """
    device = Device.query.get_or_404(id)
    # delete related handovers first to satisfy foreign key constraints
    for h in device.handovers.all():
        db.session.delete(h)
    db.session.delete(device)
    db.session.commit()
    flash('Gerät wurde gelöscht.', 'success')
    return redirect(url_for('inventory_admin.index'))


@inventory_admin_bp.route('/<int:id>/mark_broken', methods=['POST'])
@login_required
@require_permission('inventory_admin.edit')
@csrf.exempt
def mark_broken(id):
    """Mark a device as broken/discarded."""
    device = Device.query.get_or_404(id)
    notes = request.form.get('discard_notes') or ''
    try:
        device.is_active = False
        device.discarded_at = _date.today()
        if notes:
            device.discarded_notes = (device.discarded_notes or '') + '\n' + notes
        db.session.commit()
        flash('Gerät als defekt markiert.', 'success')
    except Exception:
        current_app.logger.exception('Failed to mark device broken')
        flash('Fehler beim Markieren des Geräts.', 'danger')
    return redirect(url_for('inventory_admin.index'))


@inventory_admin_bp.route('/<int:id>/restore', methods=['POST'])
@login_required
@require_permission('inventory_admin.edit')
@csrf.exempt
def restore_device(id):
    """Restore a previously marked-as-broken device to available state."""
    device = Device.query.get_or_404(id)
    try:
        device.is_active = True
        device.discarded_at = None
        device.discarded_notes = None
        db.session.commit()
        flash('Gerät wieder verfügbar gemacht.', 'success')
    except Exception:
        current_app.logger.exception('Failed to restore device')
        flash('Fehler beim Wiederherstellen des Geräts.', 'danger')
    return redirect(url_for('inventory_admin.index'))
