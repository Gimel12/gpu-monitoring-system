#!/usr/bin/env python3
from master import db, app, GPUMetricsHistory, Worker, Command
import os
import sqlite3
from sqlalchemy import text, inspect

# Create the database tables if they don't exist
with app.app_context():
    print("Creating database tables...")
    
    # Force recreate the GPUMetricsHistory table
    inspector = inspect(db.engine)
    existing_tables = inspector.get_table_names()
    print(f"Existing tables: {existing_tables}")
    
    # Drop the table if it exists
    try:
        print("Dropping existing GPUMetricsHistory table if it exists...")
        db.session.execute(text("DROP TABLE IF EXISTS gpu_metrics_history"))
        db.session.commit()
        print("Table dropped successfully.")
    except Exception as e:
        print(f"Error dropping table: {e}")
        db.session.rollback()
    
    # Create all tables
    print("Creating tables...")
    db.create_all()
    print("All tables created.")
    
    # Verify using SQLAlchemy's inspector
    inspector = inspect(db.engine)
    tables_after_create = inspector.get_table_names()
    print(f"Tables after create_all: {tables_after_create}")
    
    if 'gpu_metrics_history' in tables_after_create:
        print("Verified GPUMetricsHistory table exists using SQLAlchemy inspector.")
        columns = inspector.get_columns('gpu_metrics_history')
        column_names = [col['name'] for col in columns]
        print(f"Columns in gpu_metrics_history: {column_names}")
    else:
        print("WARNING: GPUMetricsHistory table was not found in SQLAlchemy inspector!")
    
    # Double-check with direct SQLite query
    db_path = app.config['SQLALCHEMY_DATABASE_URI'].replace('sqlite:///', '')
    if not db_path or db_path == ':memory:':
        db_path = 'workers.db'  # Default SQLite database name
    
    if not os.path.isabs(db_path):
        # Relative path
        db_path = os.path.join(os.path.dirname(__file__), db_path)
    
    print(f"Database path: {db_path}")
    
    if os.path.exists(db_path):
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='gpu_metrics_history';")
        result = cursor.fetchone()
        
        if result:
            print("Verified GPUMetricsHistory table exists in SQLite database.")
            # Also check the structure
            cursor.execute("PRAGMA table_info(gpu_metrics_history);")
            columns = cursor.fetchall()
            print(f"SQLite table structure: {columns}")
        else:
            print("WARNING: GPUMetricsHistory table was not found in SQLite database!")
        
        conn.close()
    else:
        print(f"WARNING: Database file {db_path} does not exist!")
    
    print("Database migration completed.")
    
    # Create a test record to verify we can write to the table
    try:
        print("Creating a test record in GPUMetricsHistory table...")
        test_record = GPUMetricsHistory(
            worker_id=1,  # This assumes worker with ID 1 exists, or will be created
            gpu_index=0,
            temperature=0,
            utilization=0,
            memory_used=0,
            memory_total=1,
            power_usage=0
        )
        db.session.add(test_record)
        db.session.commit()
        print("Test record created successfully.")
    except Exception as e:
        print(f"Error creating test record: {e}")
        db.session.rollback()
    
    print("Database migration completed successfully!")
