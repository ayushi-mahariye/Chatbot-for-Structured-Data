#!/usr/bin/env python3
"""
Setup script for RBAC SQL Chatbot system
"""

import os
import subprocess
import sys
from pathlib import Path

def run_command(command, cwd=None):
    """Run a shell command and return the result"""
    try:
        result = subprocess.run(
            command, 
            shell=True, 
            cwd=cwd, 
            capture_output=True, 
            text=True
        )
        if result.returncode != 0:
            print(f"Error running command: {command}")
            print(f"Error: {result.stderr}")
            return False
        return True
    except Exception as e:
        print(f"Exception running command {command}: {e}")
        return False

def setup_backend():
    """Setup backend environment"""
    print("Setting up backend...")
    
    backend_dir = Path("backend")
    if not backend_dir.exists():
        print("Backend directory not found!")
        return False
    
    # Create virtual environment
    if not run_command("python -m venv venv", cwd=backend_dir):
        return False
    
    # Install dependencies
    pip_cmd = "venv\\Scripts\\pip" if os.name == 'nt' else "venv/bin/pip"
    
    # Try Windows-specific requirements first on Windows
    if os.name == 'nt':
        print("Installing Windows-compatible packages...")
        if not run_command(f"{pip_cmd} install -r requirements-windows.txt", cwd=backend_dir):
            print("Falling back to standard requirements...")
            if not run_command(f"{pip_cmd} install -r requirements.txt", cwd=backend_dir):
                return False
    else:
        if not run_command(f"{pip_cmd} install -r requirements.txt", cwd=backend_dir):
            return False
    
    # Copy environment file
    env_example = backend_dir / ".env.example"
    env_file = backend_dir / ".env"
    
    if env_example.exists() and not env_file.exists():
        env_file.write_text(env_example.read_text())
        print("Created .env file from .env.example")
    
    print("Backend setup completed!")
    return True

def setup_database():
    """Setup database tables"""
    print("Setting up database...")
    
    # This would typically run Alembic migrations
    # For now, just create the tables manually
    
    sql_script = """
    -- Create conversation history table
    CREATE TABLE IF NOT EXISTS conversation_history (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        question TEXT,
        sql_query TEXT,
        results JSONB,
        explanation TEXT,
        username VARCHAR(80),
        role VARCHAR(50),
        outcome_status VARCHAR(50),
        created_at TIMESTAMP DEFAULT now()
    );

    -- Create feedback table
    CREATE TABLE IF NOT EXISTS feedback (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        question_id UUID,
        complexity_score VARCHAR(10),
        intent_category VARCHAR(100),
        reviewer VARCHAR(80),
        feedback_comment TEXT,
        created_at TIMESTAMP DEFAULT now()
    );

    -- Create RBAC roles
    DO $$
    BEGIN
        IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'admin') THEN
            CREATE ROLE admin;
        END IF;
        
        IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'analyst') THEN
            CREATE ROLE analyst;
        END IF;
        
        IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'readonly') THEN
            CREATE ROLE readonly;
        END IF;
        
        IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'dataentry') THEN
            CREATE ROLE dataentry;
        END IF;
        
        IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'servicebot') THEN
            CREATE ROLE servicebot;
        END IF;
    END
    $$;
    """
    
    # Save SQL script
    with open("setup_db.sql", "w") as f:
        f.write(sql_script)
    
    print("Database setup SQL created: setup_db.sql")
    print("Run this script against your PostgreSQL database")
    return True

def main():
    """Main setup function"""
    print("RBAC SQL Chatbot System Setup")
    print("=" * 40)
    
    # Check Python version
    if sys.version_info < (3, 11):
        print("Python 3.11+ is required!")
        return False
    
    # Setup backend
    if not setup_backend():
        print("Backend setup failed!")
        return False
    
    # Setup database
    if not setup_database():
        print("Database setup failed!")
        return False
    
    print("\nSetup completed successfully!")
    print("\nNext steps:")
    print("1. Configure your .env files with proper database credentials")
    print("2. Run setup_db.sql against your PostgreSQL database")
    print("3. Start the backend: cd backend && python main.py")
    print("4. Start pos-api if not already running")
    
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)