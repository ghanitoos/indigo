"""
LDAP Connector for Active Directory authentication and user management.
"""
import logging
import ssl
from typing import Optional, Dict, List, Any
from ldap3 import Server, Connection, ALL, SUBTREE, NTLM, Tls
from ldap3.core.exceptions import LDAPException
from flask import current_app

logger = logging.getLogger(__name__)


class LDAPConnector:
    """
    Connector for interacting with Samba AD DC via LDAP (Secure).
    """
    
    def __init__(self):
        """Initialize LDAP connection parameters from config."""
        self.server_uri = current_app.config.get('LDAP_SERVER')
        self.bind_dn = current_app.config.get('LDAP_BIND_DN')
        self.bind_password = current_app.config.get('LDAP_BIND_PASSWORD')
        self.base_dn = current_app.config.get('LDAP_BASE_DN')
        self.user_search_base = current_app.config.get('LDAP_USER_SEARCH_BASE')
        self.group_search_base = current_app.config.get('LDAP_GROUP_SEARCH_BASE')
        self.is_dev = current_app.config.get('FLASK_ENV') == 'development'

    def authenticate(self, username, password) -> bool:
        """
        Authenticate a user against the LDAP server.
        """
        if self.is_dev and username == 'admin' and password == 'admin':
            logger.info("Authenticated using Demo Mode (admin/admin)")
            return True

        if not username or not password:
            return False

        try:
            # Configure TLS to accept self-signed certificates
            tls_config = Tls(validate=ssl.CERT_NONE, version=ssl.PROTOCOL_TLSv1_2)
            
            # Use use_ssl=True if connecting to port 636 (ldaps://)
            # If server_uri starts with ldaps://, ldap3 handles SSL automatically, 
            # but we still need to pass tls=tls_config to disable verification.
            use_ssl = self.server_uri.lower().startswith('ldaps://')
            
            server = Server(self.server_uri, get_info=ALL, tls=tls_config)
            
            # 1. Bind with Service Account
            if not self.bind_dn or not self.bind_password:
                logger.warning("LDAP Bind DN or Password not configured.")
                return False
                
            # Try simple bind first (usually works over SSL)
            # If fail, fallback to NTLM
            try:
                conn = Connection(server, user=self.bind_dn, password=self.bind_password, auto_bind=True)
            except Exception as e:
                logger.warning(f"Simple bind failed: {e}. Trying NTLM...")
                conn = Connection(server, user=self.bind_dn, password=self.bind_password, authentication=NTLM, auto_bind=True)
            
            # 2. Search for User DN
            search_base = f"{self.user_search_base},{self.base_dn}" if self.user_search_base else self.base_dn
            search_filter = f'(&(objectClass=user)(sAMAccountName={username}))'
            
            conn.search(
                search_base=search_base,
                search_filter=search_filter,
                attributes=['distinguishedName']
            )
            
            if not conn.entries:
                logger.warning(f"User {username} not found in LDAP.")
                return False
                
            user_dn = conn.entries[0].distinguishedName.value
            
            # 3. Authenticate User (Bind as User)
            # Try Simple Bind first (best for LDAPS)
            try:
                user_conn = Connection(server, user=user_dn, password=password)
                if user_conn.bind():
                    user_conn.unbind()
                    conn.unbind()
                    return True
            except Exception as e:
                logger.warning(f"User simple bind failed: {e}")
            
            # Fallback to NTLM if simple bind fails
            # NTLM needs DOMAIN\user
            domain_part = self.base_dn.split(',')[0].split('=')[1]
            ntlm_user = f"{domain_part.upper()}\\{username}"
            
            try:
                user_conn = Connection(server, user=ntlm_user, password=password, authentication=NTLM)
                if user_conn.bind():
                    user_conn.unbind()
                    conn.unbind()
                    return True
            except Exception as e:
                logger.warning(f"User NTLM bind failed: {e}")

            conn.unbind()
            return False

        except LDAPException as e:
            logger.error(f"LDAP Error during authentication: {str(e)}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error during LDAP authentication: {str(e)}")
            return False

    def get_user_info(self, username) -> Optional[Dict[str, Any]]:
        """Retrieve user information from LDAP."""
        if self.is_dev and username == 'admin':
            return {
                'username': 'admin',
                'display_name': 'Administrator',
                'email': 'admin@local.test',
                'groups': ['Admins']
            }

        try:
            tls_config = Tls(validate=ssl.CERT_NONE, version=ssl.PROTOCOL_TLSv1_2)
            server = Server(self.server_uri, get_info=ALL, tls=tls_config)
            
            try:
                conn = Connection(server, user=self.bind_dn, password=self.bind_password, auto_bind=True)
            except:
                conn = Connection(server, user=self.bind_dn, password=self.bind_password, authentication=NTLM, auto_bind=True)
            
            search_base = f"{self.user_search_base},{self.base_dn}" if self.user_search_base else self.base_dn
            search_filter = f'(&(objectClass=user)(sAMAccountName={username}))'
            
            conn.search(
                search_base=search_base,
                search_filter=search_filter,
                attributes=['displayName', 'mail', 'sAMAccountName', 'memberOf']
            )
            
            if conn.entries:
                entry = conn.entries[0]
                result = {
                    'username': str(entry.sAMAccountName),
                    'display_name': str(entry.displayName) if entry.displayName else username,
                    'email': str(entry.mail) if entry.mail else None,
                    'groups': self._parse_groups(entry.memberOf) if entry.memberOf else []
                }
                conn.unbind()
                return result
            conn.unbind()
            return None

        except Exception as e:
            logger.error(f"Error getting user info: {e}")
            return None

    def get_user_groups(self, username) -> List[str]:
        info = self.get_user_info(username)
        return info.get('groups', []) if info else []

    def get_all_groups(self) -> List[Dict]:
        """Get all LDAP groups."""
        if self.dev_mode:
            # Mock groups for dev mode testing
            return [
                {'cn': 'Domain Admins', 'dn': 'CN=Domain Admins,CN=Users,DC=example,DC=com', 'member_count': 5},
                {'cn': 'Teachers', 'dn': 'CN=Teachers,CN=Users,DC=example,DC=com', 'member_count': 10},
                {'cn': 'Students', 'dn': 'CN=Students,CN=Users,DC=example,DC=com', 'member_count': 100}
            ]

        try:
            if not self.connection.bind():
                logger.error("LDAP Bind failed for fetching groups")
                return []

            search_base = self.base_dn
            search_filter = '(objectClass=group)'
            attributes = ['cn', 'distinguishedName', 'member']

            self.connection.search(
                search_base=search_base,
                search_filter=search_filter,
                attributes=attributes
            )

            groups = []
            for entry in self.connection.entries:
                members = entry.member.values if hasattr(entry, 'member') and entry.member else []
                cn = str(entry.cn) if hasattr(entry, 'cn') and entry.cn else "Unknown"
                dn = str(entry.distinguishedName) if hasattr(entry, 'distinguishedName') and entry.distinguishedName else ""
                
                groups.append({
                    'cn': cn,
                    'dn': dn,
                    'member_count': len(members),
                    'members': members
                })

            return groups
        except Exception as e:
            logger.error(f"Error fetching groups: {e}")
            return []


    def _parse_groups(self, member_of_list) -> List[str]:
        groups = []
        if isinstance(member_of_list, str):
            member_of_list = [member_of_list]
        for group_dn in member_of_list:
            parts = str(group_dn).split(',')
            for part in parts:
                if part.upper().startswith('CN='):
                    groups.append(part[3:])
                    break
        return groups
