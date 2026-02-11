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
