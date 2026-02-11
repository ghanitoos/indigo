"""
Authentication routes (login, logout).
"""
from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app
from flask_login import login_user, logout_user, login_required, current_user
from extensions import db
from models.user import User
from models.rbac import Role
from auth.ldap_connector import LDAPConnector
from auth.decorators import logout_required
from utils.translation import get_text

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    """
    Handle user login.
    
    GET: Render login form
    POST: Process login credentials
    """
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))

    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        if not username or not password:
            flash(get_text('messages.error_save'), 'danger')
            return render_template('auth/login.html')

        ldap = LDAPConnector()
        # Authenticate against LDAP
        if ldap.authenticate(username, password):
            # Auth success
            user_info = ldap.get_user_info(username)
            user = User.query.filter_by(username=username).first()
            
            if not user:
                user = User(username=username)
                db.session.add(user)
            
            # Update user details from LDAP
            if user_info:
                user.display_name = user_info.get('display_name')
                user.email = user_info.get('email')
                
                # Sync Roles based on Groups
                groups = user_info.get('groups', [])
                admin_role = Role.query.filter_by(name='admin').first()
                
                if admin_role:
                    if 'Domain Admins' in groups:
                        if admin_role not in user.roles:
                            user.roles.append(admin_role)
                            # flash('Admin access granted.', 'info')
                    # Optional: Remove admin role if removed from group?
                    # else:
                    #     if admin_role in user.roles:
                    #         user.roles.remove(admin_role)
            
            user.last_login = datetime.utcnow()
            user.is_active = True
            db.session.commit()
            
            login_user(user)
            flash(get_text('auth.login_success'), 'success')
            
            next_page = request.args.get('next')
            # Validate next_page to prevent open redirects if necessary
            return redirect(next_page or url_for('main.index'))
        else:
            flash(get_text('auth.login_failed'), 'danger')
    
    return render_template('auth/login.html')

@auth_bp.route('/logout')
@login_required
def logout():
    """Handle user logout."""
    logout_user()
    flash(get_text('auth.logout_success'), 'success')
    return redirect(url_for('auth.login'))
