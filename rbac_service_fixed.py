from sqlalchemy import text
from sqlalchemy.orm import Session
from typing import Dict, List
import re

class RBACService:
    def __init__(self, db: Session):
        self.db = db
    
    def get_user_permissions(self, username: str, role: str) -> Dict:
        """Get user's table and column permissions"""
        try:
            permissions = {}
            
            # First check if user is admin - if so, grant all permissions
            if role == "admin":
                # Grant full access to public schema
                permissions["public"] = {}
                
                # Query all tables in public schema
                tables_query = text("""
                    SELECT table_name 
                    FROM information_schema.tables 
                    WHERE table_schema = 'public'
                """)
                
                tables_result = self.db.execute(tables_query).fetchall()
                
                # Grant all privileges to all tables for admin
                for row in tables_result:
                    table = row.table_name
                    permissions["public"][table] = {
                        "columns": [], 
                        "privileges": ["SELECT", "INSERT", "UPDATE", "DELETE"]
                    }
                
                return permissions
            
            # For non-admin users, check PostgreSQL native permissions
            query = text("""
                SELECT 
                    table_schema,
                    table_name,
                    column_name,
                    privilege_type
                FROM information_schema.role_column_grants 
                WHERE grantee = :username
                UNION
                SELECT 
                    table_schema,
                    table_name,
                    NULL as column_name,
                    privilege_type
                FROM information_schema.role_table_grants 
                WHERE grantee = :username
            """)
            
            result = self.db.execute(query, {"username": username}).fetchall()
            
            for row in result:
                schema = row.table_schema
                table = row.table_name
                column = row.column_name
                privilege = row.privilege_type
                
                if schema not in permissions:
                    permissions[schema] = {}
                if table not in permissions[schema]:
                    permissions[schema][table] = {"columns": [], "privileges": []}
                
                if column and column not in permissions[schema][table]["columns"]:
                    permissions[schema][table]["columns"].append(column)
                if privilege not in permissions[schema][table]["privileges"]:
                    permissions[schema][table]["privileges"].append(privilege)
            
            return permissions
            
        except Exception as e:
            print(f"Error getting permissions: {e}")
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
