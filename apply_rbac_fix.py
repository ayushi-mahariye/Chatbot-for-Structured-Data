#!/usr/bin/env python3
"""
RBAC Fix Application Script
Applies user_roles table migration and grants permissions on all tables
"""

import sys
import os
from pathlib import Path
import psycopg2
from psycopg2 import sql
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class RBACFixApplicator:
    """Apply RBAC fixes to PostgreSQL database"""
    
    def __init__(self, database_url: str):
        """Initialize with database connection string"""
        self.database_url = database_url
        self.conn = None
        self.cursor = None
    
    def connect(self):
        """Connect to PostgreSQL database"""
        try:
            logger.info("Connecting to database...")
            self.conn = psycopg2.connect(self.database_url)
            self.conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
            self.cursor = self.conn.cursor()
            logger.info("✅ Connected successfully")
            return True
        except Exception as e:
            logger.error(f"❌ Connection failed: {e}")
            return False
    
    def disconnect(self):
        """Close database connection"""
        if self.cursor:
            self.cursor.close()
        if self.conn:
            self.conn.close()
        logger.info("Disconnected from database")
    
    def check_roles_exist(self):
        """Check if PostgreSQL roles exist"""
        logger.info("\n📋 Checking PostgreSQL roles...")
        roles = ['admin', 'analyst', 'readonly', 'dataentry', 'servicebot']
        
        try:
            self.cursor.execute("""
                SELECT rolname FROM pg_roles 
                WHERE rolname IN ('admin', 'analyst', 'readonly', 'dataentry', 'servicebot')
            """)
            existing_roles = [row[0] for row in self.cursor.fetchall()]
            
            for role in roles:
                if role in existing_roles:
                    logger.info(f"  ✅ Role '{role}' exists")
                else:
                    logger.warning(f"  ⚠️  Role '{role}' does not exist - creating...")
                    self.cursor.execute(sql.SQL("CREATE ROLE {}").format(sql.Identifier(role)))
                    logger.info(f"  ✅ Created role '{role}'")
            
            return True
        except Exception as e:
            logger.error(f"❌ Error checking roles: {e}")
            return False
    
    def create_user_roles_table(self):
        """Create user_roles mapping table"""
        logger.info("\n📋 Creating user_roles table...")
        
        try:
            self.cursor.execute("""
                CREATE TABLE IF NOT EXISTS user_roles (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    user_id VARCHAR(255) NOT NULL,
                    db_role VARCHAR(50) NOT NULL,
                    is_active BOOLEAN DEFAULT true,
                    assigned_by VARCHAR(80),
                    assigned_at TIMESTAMP DEFAULT now(),
                    UNIQUE(user_id, db_role)
                );
            """)
            logger.info("  ✅ user_roles table created")
            
            # Create index
            self.cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_user_roles_user_id 
                ON user_roles(user_id) WHERE is_active = true;
            """)
            logger.info("  ✅ Index created")
            
            return True
        except Exception as e:
            logger.error(f"❌ Error creating table: {e}")
            return False
    
    def grant_permissions_on_all_tables(self):
        """Grant permissions on all tables in marketmap_schemaschema"""
        logger.info("\n📋 Granting permissions on all tables...")
        
        try:
            # Get all tables in marketmap_schemaschema
            self.cursor.execute("""
                SELECT tablename FROM pg_tables WHERE schemaname = 'marketmap_schema'
            """)
            tables = [row[0] for row in self.cursor.fetchall()]
            
            if not tables:
                logger.warning("  ⚠️  No tables found in marketmap_schemaschema")
                return True
            
            logger.info(f"  Found {len(tables)} tables")
            
            for table in tables:
                try:
                    # Grant SELECT to readonly and analyst
                    self.cursor.execute(
                        sql.SQL("GRANT SELECT ON TABLE {} TO readonly, analyst").format(
                            sql.Identifier(table)
                        )
                    )
                    
                    # Grant SELECT, INSERT, UPDATE to dataentry
                    self.cursor.execute(
                        sql.SQL("GRANT SELECT, INSERT, UPDATE ON TABLE {} TO dataentry").format(
                            sql.Identifier(table)
                        )
                    )
                    
                    # Grant ALL to admin
                    self.cursor.execute(
                        sql.SQL("GRANT ALL PRIVILEGES ON TABLE {} TO admin").format(
                            sql.Identifier(table)
                        )
                    )
                    
                    logger.info(f"  ✅ Granted permissions on '{table}'")
                except Exception as e:
                    logger.warning(f"  ⚠️  Error granting permissions on '{table}': {e}")
            
            return True
        except Exception as e:
            logger.error(f"❌ Error granting permissions: {e}")
            return False
    
    def grant_sequence_permissions(self):
        """Grant permissions on sequences"""
        logger.info("\n📋 Granting permissions on sequences...")
        
        try:
            # Get all sequences in marketmap_schemaschema
            self.cursor.execute("""
                SELECT sequencename FROM pg_sequences WHERE schemaname = 'marketmap_schema'
            """)
            sequences = [row[0] for row in self.cursor.fetchall()]
            
            if not sequences:
                logger.info("  ℹ️  No sequences found")
                return True
            
            logger.info(f"  Found {len(sequences)} sequences")
            
            for sequence in sequences:
                try:
                    # Grant USAGE, SELECT to dataentry
                    self.cursor.execute(
                        sql.SQL("GRANT USAGE, SELECT ON SEQUENCE {} TO dataentry").format(
                            sql.Identifier(sequence)
                        )
                    )
                    
                    # Grant ALL to admin
                    self.cursor.execute(
                        sql.SQL("GRANT ALL PRIVILEGES ON SEQUENCE {} TO admin").format(
                            sql.Identifier(sequence)
                        )
                    )
                    
                    logger.info(f"  ✅ Granted permissions on sequence '{sequence}'")
                except Exception as e:
                    logger.warning(f"  ⚠️  Error granting permissions on '{sequence}': {e}")
            
            return True
        except Exception as e:
            logger.error(f"❌ Error granting sequence permissions: {e}")
            return False
    
    def verify_permissions(self):
        """Verify permissions were granted correctly"""
        logger.info("\n📋 Verifying permissions...")
        
        try:
            self.cursor.execute("""
                SELECT grantee, table_name, privilege_type
                FROM information_schema.role_table_grants
                WHERE grantee IN ('admin', 'analyst', 'readonly', 'dataentry', 'servicebot')
                  AND table_schema = 'marketmap_schema'
                ORDER BY grantee, table_name
            """)
            
            results = self.cursor.fetchall()
            
            if not results:
                logger.warning("  ⚠️  No permissions found")
                return False
            
            # Group by role
            role_permissions = {}
            for grantee, table_name, privilege_type in results:
                if grantee not in role_permissions:
                    role_permissions[grantee] = {}
                if table_name not in role_permissions[grantee]:
                    role_permissions[grantee][table_name] = []
                role_permissions[grantee][table_name].append(privilege_type)
            
            # Display summary
            for role, tables in role_permissions.items():
                logger.info(f"  ✅ Role '{role}': {len(tables)} tables with permissions")
            
            return True
        except Exception as e:
            logger.error(f"❌ Error verifying permissions: {e}")
            return False
    
    def assign_test_user_role(self, user_id: str, db_role: str = 'readonly'):
        """Assign a test user to a role (optional)"""
        logger.info(f"\n📋 Assigning user '{user_id}' to role '{db_role}'...")
        
        try:
            self.cursor.execute("""
                INSERT INTO user_roles (user_id, db_role, assigned_by)
                VALUES (%s, %s, 'system')
                ON CONFLICT (user_id, db_role) DO NOTHING
            """, (user_id, db_role))
            
            logger.info(f"  ✅ User assigned to role '{db_role}'")
            return True
        except Exception as e:
            logger.error(f"❌ Error assigning user role: {e}")
            return False
    
    def run(self, assign_user: str = None, user_role: str = 'readonly'):
        """Run all migration steps"""
        logger.info("=" * 60)
        logger.info("🚀 Starting RBAC Fix Application")
        logger.info("=" * 60)
        
        if not self.connect():
            return False
        
        try:
            # Step 1: Check/Create roles
            if not self.check_roles_exist():
                logger.error("Failed to verify roles")
                return False
            
            # Step 2: Create user_roles table
            if not self.create_user_roles_table():
                logger.error("Failed to create user_roles table")
                return False
            
            # Step 3: Grant table permissions
            if not self.grant_permissions_on_all_tables():
                logger.error("Failed to grant table permissions")
                return False
            
            # Step 4: Grant sequence permissions
            if not self.grant_sequence_permissions():
                logger.warning("Failed to grant sequence permissions (non-critical)")
            
            # Step 5: Verify permissions
            if not self.verify_permissions():
                logger.warning("Permission verification incomplete")
            
            # Step 6: Assign test user (optional)
            if assign_user:
                if not self.assign_test_user_role(assign_user, user_role):
                    logger.warning("Failed to assign test user (non-critical)")
            
            logger.info("\n" + "=" * 60)
            logger.info("✅ RBAC Fix Applied Successfully!")
            logger.info("=" * 60)
            logger.info("\n📝 Next Steps:")
            logger.info("  1. Restart backend: docker-compose restart backend")
            logger.info("  2. Test query with JWT token")
            logger.info("  3. Check logs: docker-compose logs backend --tail=50")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Unexpected error: {e}")
            return False
        finally:
            self.disconnect()


def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Apply RBAC fix to SQL Pipeline database',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Using environment variable
  export DATABASE_URL="postgresql://ai:ai%402025@43.205.18.21:5432/ai-db"
  python apply_rbac_fix.py
  
  # Using command line argument
  python apply_rbac_fix.py --db-url "postgresql://user:pass@host:5432/dbname"
  
  # Assign specific user to role
  python apply_rbac_fix.py --assign-user "59ee3a01-980b-42ee-b590-65df39c59f4e" --user-role "admin"
        """
    )
    
    parser.add_argument(
        '--db-url',
        help='Database URL (default: from DATABASE_URL env var)',
        default=os.getenv('DATABASE_URL', 'postgresql://ai:ai%402025@43.205.18.21:5432/ai-db')
    )
    
    parser.add_argument(
        '--assign-user',
        help='User ID to assign to a role (optional)',
        default=None
    )
    
    parser.add_argument(
        '--user-role',
        help='Role to assign to user (default: readonly)',
        default='readonly',
        choices=['admin', 'analyst', 'readonly', 'dataentry', 'servicebot']
    )
    
    args = parser.parse_args()
    
    # Validate database URL
    if not args.db_url:
        logger.error("❌ Database URL not provided. Use --db-url or set DATABASE_URL environment variable")
        sys.exit(1)
    
    # Run migration
    applicator = RBACFixApplicator(args.db_url)
    success = applicator.run(assign_user=args.assign_user, user_role=args.user_role)
    
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
