"""
Script to update the database with the new schema including user_id in models.
"""

import os
import sys
import logging
from datetime import datetime

from checktime.shared.db import db
from checktime.web import create_app
from checktime.shared.models.user import User
from checktime.shared.models.holiday import Holiday
from checktime.shared.models.schedule import SchedulePeriod
from sqlalchemy.exc import OperationalError, IntegrityError

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

if __name__ == "__main__":
    logger.info("Starting database update...")
    
    app = create_app()
    
    with app.app_context():
        try:
            # Create all tables according to current models
            db.create_all()
            
            logger.info("Database schema updated!")
            
            # Check if we need to migrate existing data
            admin_user = User.query.filter_by(username='admin').first()
            if admin_user:
                try:
                    # Count records that need migration
                    holidays_count = db.session.query(Holiday).filter(Holiday.user_id.is_(None)).count()
                    periods_count = db.session.query(SchedulePeriod).filter(SchedulePeriod.user_id.is_(None)).count()
                    
                    if holidays_count > 0 or periods_count > 0:
                        logger.info(f"Found {holidays_count} holidays and {periods_count} schedule periods without user_id.")
                        logger.info(f"Assigning them to admin user (id: {admin_user.id})...")
                        
                        # Update holidays
                        for holiday in db.session.query(Holiday).filter(Holiday.user_id.is_(None)).all():
                            holiday.user_id = admin_user.id
                            logger.info(f"Updated holiday {holiday.id}: {holiday.date} - {holiday.description}")
                        
                        # Update schedule periods
                        for period in db.session.query(SchedulePeriod).filter(SchedulePeriod.user_id.is_(None)).all():
                            period.user_id = admin_user.id
                            logger.info(f"Updated schedule period {period.id}: {period.name}")
                        
                        # Commit changes
                        db.session.commit()
                        logger.info("Migration completed successfully!")
                except OperationalError as oe:
                    # This can happen if the new columns don't exist yet
                    logger.warning(f"Operational error during migration: {str(oe)}")
                    logger.info("This is normal for a first-time setup with new columns.")
                    db.session.rollback()
                except IntegrityError as ie:
                    logger.error(f"Integrity error during migration: {str(ie)}")
                    logger.info("Possible duplicate records or constraint violations.")
                    db.session.rollback()
                except Exception as e:
                    logger.error(f"Error during data migration: {str(e)}")
                    db.session.rollback()
            else:
                logger.warning("Admin user not found. Cannot migrate existing data.")
                logger.info("Please create an admin user first or run the database initialization script.")
        except Exception as e:
            logger.error(f"Error updating database schema: {str(e)}")
            sys.exit(1)
        
        logger.info("Database update completed!")
        sys.exit(0) 