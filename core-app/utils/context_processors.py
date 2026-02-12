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
            
            # Sort by display name or other logic if needed?
            # User snippet: order_by(Module.order) - but Module model might not have order field?
            # Let's sort by name for now.
            valid_modules.sort(key=lambda x: x.display_name)

            for mod in valid_modules:
                # Skip if module is 'admin' and handled manually? 
                # Wait, user wants duplicates GONE.
                # If 'admin' is in DB, it will be added here.
                # If we remove manual 'admin', then this is fine.
                
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
            
        # We removed manual Administration entry to avoid duplication with DB entry.
        # But if 'admin' module is NOT in DB, we lose it.
        # But 'admin' IS in DB (id 1).
            
        return menu
        
    return dict(get_sidebar_menu=get_sidebar_menu)
