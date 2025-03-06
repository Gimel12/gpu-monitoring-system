#!/usr/bin/env python3
from master import db, app, GPUMetricsHistory
import os

# Create the database tables if they don't exist
with app.app_context():
    print("Creating GPUMetricsHistory table...")
    db.create_all()
    print("Database migration completed successfully!")
