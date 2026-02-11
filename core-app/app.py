import os
from flask import Flask, jsonify, redirect, url_for, Blueprint, render_template
from flask_login import login_required, current_user
from config import get_config
from extensions import db, migrate, login_manager, csrf
from utils.translation import get_text

# Import models to ensure they are registered with SQLAlchemy
from models.user import User

def create_app(config_name=None):
    app = Flask(__name__)
    
    # Load config
    config = get_config(config_name)
    app.config.from_object(config)
    
    # Initialize extensions
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    csrf.init_app(app)
    
    # Configure Login Manager
    login_manager.login_view = 'auth.login'
    login_manager.login_message_category = 'error'
    
    # Import session manager to register user_loader
    import auth.session_manager
    
    # Register Blueprints
    from auth.routes import auth_bp
    app.register_blueprint(auth_bp, url_prefix='/auth')
    
    # Main Blueprint (Placeholder for Dashboard)
    main_bp = Blueprint('main', __name__)
    
    @main_bp.route('/')
    @login_required
    def index():
        # Render a simple dashboard template or placeholder
        return render_template('base.html')
        
    app.register_blueprint(main_bp)
    
    # Context processors
    @app.context_processor
    def inject_helpers():
        return dict(get_text=get_text)
        
    # Health check
    @app.route('/health')
    def health():
        return jsonify({'status': 'healthy'})

    return app

app = create_app()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
