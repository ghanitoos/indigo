"""
LDAP Connector for Active Directory authentication and user management.
"""
import logging
from typing import Optional, Dict, List, Any
from ldap3 import Server, Connection, ALL, SUBTREE, NTLM
from ldap3.core.exceptions import LDAPException
from flask import current_app

logger = logging.getLogger(__name__)


class LDAPConnector:
    """
    Connector for interacting with Samba AD DC via LDAP.
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
        
        Args:
            username (str): The username to authenticate
            password (str): The user's password
            
        Returns:
            bool: True if authentication was successful, False otherwise
        """
        # Demo mode for development
        if self.is_dev and username == 'admin' and password == 'admin':
            logger.info("Authenticated using Demo Mode (admin/admin)")
            return True

        if not username or not password:
            return False

        try:
            server = Server(self.server_uri, get_info=ALL)
            
            # First bind with service account to find the user DN
            # If BIND_DN is not set, we can't search easily in AD without anonymous bind (disabled by default)
            if not self.bind_dn or not self.bind_password:
                logger.warning("LDAP Bind DN or Password not configured.")
                return False
                
            conn = Connection(server, user=self.bind_dn, password=self.bind_password, auto_bind=True)
            
            # Search for the user
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
            
            # Verify credentials by binding as the user
            user_conn = Connection(server, user=user_dn, password=password)
            if user_conn.bind():
                user_conn.unbind()
                return True
            else:
                return False

        except LDAPException as e:
            logger.error(f"LDAP Error during authentication: {str(e)}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error during LDAP authentication: {str(e)}")
            return False

    def get_user_info(self, username) -> Optional[Dict[str, Any]]:
        """
        Retrieve user information from LDAP.
        
        Args:
            username (str): The username to look up
            
        Returns:
            dict: User attributes (display_name, email, etc.) or None if not found
        """
        if self.is_dev and username == 'admin':
            return {
                'username': 'admin',
                'display_name': 'Administrator',
                'email': 'admin@local.test',
                'groups': ['Admins']
            }

        try:
            server = Server(self.server_uri, get_info=ALL)
            conn = Connection(server, user=self.bind_dn, password=self.bind_password, auto_bind=True)
            
            search_base = f"{self.user_search_base},{self.base_dn}" if self.user_search_base else self.base_dn
            search_filter = f'(&(objectClass=user)(sAMAccountName={username}))'
            
            conn.search(
                search_base=search_base,
                search_filter=search_filter,
                attributes=['displayName', 'mail', 'sAMAccountName', 'memberOf']
            )
            
            if conn.entries:
                entry = conn.entries[0]
                return {
                    'username': str(entry.sAMAccountName),
                    'display_name': str(entry.displayName) if entry.displayName else username,
                    'email': str(entry.mail) if entry.mail else None,
                    'groups': self._parse_groups(entry.memberOf) if entry.memberOf else []
                }
            return None

        except Exception as e:
            logger.error(f"Error getting user info: {e}")
            return None

    def get_user_groups(self, username) -> List[str]:
        """
        Get the list of groups a user belongs to.
        
        Args:
            username (str): The username
            
        Returns:
            list: List of group names
        """
        info = self.get_user_info(username)
        return info.get('groups', []) if info else []

    def _parse_groups(self, member_of_list) -> List[str]:
        """Parse group names from DN list."""
        groups = []
        # memberOf can be a single string or list
        if isinstance(member_of_list, str):
            member_of_list = [member_of_list]
            
        for group_dn in member_of_list:
            # Extract CN from DN (CN=Group Name,OU=...)
            parts = str(group_dn).split(',')
            for part in parts:
                if part.upper().startswith('CN='):
                    groups.append(part[3:])
                    break
        return groups
