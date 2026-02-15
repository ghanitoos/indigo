from app import create_app
app = create_app()
with app.app_context():
    from models.user import User
    from models.rbac import Role, Module
    from extensions import db

    u = User.query.filter_by(username='pfldap').first()
    print('User before:', u)
    if not u:
        u = User(username='pfldap')
        db.session.add(u)
        db.session.commit()
        print('Created user pfldap')

    role = Role.query.filter_by(name='GG-Alle-Mitarbeiter').first()
    print('Role found:', role)
    if role:
        print('Role perms:', [p.name for p in role.permissions])
        if role not in u.roles:
            u.roles.append(role)
            db.session.commit()
            print('Role assigned to user')
        else:
            print('User already has role')
    else:
        print('Role GG-Alle-Mitarbeiter not found')

    print('All modules:')
    for m in Module.query.order_by(Module.display_name).all():
        print(' -', m.name, m.url_prefix)
