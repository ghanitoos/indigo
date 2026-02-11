"""
Authentication routes (login, logout).
"""
from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app
from flask_login import login_user, logout_user, login_required
from extensions import db
from models.user import User
from auth.ldap_connector import LDAPConnector
from auth.decorators import logout_required
from utils.translation import get_text

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/login', methods=['GET', 'POST'])
@logout_required
def login():
    """
    Handle user login.
    
    GET: Render login form
    POST: Process login credentials
    """
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        if not username or not password:
            flash(get_text('messages.error_save'), 'error') # Using generic error or specific if available
            return render_template('auth/login.html')

        ldap = LDAPConnector()
        if ldap.authenticate(username, password):
            # Auth success, check if user exists locally
            user = User.query.filter_by(username=username).first()
            user_info = ldap.get_user_info(username)
            
            if not user:
                user = User(username=username)
                db.session.add(user)
            
            # Update user details from LDAP
            if user_info:
                user.display_name = user_info.get('display_name')
                user.email = user_info.get('email')
            
            user.last_login = datetime.utcnow()
            user.is_active = True
            db.session.commit()
            
            login_user(user)
            flash(get_text('auth.login_success'), 'success')
            
            # Redirect to next page or default
            next_page = request.args.get('next')
            # Security check for next_page to prevent open redirect would go here
            
            return redirect(next_page or url_for('main.index'))
        else:
            flash(get_text('auth.login_failed'), 'error')
    
    return render_template('auth/login.html')

@auth_bp.route('/logout')
@login_required
def logout():
    """Handle user logout."""
    logout_user()
    flash(get_text('auth.logout_success'), 'success')
    return redirect(url_for('auth.login'))
