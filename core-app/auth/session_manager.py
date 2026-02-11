"""
Session management integration with Flask-Login.
"""
from extensions import login_manager
from models.user import User

@login_manager.user_loader
def load_user(user_id):
    """
    Load user by ID.
    
    Args:
        user_id (str): User ID from session
        
    Returns:
        User: User instance or None
    """
    if user_id is not None:
        return User.query.get(int(user_id))
    return None
