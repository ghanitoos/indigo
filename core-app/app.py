import os
from flask import Flask, jsonify, redirect, url_for, Blueprint, render_template
from werkzeug.middleware.proxy_fix import ProxyFix
from flask_login import login_required, current_user
from config import get_config
from extensions import db, migrate, login_manager, csrf
from utils.translation import get_text
from utils.context_processors import inject_sidebar_menu
from modules.admin import admin_bp

# Import models to ensure they are registered with SQLAlchemy
from models.user import User
from models.rbac import Role, Module, Permission
from models.inventory import Device, PersonRef, Handover, InventorySettings

def create_app(config_name=None):
    app = Flask(__name__)
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)
    
    # Load config
    config = get_config(config_name)
    app.config.from_object(config)
    
    # Initialize extensions
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    csrf.init_app(app)
    
    # Configure Login Manager
    login_manager.login_view = 'auth.login'
    login_manager.login_message_category = 'error'
    
    # Import session manager to register user_loader
    import auth.session_manager
    
    # Register Blueprints
    from auth.routes import auth_bp
    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(admin_bp)

    from modules.profile import profile_bp
    from modules.inventory_admin import inventory_admin_bp
    from modules.my_devices import my_devices_bp
    app.register_blueprint(my_devices_bp)
    app.register_blueprint(inventory_admin_bp)
    app.register_blueprint(profile_bp, url_prefix='/profile')
    # Register welcome module if present
    try:
        from modules.welcome import welcome_bp
        app.register_blueprint(welcome_bp, url_prefix='/welcome')
    except Exception:
        pass
    
    # Main Blueprint (Placeholder for Dashboard)
    main_bp = Blueprint('main', __name__)
    
    @main_bp.route('/')
    @login_required
    def index():
        return render_template('base.html')

    @main_bp.route('/debug/session-info')
    @login_required
    def debug_session_info():
        # Return session and current user role info for debugging.
        try:
            from flask import jsonify, session
            user = current_user
            roles = [r.name for r in getattr(user, 'roles', [])]
            perms = []
            for r in getattr(user, 'roles', []):
                for p in getattr(r, 'permissions', []):
                    perms.append(p.name)
            return jsonify({
                'username': user.username,
                'display_name': user.display_name,
                'roles': roles,
                'permissions': sorted(list(set(perms))),
                'session_active_ldap_group': session.get('active_ldap_group'),
                'session_ldap_groups': session.get('ldap_groups')
            })
        except Exception as e:
            return jsonify({'error': str(e)}), 500
        
    app.register_blueprint(main_bp)
    
    # Context processors
    app.context_processor(inject_sidebar_menu)
    
    @app.context_processor
    def inject_helpers():
        return dict(get_text=get_text)
        
    # Health check
    @app.route('/health')
    def health():
        return jsonify({'status': 'healthy'})

    return app

app = create_app()

import click
from flask.cli import with_appcontext

@app.cli.command("init-rbac")
@with_appcontext
def init_rbac_command():
    """Initialize RBAC: sync modules and create default roles."""
    from utils.module_registry import ModuleRegistry
    
    print("Initializing RBAC...")
    # Sync Modules
    registry = ModuleRegistry(app)
    registry.sync_database()
    
    # Create Admin Role
    admin_role = Role.query.filter_by(name='admin').first()
    if not admin_role:
        admin_role = Role(name='admin', description='System Administrator', is_system=True)
        db.session.add(admin_role)
        db.session.commit()
        print("Created 'admin' role.")
    else:
        print("'admin' role exists.")
        
    print("RBAC Initialization complete.")

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
