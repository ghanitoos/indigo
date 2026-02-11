from functools import wraps
from flask import abort, redirect, url_for, flash
from flask_login import current_user
# We don't import models here to avoid Circular Import if models import auth
# But we rely on current_user methods which are on the User model.

def require_role(role_name):
    """
    Decorator to restrict access to users with a specific role.
    
    Args:
        role_name (str): The name of the role required (e.g. 'admin')
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                return redirect(url_for('auth.login'))
            
            # Check if user has role or is admin
            if not current_user.has_role(role_name) and not current_user.has_role('admin'):
                flash('You do not have permission to access this resource.', 'danger')
                return redirect(url_for('main.index'))
                
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def require_permission(permission_name):
    """
    Decorator to restrict access to users with a specific permission.
    
    Args:
        permission_name (str): The name of the permission required (e.g. 'backup.read')
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                return redirect(url_for('auth.login'))
            
            # Admin role usually implies all permissions, or check explicitly
            if current_user.has_role('admin'):
                return f(*args, **kwargs)
                
            if not current_user.has_permission(permission_name):
                flash(f'Permission denied: {permission_name} required.', 'danger')
                return redirect(url_for('main.index'))
                
            return f(*args, **kwargs)
        return decorated_function
    return decorator
