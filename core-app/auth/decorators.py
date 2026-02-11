"""
Authentication decorators for route protection.
"""
from functools import wraps
from flask import redirect, url_for, flash
from flask_login import current_user, login_required as flask_login_required


def login_required(func):
    """
    Decorator that requires user to be logged in.
    
    Args:
        func: Function to wrap
        
    Returns:
        Wrapped function that checks authentication
    """
    @wraps(func)
    @flask_login_required
    def decorated_view(*args, **kwargs):
        return func(*args, **kwargs)
    return decorated_view


def logout_required(func):
    """
    Decorator that requires user to be logged out.
    Redirects to dashboard if user is already authenticated.
    
    Args:
        func: Function to wrap
        
    Returns:
        Wrapped function that checks user is not authenticated
    """
    @wraps(func)
    def decorated_view(*args, **kwargs):
        if current_user.is_authenticated:
            return redirect(url_for('dashboard.index'))
        return func(*args, **kwargs)
    return decorated_view
