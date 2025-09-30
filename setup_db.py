from main import app, db
import logging
import os

# Set up basic logging
logging.basicConfig(level=logging.INFO)

with app.app_context():
    logging.info("Starting database table creation...")
    try:
        # This function creates all tables defined in your models if they don't exist.
        db.create_all()
        logging.info("✅ Database tables created successfully (or already existed).")
    except Exception as e:
        logging.error(f"❌ Failed to create database tables: {e}")
        # Exit with a non-zero status code to fail the deployment
        os._exit(1)