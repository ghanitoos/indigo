import logging
import sys
from flask import Flask
from config import get_config
from ldap3 import Connection, Server, ALL, SIMPLE, Tls
import ssl

# Setup app context
app = Flask(__name__)
config = get_config('default')
app.config.from_object(config)

# Configure logging
logging.basicConfig(stream=sys.stdout, level=logging.DEBUG)

print("\n--- Starting Simple Bind Debug ---")
with app.app_context():
    ldap_server = app.config.get('LDAP_SERVER')
    bind_dn = app.config.get('LDAP_BIND_DN')
    bind_password = app.config.get('LDAP_BIND_PASSWORD')
    base_dn = app.config.get('LDAP_BASE_DN')
    
    print(f"LDAP Server: {ldap_server}")
    print(f"Bind DN: {bind_dn}")
    # print(f"Bind Password: {bind_password}") # Don't print password

    try:
        tls_conf = Tls(validate=ssl.CERT_NONE, version=ssl.PROTOCOL_TLSv1_2)
        server = Server(ldap_server, use_ssl=True, tls=tls_conf, get_info=ALL)
        
        # TRY SIMPLE BIND
        print("Attempting SIMPLE bind...")
        conn = Connection(server, user=bind_dn, password=bind_password, authentication=SIMPLE, auto_bind=True)
        print(f"SIMPLE Bind Successful: {conn}")
        
        search_filter = '(objectClass=group)'
        attributes = ['cn', 'distinguishedName', 'member']
        
        print(f"\nSearching with filter: {search_filter} in {base_dn}")
        conn.search(search_base=base_dn, search_filter=search_filter, attributes=attributes)
        
        print(f"Found {len(conn.entries)} entries.")
        for entry in conn.entries:
            print(f" - {entry.cn}")
            
    except Exception as e:
        print(f"\nERROR: {e}")

print("--- End Simple Bind Debug ---")
