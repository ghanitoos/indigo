"""
Configuration module for Indigo Admin Panel.
Loads settings from environment variables and provides configuration classes.
"""
import os
from typing import Optional
from decouple import config


class Config:
    """Base configuration class with common settings."""
    
    # Flask settings
    SECRET_KEY: str = config('SECRET_KEY', default='dev-secret-key-change-in-production')
    FLASK_ENV: str = config('FLASK_ENV', default='development')
    DEBUG: bool = config('DEBUG', default=False, cast=bool)
    
    # Database settings
    DATABASE_URL: str = config(
        'DATABASE_URL',
        default='postgresql://adminuser:changeme_secure_password@postgres:5432/adminpanel'
    )
    SQLALCHEMY_DATABASE_URI: str = DATABASE_URL
    SQLALCHEMY_TRACK_MODIFICATIONS: bool = False
    SQLALCHEMY_ECHO: bool = config('SQLALCHEMY_ECHO', default=False, cast=bool)
    
    # LDAP settings
    LDAP_SERVER: str = config('LDAP_SERVER', default='ldap://samba-dc:389')
    LDAP_BIND_DN: str = config('LDAP_BIND_DN', default='')
    LDAP_BIND_PASSWORD: str = config('LDAP_BIND_PASSWORD', default='')
    LDAP_BASE_DN: str = config('LDAP_BASE_DN', default='dc=school,dc=local')
    LDAP_USER_SEARCH_BASE: str = config('LDAP_USER_SEARCH_BASE', default='cn=Users')
    LDAP_GROUP_SEARCH_BASE: str = config('LDAP_GROUP_SEARCH_BASE', default='cn=Groups')
    
    # Session settings
    SESSION_COOKIE_NAME: str = 'indigo_session'
    SESSION_COOKIE_HTTPONLY: bool = True
    SESSION_COOKIE_SECURE: bool = config('SESSION_COOKIE_SECURE', default=False, cast=bool)
    PERMANENT_SESSION_LIFETIME: int = config('SESSION_LIFETIME', default=1800, cast=int)  # 30 minutes
    
    # Security settings
    WTF_CSRF_ENABLED: bool = True
    WTF_CSRF_TIME_LIMIT: Optional[int] = None
    
    # Application settings
    APP_NAME: str = 'Indigo Admin Panel'
    APP_VERSION: str = '1.0.0'
    DEFAULT_LANGUAGE: str = 'de'
    SUPPORTED_LANGUAGES: list = ['de', 'en']
    
    # Logging settings
    LOG_LEVEL: str = config('LOG_LEVEL', default='INFO')
    LOG_FILE: str = config('LOG_FILE', default='/app/logs/app.log')
    
    # Module settings
    ENABLED_MODULES: list = config(
        'ENABLED_MODULES',
        default='dashboard,users,pfsense,fileserver,backup,fog',
        cast=lambda x: [m.strip() for m in x.split(',')]
    )


class DevelopmentConfig(Config):
    """Development environment configuration."""
    
    DEBUG: bool = True
    FLASK_ENV: str = 'development'
    SQLALCHEMY_ECHO: bool = True


class ProductionConfig(Config):
    """Production environment configuration."""
    
    DEBUG: bool = False
    FLASK_ENV: str = 'production'
    # Allow overriding secure cookie in production (e.g. for HTTP-only internal networks)
    SESSION_COOKIE_SECURE: bool = config('SESSION_COOKIE_SECURE', default=True, cast=bool)
    
    # Override secret key requirement
    SECRET_KEY: str = config('SECRET_KEY')  # Must be set in production


class TestingConfig(Config):
    """Testing environment configuration."""
    
    TESTING: bool = True
    DEBUG: bool = True
    SQLALCHEMY_DATABASE_URI: str = 'sqlite:///:memory:'
    WTF_CSRF_ENABLED: bool = False


# Configuration dictionary
config_by_name = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig
}


def get_config(config_name: Optional[str] = None) -> Config:
    """
    Get configuration object based on environment name.
    
    Args:
        config_name: Name of configuration (development, production, testing)
        
    Returns:
        Configuration object instance
    """
    if config_name is None:
        config_name = os.getenv('FLASK_ENV', 'development')
    
    return config_by_name.get(config_name, DevelopmentConfig)()
