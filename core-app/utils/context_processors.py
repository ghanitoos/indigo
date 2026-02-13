import os
from flask import current_app, url_for
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
        
        def module_exists(name):
            """Check if module directory has config.json"""
            module_path = os.path.join(current_app.root_path, 'modules', name)
            config_file = os.path.join(module_path, 'config.json')
            return os.path.exists(config_file)

        # Dynamic Modules
        try:
            modules = Module.query.filter_by(is_enabled=True).all()
            
            # Filter valid modules
            valid_modules = [m for m in modules if module_exists(m.name)]
            
            valid_modules.sort(key=lambda x: x.display_name)

            for mod in valid_modules:
                # Check permission
                perm_name = f"{mod.name}.access"
                if current_user.has_role('admin') or current_user.has_permission(perm_name):
                    # FIX: Use url_for if module is 'admin' or others to ensure relative path is correct.
                    # Or assume url_prefix is relative and safe.
                    # If mod.url_prefix is '/admin', it works.
                    # But if 'Administration' is broken, let's debug.
                    
                    if mod.name == 'admin':
                        # Force correct URL for admin module
                        try:
                            url = url_for('admin.index')
                        except:
                            url = mod.url_prefix or '#'
                    else:
                        url = mod.url_prefix if mod.url_prefix else '#'
                        
                    menu.append({
                        'name': mod.display_name,
                        'url': url,
                        'icon': mod.icon
                    })
        except Exception:
            pass
            
        return menu
        
    return dict(get_sidebar_menu=get_sidebar_menu)
