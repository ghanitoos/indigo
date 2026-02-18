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


def _user_to_dict(u):
    if not u:
        return None
    first = getattr(u, 'first_name', None) or getattr(u, 'given_name', None) or getattr(u, 'firstname', None) or getattr(u, 'name', None) or ''
    last = getattr(u, 'last_name', None) or getattr(u, 'sn', None) or getattr(u, 'lastname', None) or ''
    email = getattr(u, 'email', None) or getattr(u, 'mail', None) or ''
    username = getattr(u, 'username', None) or getattr(u, 'uid', None) or (email.split('@')[0] if email else '')
    # If display_name exists and first/last not present, try to split it
    if not first and not last:
        disp = getattr(u, 'display_name', None) or getattr(u, 'displayName', None) or None
        if disp:
            parts = disp.split()
            if len(parts) >= 2:
                first = parts[0]
                last = ' '.join(parts[1:])
            elif len(parts) == 1:
                first = parts[0]
    return {
        'username': username,
        'first_name': first,
        'last_name': last,
        'email': email,
    }


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
            ud = _user_to_dict(u)
            if ud:
                return jsonify(ud)

    # Fallback: minimal LDAP search if helper exists
    try:
        from auth.ldap_connector import LDAPConnector
        ldap = LDAPConnector()
        info = ldap.get_user_info(q)
        if info:
            # normalize keys to match expected structure
            return jsonify({
                'username': info.get('username') or info.get('ldap_username') or q,
                'first_name': info.get('first_name') or info.get('display_name','').split(' ')[0] if info.get('display_name') else '',
                'last_name': info.get('last_name') or ' '.join(info.get('display_name','').split(' ')[1:]) if info.get('display_name') else '',
                'email': info.get('email') or ''
            })
    except Exception:
        pass

    return jsonify({'error': 'not found'}), 404


@welcome_bp.route('/search', methods=['GET'])
@login_required
@require_permission('welcome.access')
def search_users():
    """Return a list of user suggestions matching the query prefix.
    Query param: q (partial username/email)
    Returns: JSON array of {username, first_name, last_name, email}
    """
    q = request.args.get('q', '').strip()
    if not q or len(q) < 1:
        return jsonify([])

    results = []
    # Try DB model prefix search
    if User:
        # Use ilike for case-insensitive startswith
        try:
            users = User.query.filter((User.username.ilike(f"{q}%")) | (User.email.ilike(f"{q}%"))).limit(20).all()
            for u in users:
                ud = _user_to_dict(u)
                if ud:
                    results.append(ud)
        except Exception:
            # Fall through to LDAP fallback
            results = []

    # If no DB results, try LDAP helper which may return multiple matches
    if not results:
        try:
            from auth.ldap_connector import LDAPConnector
            ldap = LDAPConnector()
            ldap_res = ldap.search_users(q)
            for r in ldap_res:
                uname = r.get('ldap_username') or r.get('username') or ''
                # try to enrich with email by calling get_user_info
                email = ''
                try:
                    info = ldap.get_user_info(uname) if uname else None
                    if info:
                        email = info.get('email') or ''
                except Exception:
                    email = ''

                results.append({
                    'username': uname,
                    'first_name': r.get('first_name') or r.get('display_name', '').split(' ')[0] or '',
                    'last_name': r.get('last_name') or ' '.join(r.get('display_name', '').split(' ')[1:]) or '',
                    'email': email
                })
        except Exception:
            pass

    return jsonify(results)


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
