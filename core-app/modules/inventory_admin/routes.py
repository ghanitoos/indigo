from flask import render_template, redirect, url_for, flash, request, jsonify, current_app, send_from_directory
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from models.inventory import Device, PersonRef, Handover, InventorySettings
from auth.ldap_connector import LDAPConnector
from auth.permissions import require_permission
from . import inventory_admin_bp
from .forms import DeviceForm, HandoverForm
from datetime import datetime
import os
from extensions import db

@inventory_admin_bp.route('/')
@login_required
@require_permission('inventory_admin.access')
def index():
    devices = Device.query.all()
    return render_template('inventory_admin/index.html', devices=devices)

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
def return_handover(handover_id):
    handover = Handover.query.get_or_404(handover_id)
    if request.method == 'POST':
        # record return
        rd = request.form.get('return_date')
        notes = request.form.get('notes', '')
        try:
            if rd:
                handover.return_date = datetime.strptime(rd, '%Y-%m-%d').date()
        except Exception:
            pass
        if notes:
            handover.notes = (handover.notes or '') + '\n\nReturn notes: ' + notes
        db.session.commit()
        flash('Rückgabe vermerkt.', 'success')
        return redirect(url_for('inventory_admin.protocol', handover_id=handover.id))

    return render_template('inventory_admin/return_handover.html', handover=handover)


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

    return render_template('inventory_admin/protocol.html', handover=handover, logo_url=logo_url)
