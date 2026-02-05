from sqlalchemy import text
from sqlalchemy.orm import Session
from typing import Dict, List, Optional
import re
import logging

logger = logging.getLogger(__name__)

class RBACService:
    def __init__(self, db: Session):
        self.db = db
    
    def _map_jwt_role_to_db_role(self, jwt_role: str) -> Optional[str]:
        """Map JWT role claim to PostgreSQL database role"""
        # Default role mapping - customize based on your JWT role structure
        role_mapping = {
            "admin": "admin",
            "administrator": "admin",
            "analyst": "analyst",
            "data_analyst": "analyst",
            "readonly": "readonly",
            "read_only": "readonly",
            "viewer": "readonly",
            "dataentry": "dataentry",
            "data_entry": "dataentry",
            "editor": "dataentry",
            "servicebot": "servicebot",
            "bot": "servicebot",
            "user": "readonly",  # Default user role maps to readonly
        }
        
        return role_mapping.get(jwt_role.lower(), "readonly")
    
    def _get_user_db_role(self, username: str, jwt_role: str) -> Optional[str]:
        """Get PostgreSQL database role for user"""
        try:
            # First, check if there's an explicit user-role mapping in database
            # This allows for user-specific role assignments
            query = text("""
                SELECT db_role 
                FROM user_roles 
                WHERE user_id = :username AND is_active = true
                LIMIT 1
            """)
            
            result = self.db.execute(query, {"username": username}).fetchone()
            if result:
                logger.info(f"Found explicit role mapping for user {username}: {result[0]}")
                return result[0]
        except Exception as e:
            # Table might not exist yet - this is expected for new installations
            logger.debug(f"No user_roles table or mapping found: {e}")
        
        # Fallback: Use JWT role mapping
        db_role = self._map_jwt_role_to_db_role(jwt_role)
        logger.info(f"Using JWT role mapping for user {username}: {jwt_role} -> {db_role}")
        return db_role
    
    def get_user_permissions(self, username: str, role: str) -> Dict:
        """Get user's table and column permissions based on their PostgreSQL role"""
        try:
            # Get the PostgreSQL database role for this user
            db_role = self._get_user_db_role(username, role)
            
            if not db_role:
                logger.warning(f"No database role found for user {username} with JWT role {role}")
                return {}
            
            logger.info(f"Querying permissions for database role: {db_role}")
            
            # Query PostgreSQL information_schema for role permissions
            query = text("""
                SELECT 
                    table_schema,
                    table_name,
                    column_name,
                    privilege_type
                FROM information_schema.role_column_grants 
                WHERE grantee = :db_role
                UNION
                SELECT 
                    table_schema,
                    table_name,
                    NULL as column_name,
                    privilege_type
                FROM information_schema.role_table_grants 
                WHERE grantee = :db_role
            """)
            
            result = self.db.execute(query, {"db_role": db_role}).fetchall()
            
            if not result:
                logger.warning(f"No permissions found for database role: {db_role}")
                return {}
            
            permissions = {}
            for row in result:
                schema = row.table_schema
                table = row.table_name
                column = row.column_name
                privilege = row.privilege_type
                
                if schema not in permissions:
                    permissions[schema] = {}
                if table not in permissions[schema]:
                    permissions[schema][table] = {"columns": [], "privileges": []}
                
                if column:
                    permissions[schema][table]["columns"].append(column)
                permissions[schema][table]["privileges"].append(privilege)
            
            logger.info(f"Found permissions for {len(permissions)} schemas")
            return permissions
            
        except Exception as e:
            logger.error(f"Error getting permissions: {e}")
            return {}
    
    def validate_sql_query(self, sql_query: str, user_permissions: Dict) -> Dict:
        """Validate SQL query against user permissions"""
        try:
            # Basic SQL parsing to extract tables and columns
            sql_upper = sql_query.upper()
            
            # Check for destructive operations
            destructive_ops = ["DROP", "DELETE", "TRUNCATE", "ALTER", "CREATE"]
            for op in destructive_ops:
                if op in sql_upper:
                    if op == "DELETE" and "WHERE" not in sql_upper:
                        return {"valid": False, "error": "DELETE without WHERE clause not allowed"}
                    elif op != "DELETE":
                        return {"valid": False, "error": f"{op} operations not allowed"}
            
            # Extract table names (improved regex)
            table_pattern = r"FROM\s+(?:public\.)?([\w-]+)|JOIN\s+(?:public\.)?([\w-]+)|UPDATE\s+(?:public\.)?([\w-]+)|INSERT\s+INTO\s+(?:public\.)?([\w-]+)"
            tables = re.findall(table_pattern, sql_upper)
            
            # Flatten and clean table names
            referenced_tables = []
            for match in tables:
                for table in match:
                    if table:
                        referenced_tables.append(table.lower())
            
            # Check if user has access to all referenced tables
            for table in referenced_tables:
                has_access = False
                # Check both with and without schema prefix
                for schema, schema_tables in user_permissions.items():
                    if table in schema_tables or table.replace('public.', '') in schema_tables:
                        has_access = True
                        break
                
                if not has_access:
                    return {"valid": False, "error": f"No access to table: {table}"}
            
            return {"valid": True, "message": "Query validated successfully"}
            
        except Exception as e:
            return {"valid": False, "error": f"Validation error: {str(e)}"}
    
    def grant_permission(self, role: str, table: str, columns: List[str] = None, privilege: str = "SELECT") -> Dict:
        """Grant permissions to a role"""
        try:
            if columns:
                # Column-level permissions
                columns_str = ", ".join(columns)
                query = text(f"GRANT {privilege} ({columns_str}) ON {table} TO {role}")
            else:
                # Table-level permissions
                query = text(f"GRANT {privilege} ON {table} TO {role}")
            
            self.db.execute(query)
            self.db.commit()
            
            return {"success": True, "message": f"Granted {privilege} on {table} to {role}"}
            
        except Exception as e:
            self.db.rollback()
            return {"success": False, "error": str(e)}
    
    def revoke_permission(self, role: str, table: str, columns: List[str] = None, privilege: str = "SELECT") -> Dict:
        """Revoke permissions from a role"""
        try:
            if columns:
                columns_str = ", ".join(columns)
                query = text(f"REVOKE {privilege} ({columns_str}) ON {table} FROM {role}")
            else:
                query = text(f"REVOKE {privilege} ON {table} FROM {role}")
            
            self.db.execute(query)
            self.db.commit()
            
            return {"success": True, "message": f"Revoked {privilege} on {table} from {role}"}
            
        except Exception as e:
            self.db.rollback()
            return {"success": False, "error": str(e)}