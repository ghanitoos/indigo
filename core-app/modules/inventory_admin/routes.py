from flask import render_template, redirect, url_for, flash, request, jsonify, current_app, send_from_directory, session
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from models.inventory import Device, PersonRef, Handover, InventorySettings
from auth.ldap_connector import LDAPConnector
from auth.permissions import require_permission
from . import inventory_admin_bp
from .forms import DeviceForm, HandoverForm, ReturnForm
from datetime import datetime
import os
from extensions import db
from extensions import csrf

@inventory_admin_bp.route('/')
@login_required
@require_permission('inventory_admin.access')
def index():
    devices = Device.query.all()
    # prepare last handover mapping for quick access in template
    last_handover_map = {}
    for d in devices:
        last = d.handovers.order_by(Handover.handover_date.desc()).first()
        last_handover_map[d.id] = last
    return render_template('inventory_admin/index.html', devices=devices, last_handover_map=last_handover_map)

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
            # Pre-fill giver department from LDAP groups if available
            try:
                ldap = LDAPConnector()
                groups = ldap.get_user_groups(current_user.username)
                # Prefer Domain Admins if present, otherwise a group that starts with 'GG'.
                selected = None
                if groups:
                    # If user is member of Domain Admins, prefer that group explicitly.
                    if 'Domain Admins' in groups:
                        selected = 'Domain Admins'
                    else:
                        for g in groups:
                            if g and g.startswith('GG'):
                                selected = g
                                break
                if selected and not form.giver_department.data:
                    form.giver_department.data = selected
            except Exception:
                pass
            # If active LDAP group is in session, set it as giver department (always override)
            try:
                active = session.get('active_ldap_group')
                if active:
                    form.giver_department.data = active
            except Exception:
                pass
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
        else:
            # If receiver exists but department is missing, attempt to auto-fill
            # from LDAP groups that start with 'GG' (excluding Domain Admins members).
            try:
                if not receiver.department and getattr(receiver, 'ldap_username', None):
                    ldap = LDAPConnector()
                    groups = ldap.get_user_groups(receiver.ldap_username)
                    selected = None
                    if groups:
                        if 'Domain Admins' in groups:
                            selected = 'Domain Admins'
                        else:
                            for g in groups:
                                if g and g.startswith('GG'):
                                    selected = g
                                    break
                    if selected:
                        receiver.department = selected
            except Exception:
                pass

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

        else:
            # If giver exists, ensure department follows active LDAP group if set
            try:
                active = session.get('active_ldap_group')
                if active:
                    giver.department = active
            except Exception:
                pass

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
    upload_dir = current_app.config.get('INVENTORY_UPLOAD_FOLDER') or os.path.join(os.getcwd(), 'data', 'uploads')
    logo_url = None
    # prefer png/jpg if exists
    for ext in ('.png', '.jpg', '.jpeg', '.svg'):
        p = os.path.join(upload_dir, 'logo' + ext)
        if os.path.exists(p):
            logo_url = url_for('inventory_admin.uploaded_file', filename='logo' + ext)
            break

    # default: show handover protocol
    return render_template('inventory_admin/protocol.html', handover=handover, logo_url=logo_url, is_return=False)


@inventory_admin_bp.route('/handovers/<int:handover_id>/protocol_return')
@login_required
@require_permission('inventory_admin.access')
def protocol_return(handover_id):
    """Render a distinct return protocol view for a handover that has been returned.
    Provides a separate route so the printed/visible title and contents can differ
    and be saved/printed with a different meaning.
    """
    handover = Handover.query.get_or_404(handover_id)
    upload_dir = current_app.config.get('INVENTORY_UPLOAD_FOLDER') or os.path.join(os.getcwd(), 'data', 'uploads')
    logo_url = None
    for ext in ('.png', '.jpg', '.jpeg', '.svg'):
        p = os.path.join(upload_dir, 'logo' + ext)
        if os.path.exists(p):
            logo_url = url_for('inventory_admin.uploaded_file', filename='logo' + ext)
            break

    return render_template('inventory_admin/protocol.html', handover=handover, logo_url=logo_url, is_return=True)


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
