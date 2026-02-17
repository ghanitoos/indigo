from flask import jsonify
from auth.ldap_connector import LDAPConnector
from flask import render_template, redirect, url_for, flash, request
from flask_login import login_required
from extensions import db
from models.rbac import Role, Permission, Module
from models.user import User
from auth.permissions import require_role, require_permission
from . import admin_bp
from .forms import RoleForm, UserRoleForm
import os, json
from werkzeug.utils import secure_filename
from flask_wtf.csrf import generate_csrf

UPLOAD_DIR = os.path.join(os.path.dirname(__file__), '..', '..', 'static', 'uploads', 'print_templates')
DATA_FILE = os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'print_templates.json')

def ensure_storage():
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    data_dir = os.path.dirname(DATA_FILE)
    os.makedirs(data_dir, exist_ok=True)

def load_print_templates():
    try:
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return {}

def save_print_templates(data):
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

@admin_bp.route('/')
@require_role('admin')
def index():
    return render_template('admin/index.html')

@admin_bp.route('/roles')
@require_permission('admin.roles.read')
def roles():
    roles = Role.query.all()
    return render_template('admin/roles.html', roles=roles)

@admin_bp.route('/roles/create', methods=['GET', 'POST'])
@require_permission('admin.roles.write')
def create_role():
    form = RoleForm()
    # Populate permissions
    form.permissions.choices = [(p.id, p.display_name or p.name) for p in Permission.query.order_by(Permission.name).all()]
    
    if form.validate_on_submit():
        role = Role(name=form.name.data, description=form.description.data)
        selected_perms = Permission.query.filter(Permission.id.in_(form.permissions.data)).all()
        role.permissions = selected_perms
        db.session.add(role)
        db.session.commit()
        flash('Role created successfully.', 'success')
        return redirect(url_for('admin.roles'))
        
    return render_template('admin/role_form.html', form=form, title='Create Role')

@admin_bp.route('/roles/<int:id>/edit', methods=['GET', 'POST'])
@require_permission('admin.roles.write')
def edit_role(id):
    role = Role.query.get_or_404(id)
    if role.is_system:
        flash('System roles cannot be edited.', 'warning')
        return redirect(url_for('admin.roles'))
        
    form = RoleForm(obj=role)
    form.permissions.choices = [(p.id, p.display_name or p.name) for p in Permission.query.order_by(Permission.name).all()]
    
    if request.method == 'GET':
        form.permissions.data = [p.id for p in role.permissions]
        
    if form.validate_on_submit():
        role.name = form.name.data
        role.description = form.description.data
        selected_perms = Permission.query.filter(Permission.id.in_(form.permissions.data)).all()
        role.permissions = selected_perms
        db.session.commit()
        flash('Role updated successfully.', 'success')
        return redirect(url_for('admin.roles'))
        
    return render_template('admin/role_form.html', form=form, title='Edit Role')

@admin_bp.route('/users')
@require_permission('admin.users.manage')
def users():
    users = User.query.all()
    return render_template('admin/users.html', users=users)

@admin_bp.route('/users/<int:id>/roles', methods=['GET', 'POST'])
@require_permission('admin.users.manage')
def manage_user_roles(id):
    user = User.query.get_or_404(id)
    form = UserRoleForm()
    form.roles.choices = [(r.id, r.name) for r in Role.query.all()]
    
    if request.method == 'GET':
        form.roles.data = [r.id for r in user.roles]
        
    if form.validate_on_submit():
        selected_roles = Role.query.filter(Role.id.in_(form.roles.data)).all()
        user.roles = selected_roles
        db.session.commit()
        flash(f'Roles updated for {user.username}.', 'success')
        return redirect(url_for('admin.users'))
        
    return render_template('admin/user_roles.html', form=form, user=user)

@admin_bp.route('/group-permissions')
@require_role('admin')
def group_permissions():
    """Show group permission management page."""
    ldap = LDAPConnector()
    ldap_groups = ldap.get_all_groups()
    
    local_roles = Role.query.all()
    modules = Module.query.order_by(Module.display_name).all()
    
    editable_roles = [r for r in local_roles if not r.is_system]
    
    return render_template('admin/group_permissions.html', 
                           ldap_groups=ldap_groups, 
                           roles=editable_roles,
                           modules=modules)

@admin_bp.route('/group-permissions/add', methods=['POST'])
@require_role('admin')
def add_group():
    """Add LDAP group to system."""
    group_cn = request.form.get('group_cn')
    if not group_cn:
        flash('Group name is required', 'danger')
        return redirect(url_for('admin.group_permissions'))
        
    role = Role.create_from_ldap_group(group_cn)
    flash(f'Group {role.name} added successfully.', 'success')
    return redirect(url_for('admin.group_permissions'))

@admin_bp.route('/group-permissions/update/<int:role_id>', methods=['POST'])
@require_role('admin')
def update_group_permissions(role_id):
    """Update module permissions for a role."""
    role = Role.query.get_or_404(role_id)
    if role.is_system:
        return jsonify({'status': 'error', 'message': 'Cannot modify system role'}), 403

    data = request.get_json()
    if not data:
         return jsonify({'status': 'error', 'message': 'Invalid data'}), 400
         
    module_names = data.get('modules', [])
    
    all_modules = Module.query.all()
    
    # Remove all access permissions first
    current_perms = list(role.permissions)
    new_perms = []
    
    access_perm_names = [f"{m.name}.access" for m in all_modules]
    
    for p in current_perms:
        if p.name not in access_perm_names:
            new_perms.append(p)
            
    # Add new access permissions
    for mod_name in module_names:
        perm_name = f"{mod_name}.access"
        perm = Permission.query.filter_by(name=perm_name).first()
        
        # Robustness check: if permission doesn't exist but module does, create it
        if not perm:
            module = Module.query.filter_by(name=mod_name).first()
            if module:
                perm = Permission(
                    name=perm_name,
                    display_name=f"Access {module.display_name}",
                    description=f"Access permission for {module.display_name}",
                    module_id=module.id
                )
                db.session.add(perm)
                # db.session.flush() # Not strictly needed as we just append the object
        
        if perm:
            new_perms.append(perm)
            
    role.permissions = new_perms
    db.session.commit()
    
    return jsonify({'status': 'success', 'message': 'Permissions updated'})

@admin_bp.route('/group-permissions/delete/<int:role_id>', methods=['POST'])
@require_role('admin')
def delete_group(role_id):
    """Delete a role/group."""
    role = Role.query.get_or_404(role_id)
    if role.is_system:
         return jsonify({'status': 'error', 'message': 'Cannot delete system role'}), 403
         
    db.session.delete(role)
    db.session.commit()
    return jsonify({'status': 'success', 'message': 'Group deleted'})


@admin_bp.route('/print-templates', methods=['GET', 'POST'])
@require_role('admin')
def print_templates():
    """Manage header/footer images used for printing."""
    ensure_storage()
    data = load_print_templates()

    if request.method == 'POST':
        header = request.files.get('header_image')
        footer = request.files.get('footer_image')
        notes = request.form.get('notes', '')

        updated = False
        if header and header.filename:
            filename = secure_filename(header.filename)
            target = os.path.join(UPLOAD_DIR, 'header_' + filename)
            header.save(target)
            data['header'] = os.path.relpath(target, os.path.join(os.path.dirname(__file__), '..', '..', 'static')).replace('\\', '/')
            updated = True

        if footer and footer.filename:
            filename = secure_filename(footer.filename)
            target = os.path.join(UPLOAD_DIR, 'footer_' + filename)
            footer.save(target)
            data['footer'] = os.path.relpath(target, os.path.join(os.path.dirname(__file__), '..', '..', 'static')).replace('\\', '/')
            updated = True

        data['notes'] = notes
        if updated or notes is not None:
            save_print_templates(data)
            flash('Print templates updated.', 'success')
        return redirect(url_for('admin.print_templates'))

    header_url = None
    footer_url = None
    notes = data.get('notes') if data else None
    if data.get('header'):
        header_url = url_for('static', filename=data['header'])
    if data.get('footer'):
        footer_url = url_for('static', filename=data['footer'])

    # Generate CSRF token for the form
    csrf_token = generate_csrf()

    return render_template('admin/print_templates.html', header_url=header_url, footer_url=footer_url, notes=notes, csrf_token=csrf_token)
