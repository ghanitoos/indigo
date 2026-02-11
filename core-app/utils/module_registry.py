import os
import json
from extensions import db
from models.rbac import Module, Permission

class ModuleRegistry:
    def __init__(self, app=None):
        self.app = app
        if app:
            self.init_app(app)

    def init_app(self, app):
        self.app = app
        # We can add a CLI command here if needed
        pass

    def sync_database(self):
        """Sync discovered modules to database."""
        if not self.app:
            raise RuntimeError("ModuleRegistry not initialized with app")
            
        with self.app.app_context():
            modules_dir = os.path.join(self.app.root_path, 'modules')
            if not os.path.exists(modules_dir):
                print(f"Modules directory not found: {modules_dir}")
                return

            print(f"Scanning modules in {modules_dir}...")
            for module_name in os.listdir(modules_dir):
                module_path = os.path.join(modules_dir, module_name)
                if os.path.isdir(module_path) and not module_name.startswith('__'):
                    try:
                        self._sync_module_to_db(module_name, module_path)
                    except Exception as e:
                        print(f"Failed to sync module {module_name}: {e}")

    def _sync_module_to_db(self, module_name, module_path):
        config_file = os.path.join(module_path, 'config.json')
        metadata = {}
        
        if os.path.exists(config_file):
            try:
                with open(config_file, 'r') as f:
                    metadata = json.load(f)
            except Exception as e:
                print(f"Error reading config for {module_name}: {e}")
        
        # Defaults
        name = metadata.get('name', module_name)
        display_name = metadata.get('display_name', name.replace('_', ' ').title())
        
        # Upsert Module
        module = Module.query.filter_by(name=name).first()
        if not module:
            module = Module(name=name)
            print(f"Creating new module: {name}")
        
        module.display_name = display_name
        module.description = metadata.get('description', f'{display_name} module')
        module.icon = metadata.get('icon', 'fa-cube')
        module.url_prefix = metadata.get('url_prefix', f'/{name}')
        module.is_enabled = metadata.get('enabled', True)
        
        db.session.add(module)
        db.session.commit()
        
        # Sync Permissions
        defined_permissions = metadata.get('permissions', [])
        # Always ensure 'access' permission exists
        access_perm_name = f"{name}.access"
        if not any(p.get('name') == access_perm_name for p in defined_permissions):
            defined_permissions.insert(0, {
                'name': access_perm_name,
                'display_name': f'Access {display_name}',
                'description': f'Allow access to {display_name} module'
            })

        existing_perms = {p.name: p for p in module.permissions}
        current_perm_names = set()

        for perm_data in defined_permissions:
            perm_name = perm_data['name']
            current_perm_names.add(perm_name)
            
            if perm_name in existing_perms:
                perm = existing_perms[perm_name]
            else:
                perm = Permission(name=perm_name, module_id=module.id)
                db.session.add(perm)
                print(f"  + Permission: {perm_name}")
            
            perm.display_name = perm_data.get('display_name', perm_name)
            perm.description = perm_data.get('description', '')
            
        db.session.commit()
