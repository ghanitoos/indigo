"""
Base model for all database models.
"""
from datetime import datetime
from extensions import db


class BaseModel(db.Model):
    """
    Abstract base class for all database models.
    
    Provides common fields and functionality for all models.
    """
    __abstract__ = True
    
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow
    )
    
    def save(self) -> None:
        """Save the current instance to the database."""
        db.session.add(self)
        db.session.commit()
    
    def delete(self) -> None:
        """Delete the current instance from the database."""
        db.session.delete(self)
        db.session.commit()
    
    def update(self, **kwargs) -> None:
        """
        Update model attributes.
        
        Args:
            **kwargs: Key-value pairs of attributes to update
        """
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)
        self.save()
