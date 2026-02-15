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

                # Sync Roles based on LDAP Groups
                # Map any LDAP group that has a corresponding local Role record
                # to the user so group-based permissions (managed in admin UI)
                # are applied automatically on login.
                groups = user_info.get('groups', [])

                if groups:
                    # Find matching local roles by exact name (Role.name == group CN)
                    group_roles = Role.query.filter(Role.name.in_(groups)).all()
                    for gr in group_roles:
                        if gr not in user.roles:
                            user.roles.append(gr)

                # Ensure a PersonRef exists for this LDAP user so my-devices works
                try:
                    from models.inventory import PersonRef
                    if user.username:
                        person = PersonRef.query.filter_by(ldap_username=user.username).first()
                        if not person:
                            # attempt to split display_name to first/last
                            first=''; last=''
                            if user.display_name:
                                parts=user.display_name.split(' ',1)
                                first=parts[0]
                                last=parts[1] if len(parts)>1 else ''
                            person = PersonRef(ldap_username=user.username, first_name=first or user.username, last_name=last or '')
                            db.session.add(person)
                except Exception:
                    pass

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
