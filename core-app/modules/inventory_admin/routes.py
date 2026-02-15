from flask import render_template, redirect, url_for, flash, request, jsonify, current_app
from flask_login import login_required, current_user
from extensions import db
from models.inventory import Device, PersonRef, Handover
from auth.ldap_connector import LDAPConnector
from auth.permissions import require_permission
from . import inventory_admin_bp
from .forms import DeviceForm, HandoverForm
from datetime import datetime

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
        device = Device(
            inventory_number=form.inventory_number.data,
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
        # Optional: pre-fill giver if we can identify them from LDAP
        ldap = LDAPConnector()
        # We might add current user info fetch here if needed

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
        return redirect(url_for('inventory_admin.index'))

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
