#!/usr/bin/env python3
from master import db, app, GPUMetricsHistory, Worker, Command
import os
import sqlite3

# Create the database tables if they don't exist
with app.app_context():
    print("Creating database tables...")
    
    # Drop the table if it exists to recreate it
    try:
        print("Dropping existing GPUMetricsHistory table if it exists...")
        db.session.execute('DROP TABLE IF EXISTS gpu_metrics_history')
        db.session.commit()
        print("Table dropped successfully.")
    except Exception as e:
        print(f"Error dropping table: {e}")
        db.session.rollback()
    
    # Create all tables
    db.create_all()
    print("All tables created.")
    
    # Verify the table was created
    db_path = app.config['SQLALCHEMY_DATABASE_URI'].replace('sqlite:///', '')
    if db_path.startswith('/'):
        # Absolute path
        conn = sqlite3.connect(db_path)
    else:
        # Relative path
        conn = sqlite3.connect(os.path.join(os.path.dirname(__file__), db_path))
    
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='gpu_metrics_history';")
    result = cursor.fetchone()
    
    if result:
        print("Verified GPUMetricsHistory table exists in database.")
        # Also check the structure
        cursor.execute("PRAGMA table_info(gpu_metrics_history);")
        columns = cursor.fetchall()
        print(f"Table structure: {columns}")
    else:
        print("WARNING: GPUMetricsHistory table was not created properly!")
    
    conn.close()
    print("Database migration completed successfully!")
