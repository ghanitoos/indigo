"""
User model implementation.
"""
from typing import Optional
from flask_login import UserMixin
from extensions import db
from models.base import BaseModel


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
