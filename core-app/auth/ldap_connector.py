"""
LDAP Connector for Active Directory authentication and user management.
"""
import logging
import ssl
from typing import Optional, Dict, List, Any
from ldap3 import Server, Connection, ALL, NTLM, Tls, SIMPLE
from ldap3.core.exceptions import LDAPException
from flask import current_app

# Configure logging
logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())


class LDAPConnector:
    def __init__(self):
        self.server_uri = current_app.config.get('LDAP_SERVER')
        self.bind_dn = current_app.config.get('LDAP_BIND_DN')
        self.bind_password = current_app.config.get('LDAP_BIND_PASSWORD')
        self.base_dn = current_app.config.get('LDAP_BASE_DN')
        self.user_search_base = current_app.config.get('LDAP_USER_SEARCH_BASE')
        self.group_search_base = current_app.config.get('LDAP_GROUP_SEARCH_BASE')

        # Determine Dev Mode
        env = current_app.config.get('FLASK_ENV')
        self.is_dev = (env == 'development')

        # Initialize connection as None
        self.connection = None
        self.server = None
        self._init_connection()

    def _init_connection(self):
        """Initialize LDAP connection object."""
        if not self.server_uri:
            return

        try:
            # Create Server object with TLS (ignore self-signed certs)
            tls_conf = Tls(validate=ssl.CERT_NONE, version=ssl.PROTOCOL_TLSv1_2)
            self.server = Server(self.server_uri, use_ssl=True, tls=tls_conf, get_info=ALL)
            # Initialize Connection (Bind later)
            # Default to NTLM if needed, or allow auto-negotiation
            self.connection = Connection(
                self.server,
                user=self.bind_dn,
                password=self.bind_password,
                authentication=NTLM,
                auto_bind=False,
            )
        except Exception as e:
            logger.error(f"Failed to initialize LDAP connection: {e}")

    def _bind_service_user(self):
        """Helper to bind with service account."""
        if not self.connection:
            return False

        try:
            # Try simple bind first (often works if DN is correct)
            self.connection.authentication = SIMPLE
            if self.connection.bind():
                return True

            # If simple fails, try NTLM
            self.connection.authentication = NTLM
            if self.connection.bind():
                return True

            logger.error("Failed to bind service user with both SIMPLE and NTLM.")
            return False
        except Exception as e:
            logger.error(f"Error binding service user: {e}")
            return False

    def authenticate(self, username, password) -> bool:
        """
        Authenticate user against LDAP.
        """
        # 1. Dev Mode Bypass
        if self.is_dev and username == 'admin' and password == 'admin':
            logger.info("Authenticated using Demo Mode (admin/admin)")
            return True

        if not username or not password:
            return False

        if not self.bind_dn or not self.bind_password:
            logger.error("LDAP Bind DN or Password not configured.")
            return False

        try:
            # 2. Bind with Service Account
            if not self._bind_service_user():
                return False

            # 3. Search for User DN
            search_base = f"{self.user_search_base},{self.base_dn}" if self.user_search_base else self.base_dn
            search_filter = f'(&(objectClass=user)(sAMAccountName={username}))'

            self.connection.search(
                search_base=search_base,
                search_filter=search_filter,
                attributes=['distinguishedName'],
            )

            if not self.connection.entries:
                logger.warning(f"User {username} not found in LDAP.")
                return False

            user_dn = self.connection.entries[0].distinguishedName.value

            # 4. Attempt Bind as User
            # Try Simple Bind with DN
            try:
                user_conn = Connection(self.server, user=user_dn, password=password, authentication=SIMPLE, auto_bind=True)
                user_conn.unbind()
                return True
            except Exception as e:
                logger.debug(f"User simple bind failed: {e}")

            # Try NTLM (DOMAIN\User)
            try:
                domain_part = self.base_dn.split(',')[0].split('=')[1]
                ntlm_user = f"{domain_part.upper()}\\{username}"
                user_conn = Connection(self.server, user=ntlm_user, password=password, authentication=NTLM, auto_bind=True)
                user_conn.unbind()
                return True
            except Exception as e:
                logger.debug(f"User NTLM bind failed: {e}")

            return False

        except LDAPException as e:
            logger.error(f"LDAP Error during authentication: {str(e)}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error during LDAP authentication: {str(e)}")
            return False

    def get_user_info(self, username) -> Optional[Dict[str, Any]]:
        """
        Get user details (Display Name, Email, Groups).
        """
        if self.is_dev and username == 'admin':
            return {
                'username': 'admin',
                'display_name': 'Administrator (Demo)',
                'email': 'admin@demo.local',
                'groups': ['Domain Admins', 'Schema Admins'],
            }

        try:
            if not self._bind_service_user():
                return None

            search_base = f"{self.user_search_base},{self.base_dn}" if self.user_search_base else self.base_dn
            search_filter = f'(&(objectClass=user)(sAMAccountName={username}))'
            attributes = ['displayName', 'mail', 'sAMAccountName', 'memberOf']

            self.connection.search(
                search_base=search_base,
                search_filter=search_filter,
                attributes=attributes,
            )

            if not self.connection.entries:
                return None

            entry = self.connection.entries[0]

            return {
                'username': str(entry.sAMAccountName),
                'display_name': str(entry.displayName) if entry.displayName else username,
                'email': str(entry.mail) if entry.mail else '',
                'groups': self._parse_groups(entry.memberOf.values if entry.memberOf else []),
            }

        except Exception as e:
            logger.error(f"Error getting user info: {e}")
            return None

    def get_user_groups(self, username) -> List[str]:
        info = self.get_user_info(username)
        return info.get('groups', []) if info else []

    def get_all_groups(self) -> List[Dict]:
        """Get all LDAP groups."""
        if hasattr(self, 'is_dev') and self.is_dev:
            # Mock groups for dev mode testing
            return [
                {'cn': 'Domain Admins', 'dn': 'CN=Domain Admins,CN=Users,DC=example,DC=com', 'member_count': 5},
                {'cn': 'Teachers', 'dn': 'CN=Teachers,CN=Users,DC=example,DC=com', 'member_count': 10},
                {'cn': 'Students', 'dn': 'CN=Students,CN=Users,DC=example,DC=com', 'member_count': 100},
            ]

        try:
            # Bind using helper to ensure correct auth method
            if not self._bind_service_user():
                logger.error("Bind failed in get_all_groups")
                return []

            search_base = self.base_dn
            search_filter = '(objectClass=group)'
            attributes = ['cn', 'distinguishedName', 'member']

            self.connection.search(
                search_base=search_base,
                search_filter=search_filter,
                attributes=attributes,
            )

            groups = []
            for entry in self.connection.entries:
                members = entry.member.values if hasattr(entry, 'member') and entry.member else []
                cn = str(entry.cn) if hasattr(entry, 'cn') and entry.cn else 'Unknown'
                dn = str(entry.distinguishedName) if hasattr(entry, 'distinguishedName') and entry.distinguishedName else ''
                groups.append({'cn': cn, 'dn': dn, 'member_count': len(members), 'members': members})

            groups.sort(key=lambda x: x['cn'])
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

    def search_users(self, query: str) -> List[Dict[str, Any]]:
        """
        Search for users in LDAP.
        """
        if self.is_dev:
            return [
                {'ldap_username': 'jdoe', 'first_name': 'John', 'last_name': 'Doe', 'department': 'IT', 'display_name': 'John Doe'},
                {'ldap_username': 'asmith', 'first_name': 'Alice', 'last_name': 'Smith', 'department': 'HR', 'display_name': 'Alice Smith'},
            ]

        if not self._bind_service_user():
            return []

        search_filter = f'(&(objectClass=user)(|(sAMAccountName=*{query}*)(givenName=*{query}*)(sn=*{query}*)(displayName=*{query}*)))'
        try:
            self.connection.search(
                search_base=self.user_search_base,
                search_filter=search_filter,
                attributes=['sAMAccountName', 'givenName', 'sn', 'department', 'displayName'],
            )

            users = []
            for entry in self.connection.entries:
                users.append({
                    'ldap_username': str(entry.sAMAccountName) if entry.sAMAccountName else '',
                    'first_name': str(entry.givenName) if entry.givenName else '',
                    'last_name': str(entry.sn) if entry.sn else '',
                    'department': str(entry.department) if entry.department else '',
                    'display_name': str(entry.displayName) if entry.displayName else '',
                })

            users.sort(key=lambda x: x['display_name'])
            return users

        except Exception as e:
            logger.error(f"Error searching users: {e}")
            return []
"""
LDAP Connector for Active Directory authentication and user management.
"""
import logging
import ssl
from typing import Optional, Dict, List, Any
from ldap3 import Server, Connection, ALL, SUBTREE, NTLM, Tls, SIMPLE
from ldap3.core.exceptions import LDAPException
from flask import current_app

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class LDAPConnector:
    def __init__(self):
        self.server_uri = current_app.config.get('LDAP_SERVER')
        self.bind_dn = current_app.config.get('LDAP_BIND_DN')
        self.bind_password = current_app.config.get('LDAP_BIND_PASSWORD')
        self.base_dn = current_app.config.get('LDAP_BASE_DN')
        self.user_search_base = current_app.config.get('LDAP_USER_SEARCH_BASE')
        self.group_search_base = current_app.config.get('LDAP_GROUP_SEARCH_BASE')
        
        # Determine Dev Mode
        env = current_app.config.get('FLASK_ENV')
        self.is_dev = (env == 'development')

            # Initialize connection as None
            self.connection = None
        self._init_connection()

    def _init_connection(self):
        """Initialize LDAP connection object."""
        if not self.server_uri:
            return

        try:
            # Create Server object with TLS (ignore self-signed certs)
            tls_conf = Tls(validate=ssl.CERT_NONE, version=ssl.PROTOCOL_TLSv1_2)
            self.server = Server(self.server_uri, use_ssl=True, tls=tls_conf, get_info=ALL)
            
            # Initialize Connection (Bind later)
            # Default to NTLM if needed, or allow auto-negotiation
                self.connection = Connection(
                self.server, 
                user=self.bind_dn, 
                password=self.bind_password,
                authentication=NTLM, # Default for AD often NTLM
                auto_bind=False
            )
        except Exception as e:
            logger.error(f"Failed to initialize LDAP connection: {e}")

    def _bind_service_user(self):
        """Helper to bind with service account."""
            if not self.connection:
            return False
            
        try:
            # Try simple bind first (often works if DN is correct)
                self.connection.authentication = SIMPLE
                if self.connection.bind():
                return True
                
            # If simple fails, try NTLM
                self.connection.authentication = NTLM
                if self.connection.bind():
                return True
                
            logger.error("Failed to bind service user with both SIMPLE and NTLM.")
            return False
        except Exception as e:
            logger.error(f"Error binding service user: {e}")
            return False

    def authenticate(self, username, password) -> bool:
        """
        Authenticate user against LDAP.
        """
        # 1. Dev Mode Bypass
        if self.is_dev and username == 'admin' and password == 'admin':
            logger.info("Authenticated using Demo Mode (admin/admin)")
            return True

        if not username or not password:
            return False

        if not self.bind_dn or not self.bind_password:
            logger.error("LDAP Bind DN or Password not configured.")
            return False

        try:
            # 2. Bind with Service Account
            if not self._bind_service_user():
                return False

            # 3. Search for User DN
            search_base = f"{self.user_search_base},{self.base_dn}" if self.user_search_base else self.base_dn
            search_filter = f'(&(objectClass=user)(sAMAccountName={username}))'
            
                self.connection.search(
                search_base=search_base,
                search_filter=search_filter,
                attributes=['distinguishedName']
            )

            if not self.connectionection.entries:
                logger.warning(f"User {username} not found in LDAP.")
                return False

            user_dn = self.connectionection.entries[0].distinguishedName.value

            # 4. Attempt Bind as User
            # Try Simple Bind with DN
            try:
                user_conn = Connection(self.server, user=user_dn, password=password, authentication=SIMPLE, auto_bind=True)
                user_conn.unbind()
                return True
            except Exception as e:
                logger.debug(f"User simple bind failed: {e}")

            # Try NTLM (DOMAIN\User)
            try:
                domain_part = self.base_dn.split(',')[0].split('=')[1]
                ntlm_user = f"{domain_part.upper()}\\{username}"
                user_conn = Connection(self.server, user=ntlm_user, password=password, authentication=NTLM, auto_bind=True)
                user_conn.unbind()
                return True
            except Exception as e:
                logger.debug(f"User NTLM bind failed: {e}")

            return False

        except LDAPException as e:
            logger.error(f"LDAP Error during authentication: {str(e)}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error during LDAP authentication: {str(e)}")
            return False

    def get_user_info(self, username) -> Optional[Dict[str, Any]]:
        """
        Get user details (Display Name, Email, Groups).
        """
        if self.is_dev and username == 'admin':
            return {
                'username': 'admin',
                'display_name': 'Administrator (Demo)',
                'email': 'admin@demo.local',
                'groups': ['Domain Admins', 'Schema Admins']
            }

        try:
            if not self._bind_service_user():
                return None

            search_base = f"{self.user_search_base},{self.base_dn}" if self.user_search_base else self.base_dn
            search_filter = f'(&(objectClass=user)(sAMAccountName={username}))'
            attributes = ['displayName', 'mail', 'sAMAccountName', 'memberOf']

                self.connection.search(
                search_base=search_base,
                search_filter=search_filter,
                attributes=attributes
            )

            if not self.connectionection.entries:
                return None

            *** End Patch
        except Exception as e:
            logger.error(f"Error searching users: {e}")
            return []
