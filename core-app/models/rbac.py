"""
RBAC models: Role, Module, Permission.
"""
from extensions import db
from models.base import BaseModel

# Association Tables
role_permissions = db.Table('role_permissions',
    db.Column('role_id', db.Integer, db.ForeignKey('roles.id'), primary_key=True),
    db.Column('permission_id', db.Integer, db.ForeignKey('permissions.id'), primary_key=True)
)

user_roles = db.Table('user_roles',
    db.Column('user_id', db.Integer, db.ForeignKey('users.id'), primary_key=True),
    db.Column('role_id', db.Integer, db.ForeignKey('roles.id'), primary_key=True)
)

class Role(BaseModel):
    """
    Role model for grouping permissions.
    Attributes:
        name: Unique role name (e.g., 'admin', 'user')
        description: Role description
        is_system: If True, cannot be deleted (e.g., 'admin')
    """
    __tablename__ = 'roles'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)
    description = db.Column(db.String(255))
    is_system = db.Column(db.Boolean, default=False)
    
    permissions = db.relationship('Permission', secondary=role_permissions, lazy='subquery',
        backref=db.backref('roles', lazy=True))

    def __repr__(self):
        return f'<Role {self.name}>'


    @classmethod
    def create_from_ldap_group(cls, ldap_group_cn):
        """
        Create or get role from LDAP group name.
        """
        role = cls.query.filter_by(name=ldap_group_cn).first()
        if not role:
            role = cls(
                name=ldap_group_cn,
                description=f"LDAP-Gruppe: {ldap_group_cn}",
                is_system=False
            )
            db.session.add(role)
            db.session.commit()
        return role

class Module(BaseModel):
    """
    Module model for dynamic module registration.
    Attributes:
        name: Internal module name
        display_name: Human readable name
        icon: FontAwesome icon class
        is_enabled: Toggle module availability
    """
    __tablename__ = 'modules'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)
    display_name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.String(255))
    icon = db.Column(db.String(50))
    is_enabled = db.Column(db.Boolean, default=True)
    url_prefix = db.Column(db.String(50))
    
    permissions = db.relationship('Permission', backref='module', lazy=True, cascade="all, delete-orphan")

    def __repr__(self):
        return f'<Module {self.name}>'

class Permission(BaseModel):
    """
    Permission model.
    Attributes:
        name: Unique permission string (e.g., 'user.create')
        module_id: Optional link to a module
    """
    __tablename__ = 'permissions'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    display_name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.String(255))
    module_id = db.Column(db.Integer, db.ForeignKey('modules.id'), nullable=True)

    def __repr__(self):
        return f'<Permission {self.name}>'
