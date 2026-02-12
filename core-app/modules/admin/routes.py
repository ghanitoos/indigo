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
