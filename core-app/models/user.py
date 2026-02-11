"""
User model implementation.
"""
from typing import Optional
from flask_login import UserMixin
from extensions import db
from models.base import BaseModel
# We use a string for secondary to avoid circular imports if possible,
# but since user_roles is a Table object, we need to import it or rely on registry.
# Using string 'user_roles' works if the table is in metadata.
# But let's import it to be explicit.
# Note: To avoid circular imports at module level, we might need to do this carefully.
# However, rbac.py does not import user.py. So user.py importing rbac.py is safe.

from models.rbac import Role, user_roles

class User(BaseModel, UserMixin):
    """
    User model for storing user information locally.
    
    Attributes:
        id (int): Primary key
        username (str): Unique username (from LDAP)
        display_name (str): Full name of the user
        email (str): Email address
        last_login (datetime): Last login timestamp
        is_active (bool): Whether the user account is active
    """
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False, index=True)
    display_name = db.Column(db.String(150), nullable=True)
    email = db.Column(db.String(150), nullable=True)
    last_login = db.Column(db.DateTime, nullable=True)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    
    # Relationships
    roles = db.relationship('Role', secondary=user_roles, lazy='subquery',
        backref=db.backref('users', lazy=True))
    
    def __repr__(self) -> str:
        return f'<User {self.username}>'
    
    def get_id(self) -> str:
        """Return the user ID as a string."""
        return str(self.id)
        
    @property
    def is_authenticated(self) -> bool:
        """Return True if the user is authenticated."""
        return True
        
    @property
    def is_anonymous(self) -> bool:
        """Return False as regular users are not anonymous."""
        return False

    def has_role(self, role_name: str) -> bool:
        """Check if user has a specific role."""
        return any(r.name == role_name for r in self.roles)

    def has_permission(self, permission_name: str) -> bool:
        """Check if user has a specific permission via any role."""
        for role in self.roles:
            for perm in role.permissions:
                if perm.name == permission_name:
                    return True
        return False
