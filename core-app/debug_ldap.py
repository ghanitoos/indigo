from flask import Flask
from config import get_config
from auth.ldap_connector import LDAPConnector
import logging

# Setup basic app context
app = Flask(__name__)
config = get_config('default')
app.config.from_object(config)

# Configure logging
logging.basicConfig(level=logging.DEBUG)

with app.app_context():
    print("--- Starting LDAP Debug ---")
    ldap = LDAPConnector()
    print(f"LDAP Server: {app.config.get('LDAP_SERVER')}")
    print(f"Base DN: {app.config.get('LDAP_BASE_DN')}")
    
    try:
        groups = ldap.get_all_groups()
        print(f"Found {len(groups)} groups.")
        for g in groups:
            print(f" - {g['cn']} (Members: {g['member_count']})")
    except Exception as e:
        print(f"Error: {e}")
    print("--- End LDAP Debug ---")
