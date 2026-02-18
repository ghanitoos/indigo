from flask import render_template, request, jsonify, redirect, url_for, flash
from . import welcome_bp
from auth.permissions import require_permission, require_role
from flask_login import login_required
from datetime import datetime

# Lightweight LDAP/user helper: try to reuse existing app's user model if available
try:
    from models.user import User
except Exception:
    User = None


@welcome_bp.route('/', methods=['GET'])
@login_required
@require_permission('welcome.access')
def new_welcome():
    # Render page; client-side will perform LDAP search via /welcome/lookup
    # Load available print templates from admin data if exposed via global template var
    return render_template('welcome/new.html')


@welcome_bp.route('/lookup', methods=['GET'])
@login_required
@require_permission('welcome.access')
def lookup_user():
    """Lookup a user by username via LDAP / user cache and return JSON.
    Query param: q (username)
    """
    q = request.args.get('q', '').strip()
    if not q:
        return jsonify({'error': 'missing query'}), 400

    # Try to find in User model first
    if User:
        u = User.query.filter((User.username == q) | (User.email == q)).first()
        if u:
            return jsonify({
                'username': u.username,
                'first_name': u.first_name,
                'last_name': u.last_name,
                'email': u.email,
            })

    # Fallback: minimal LDAP search if helper exists
    try:
        from auth.ldap_client import ldap_search_user
        res = ldap_search_user(q)
        if res:
            return jsonify(res)
    except Exception:
        pass

    return jsonify({'error': 'not found'}), 404


# Utility route to preview generated passwords (for testing)
@welcome_bp.route('/generate', methods=['POST'])
@login_required
@require_permission('welcome.access')
def generate():
    data = request.get_json() or {}
    username = data.get('username', '')
    firstname = data.get('first_name', '')
    lastname = data.get('last_name', '')
    # Apply generation rules
    pc_pass = generate_pc_password(username)
    email_pass = generate_email_password(firstname, lastname)
    cloud_pass = email_pass
    return jsonify({
        'pc_password': pc_pass,
        'email_password': email_pass,
        'cloud_password': cloud_pass,
    })


# Password generation helpers
MAP = {
    '2': 'qa',
    '3': 'wsyx',
    '4': 'edx',
    '5': 'rfc',
    '6': 'tgv',
    '7': 'zhb',
    '8': 'ujn',
    '9': 'ikm',
    '0': 'oplöäü'
}


def map_char_to_digit(ch):
    """Return the digit (as string) corresponding to a character using MAP.
    If a character matches multiple maps, choose the digit whose value list
    contains that character. If none, fallback to 8 (arbitrary).
    """
    c = ch.lower()
    for digit, chars in MAP.items():
        if c in chars:
            return digit
    # fallback: use 8
    return '8'


def generate_pc_password(username):
    """PC password format: =!WP:<2firstletters><mapped digits>%
    Example for username 'jthiede' -> =!WP:jt86%
    """
    base = '=!WP:'
    u = (username or '')
    first2 = (u[:2]) if len(u) >= 2 else u.ljust(2, 'x')
    # Map each char to digit
    d1 = map_char_to_digit(first2[0])
    d2 = map_char_to_digit(first2[1])
    return f"{base}{first2}{d1}{d2}%"


def generate_email_password(firstname, lastname):
    """Email password: 25+WP-<2firstFirst><2firstLast>-YY
    Example: Jonas Georg Thiede -> JoTh-26
    Uses current year (two-digit)
    """
    prefix = '25+WP-'
    a = (firstname or '')[:2].capitalize()
    b = (lastname or '')[:2].capitalize()
    yy = datetime.utcnow().year % 100
    return f"{prefix}{a}{b}-{yy:02d}"
