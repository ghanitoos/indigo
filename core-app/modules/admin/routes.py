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
import os, json, re
from werkzeug.utils import secure_filename
import uuid
from datetime import datetime
from flask_wtf.csrf import generate_csrf

UPLOAD_DIR = os.path.join(os.path.dirname(__file__), '..', '..', 'static', 'uploads', 'print_templates')
DATA_FILE = os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'print_templates.json')

def ensure_storage():
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    data_dir = os.path.dirname(DATA_FILE)
    os.makedirs(data_dir, exist_ok=True)


def parse_mm(value, default=30):
    """Parse a user-supplied mm value. Accepts numbers like '5', '5.0', '5mm' or other text —
    extracts the first numeric token. Returns int if whole number else float.
    """
    if value is None:
        return default
    try:
        s = str(value).strip()
        m = re.search(r'[-+]?[0-9]*\.?[0-9]+', s)
        if not m:
            return default
        num = float(m.group(0))
        if num.is_integer():
            return int(num)
        return float(num)
    except Exception:
        return default

def load_print_templates():
    """Return a list of print templates. Maintain backwards compatibility with
    legacy dict format by converting it into a single-item list.
    """
    try:
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            # If data is a dict with header/footer keys, migrate to list
            if isinstance(data, dict):
                if 'header' in data or 'footer' in data:
                    # create a single template entry
                    tpl = {
                        'id': uuid.uuid4().hex,
                        'name': data.get('name') or 'default',
                        'header': data.get('header'),
                        'footer': data.get('footer'),
                        'notes': data.get('notes'),
                        'created': data.get('created') or datetime.utcnow().isoformat()
                    }
                    return [tpl]
                # else assume it's already a mapping of id->template; convert
                try:
                    # dict of id->template
                    return [v for k, v in data.items()]
                except Exception:
                    return []
            if isinstance(data, list):
                # ensure new fields exist with sensible defaults
                for t in data:
                    if 'header_height_mm' not in t:
                        t['header_height_mm'] = 30
                    if 'footer_height_mm' not in t:
                        t['footer_height_mm'] = 30
                    if 'header_width_mm' not in t:
                        t['header_width_mm'] = None
                    if 'footer_width_mm' not in t:
                        t['footer_width_mm'] = None
                    if 'header_position' not in t:
                        t['header_position'] = 'right'
                    if 'footer_position' not in t:
                        t['footer_position'] = 'center'
                    if 'header_is_background' not in t:
                        t['header_is_background'] = True
                    if 'footer_is_background' not in t:
                        t['footer_is_background'] = True
                    if 'header_offset_x_mm' not in t:
                        t['header_offset_x_mm'] = 0
                    if 'header_offset_y_mm' not in t:
                        t['header_offset_y_mm'] = 0
                    if 'footer_offset_x_mm' not in t:
                        t['footer_offset_x_mm'] = 0
                    if 'footer_offset_y_mm' not in t:
                        t['footer_offset_y_mm'] = 0
                return data
            return []
    except Exception:
        return []

def save_print_templates(data):
    # expect `data` to be a list of templates; write to file
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
    templates = load_print_templates()

    if request.method == 'POST':
        # Support creating a new named template
        name = request.form.get('name', '').strip() or f"template-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
        header = request.files.get('header_image')
        footer = request.files.get('footer_image')
        notes = request.form.get('notes', '')
        # optional size/position fields for new template
        header_height_mm = parse_mm(request.form.get('header_height_mm'), 30)
        footer_height_mm = parse_mm(request.form.get('footer_height_mm'), 30)
        header_width_mm = parse_mm(request.form.get('header_width_mm'), None)
        footer_width_mm = parse_mm(request.form.get('footer_width_mm'), None)
        header_position = request.form.get('header_position') or 'right'
        footer_position = request.form.get('footer_position') or 'center'
        header_is_background = bool(request.form.get('header_is_background'))
        footer_is_background = bool(request.form.get('footer_is_background'))

        tpl_id = uuid.uuid4().hex
        tpl = {
            'id': tpl_id,
            'name': name,
            'header': None,
            'footer': None,
            'header_height_mm': header_height_mm,
            'footer_height_mm': footer_height_mm,
            'header_width_mm': header_width_mm,
            'footer_width_mm': footer_width_mm,
            'header_offset_x_mm': parse_mm(request.form.get('header_offset_x_mm'), 0),
            'header_offset_y_mm': parse_mm(request.form.get('header_offset_y_mm'), 0),
            'footer_offset_x_mm': parse_mm(request.form.get('footer_offset_x_mm'), 0),
            'footer_offset_y_mm': parse_mm(request.form.get('footer_offset_y_mm'), 0),
            'header_position': header_position,
            'footer_position': footer_position,
            'header_is_background': header_is_background,
            'footer_is_background': footer_is_background,
                    'header_constrain': bool(request.form.get('header_constrain')),
                    'footer_constrain': bool(request.form.get('footer_constrain')),
            'notes': notes,
            'created': datetime.utcnow().isoformat()
        }

        saved = False
        if header and header.filename:
            filename = secure_filename(header.filename)
            target = os.path.join(UPLOAD_DIR, f"{tpl_id}_header_{filename}")
            header.save(target)
            tpl['header'] = os.path.relpath(target, os.path.join(os.path.dirname(__file__), '..', '..', 'static')).replace('\\', '/')
            saved = True

        if footer and footer.filename:
            filename = secure_filename(footer.filename)
            target = os.path.join(UPLOAD_DIR, f"{tpl_id}_footer_{filename}")
            footer.save(target)
            tpl['footer'] = os.path.relpath(target, os.path.join(os.path.dirname(__file__), '..', '..', 'static')).replace('\\', '/')
            saved = True

        # Only add template if at least one file or a name/notes provided
        if saved or tpl['name'] or tpl['notes']:
            templates.append(tpl)
            save_print_templates(templates)
            flash('Print template added.', 'success')

        return redirect(url_for('admin.print_templates'))

    # Build URLs for templates
    for t in templates:
        if t.get('header'):
            t['header_url'] = url_for('static', filename=t['header'])
        else:
            t['header_url'] = None
        if t.get('footer'):
            t['footer_url'] = url_for('static', filename=t['footer'])
        else:
            t['footer_url'] = None
        # Ensure new boolean fields exist with sensible defaults
        if 'header_constrain' not in t:
            t['header_constrain'] = True
        if 'footer_constrain' not in t:
            t['footer_constrain'] = True

    # Generate CSRF token for the form
    csrf_token = generate_csrf()
    # prevent aggressive caching which could make updated templates appear stale
    from flask import make_response
    resp = make_response(render_template('admin/print_templates.html', templates=templates, csrf_token=csrf_token))
    resp.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    return resp


@admin_bp.route('/print-templates/delete/<template_id>', methods=['POST'])
@require_role('admin')
def delete_print_template(template_id):
    ensure_storage()
    templates = load_print_templates()
    remaining = [t for t in templates if t.get('id') != template_id]
    if len(remaining) == len(templates):
        return jsonify({'status': 'error', 'message': 'Template not found'}), 404

    # Optionally remove files from disk
    for t in templates:
        if t.get('id') == template_id:
            for key in ('header', 'footer'):
                p = t.get(key)
                if p:
                    path = os.path.join(os.path.dirname(__file__), '..', '..', 'static', p)
                    try:
                        if os.path.exists(path):
                            os.remove(path)
                    except Exception:
                        pass
            break

    save_print_templates(remaining)
    flash('Print template deleted.', 'success')
    return redirect(url_for('admin.print_templates'))


@admin_bp.route('/print-templates/update/<template_id>', methods=['POST'])
@require_role('admin')
def update_print_template(template_id):
    """Update settings or images for an existing print template."""
    ensure_storage()
    templates = load_print_templates()
    tpl = None
    for t in templates:
        if t.get('id') == template_id:
            tpl = t
            break
    if not tpl:
        flash('Template not found.', 'danger')
        return redirect(url_for('admin.print_templates'))

    # Update numeric and option fields
    # parse and accept user-typed mm values (e.g. '5', '5mm', '5.5')
    tpl['header_height_mm'] = parse_mm(request.form.get('header_height_mm') or tpl.get('header_height_mm'), tpl.get('header_height_mm') or 30)
    tpl['footer_height_mm'] = parse_mm(request.form.get('footer_height_mm') or tpl.get('footer_height_mm'), tpl.get('footer_height_mm') or 30)
    # accept optional width values (mm). None means use default full-bleed behavior
    tpl['header_width_mm'] = parse_mm(request.form.get('header_width_mm') or tpl.get('header_width_mm'), tpl.get('header_width_mm'))
    tpl['footer_width_mm'] = parse_mm(request.form.get('footer_width_mm') or tpl.get('footer_width_mm'), tpl.get('footer_width_mm'))
    # offsets (mm) for fine positioning via admin UI
    tpl['header_offset_x_mm'] = parse_mm(request.form.get('header_offset_x_mm') or tpl.get('header_offset_x_mm'), tpl.get('header_offset_x_mm') or 0)
    tpl['header_offset_y_mm'] = parse_mm(request.form.get('header_offset_y_mm') or tpl.get('header_offset_y_mm'), tpl.get('header_offset_y_mm') or 0)
    tpl['footer_offset_x_mm'] = parse_mm(request.form.get('footer_offset_x_mm') or tpl.get('footer_offset_x_mm'), tpl.get('footer_offset_x_mm') or 0)
    tpl['footer_offset_y_mm'] = parse_mm(request.form.get('footer_offset_y_mm') or tpl.get('footer_offset_y_mm'), tpl.get('footer_offset_y_mm') or 0)
    tpl['header_position'] = request.form.get('header_position') or tpl.get('header_position') or 'right'
    tpl['footer_position'] = request.form.get('footer_position') or tpl.get('footer_position') or 'center'
    tpl['header_is_background'] = bool(request.form.get('header_is_background'))
    tpl['footer_is_background'] = bool(request.form.get('footer_is_background'))
    # optional: constrain header/footer to printable content width (prevent bleed)
    tpl['header_constrain'] = bool(request.form.get('header_constrain'))
    tpl['footer_constrain'] = bool(request.form.get('footer_constrain'))
    tpl['name'] = request.form.get('name') or tpl.get('name')
    tpl['notes'] = request.form.get('notes') or tpl.get('notes')

    # Allow replacing header/footer images
    header = request.files.get('header_image')
    footer = request.files.get('footer_image')
    if header and header.filename:
        filename = secure_filename(header.filename)
        target = os.path.join(UPLOAD_DIR, f"{template_id}_header_{filename}")
        header.save(target)
        tpl['header'] = os.path.relpath(target, os.path.join(os.path.dirname(__file__), '..', '..', 'static')).replace('\\', '/')
    if footer and footer.filename:
        filename = secure_filename(footer.filename)
        target = os.path.join(UPLOAD_DIR, f"{template_id}_footer_{filename}")
        footer.save(target)
        tpl['footer'] = os.path.relpath(target, os.path.join(os.path.dirname(__file__), '..', '..', 'static')).replace('\\', '/')

    save_print_templates(templates)
    flash('Print template updated.', 'success')
    return redirect(url_for('admin.print_templates'))
