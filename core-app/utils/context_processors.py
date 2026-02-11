from flask import url_for
from flask_login import current_user
from extensions import db
from models.rbac import Module

def inject_sidebar_menu():
    def get_sidebar_menu():
        if not current_user.is_authenticated:
            return []
            
        menu = []
        
        # Dashboard
        menu.append({
            'name': 'Dashboard',
            'url': url_for('main.index'),
            'icon': 'fa-tachometer-alt'
        })
        
        # Dynamic Modules
        # We wrap in try/except to avoid crashes if DB tables don't exist yet (e.g. during migration)
        try:
            modules = Module.query.filter_by(is_enabled=True).all()
            
            for mod in modules:
                # Check permission
                perm_name = f"{mod.name}.access"
                if current_user.has_role('admin') or current_user.has_permission(perm_name):
                    menu.append({
                        'name': mod.display_name,
                        'url': mod.url_prefix if mod.url_prefix else '#',
                        'icon': mod.icon
                    })
        except Exception:
            pass
            
        # Admin link
        if current_user.has_role('admin'):
            menu.append({
                'name': 'Administration',
                'url': url_for('admin.index'),
                'icon': 'fa-cogs'
            })
            
        return menu
        
    return dict(get_sidebar_menu=get_sidebar_menu)
