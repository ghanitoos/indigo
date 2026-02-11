"""
User model implementation.
"""
from typing import Optional
from datetime import datetime
from flask_login import UserMixin
from extensions import db
from models.base import BaseModel
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
        profile_photo (str): Filename of profile photo
        phone (str): Phone number
        bio (str): Short biography
        department (str): Department/Unit
        updated_at (datetime): Last update timestamp
    """
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False, index=True)
    display_name = db.Column(db.String(150), nullable=True)
    email = db.Column(db.String(150), nullable=True)
    last_login = db.Column(db.DateTime, nullable=True)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    
    # New fields
    profile_photo = db.Column(db.String(255), nullable=True)
    phone = db.Column(db.String(50), nullable=True)
    bio = db.Column(db.Text, nullable=True)
    department = db.Column(db.String(100), nullable=True)
    updated_at = db.Column(db.DateTime, nullable=True)
    
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

    def get_profile_photo_url(self) -> Optional[str]:
        """Return URL of profile photo."""
        if self.profile_photo:
            return f'/profile/photo/{self.id}'
        return None

    def update_profile(self, data: dict):
        """Update profile information."""
        allowed_fields = ['display_name', 'email', 'phone', 'bio', 'department']
        for key, value in data.items():
            if key in allowed_fields and hasattr(self, key):
                setattr(self, key, value)
        self.updated_at = datetime.utcnow()
        db.session.commit()

    def delete_profile_photo(self):
        """Remove profile photo database reference."""
        self.profile_photo = None
        self.updated_at = datetime.utcnow()
        db.session.commit()
