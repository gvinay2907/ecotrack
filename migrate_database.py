"""
Database Migration Script
Run this ONCE to add new columns to existing database
"""

from app import app, db
from sqlalchemy import text

def migrate_database():
    """Add new columns to existing tables"""
    
    with app.app_context():
        try:
            # Add new columns to User table
            with db.engine.connect() as conn:
                print("Starting database migration...")
                
                # Check if columns already exist before adding
                try:
                    conn.execute(text("SELECT location_type FROM user LIMIT 1"))
                    print("✓ location_type already exists")
                except:
                    print("Adding location_type column...")
                    conn.execute(text("ALTER TABLE user ADD COLUMN location_type VARCHAR(50) DEFAULT 'Urban'"))
                    conn.commit()
                    print("✓ Added location_type")
                
                try:
                    conn.execute(text("SELECT created_at FROM user LIMIT 1"))
                    print("✓ created_at already exists")
                except:
                    print("Adding created_at column...")
                    conn.execute(text("ALTER TABLE user ADD COLUMN created_at DATETIME"))
                    conn.commit()
                    print("✓ Added created_at")
                
                # Add new columns to UsageLog table
                try:
                    conn.execute(text("SELECT water_co2 FROM usage_log LIMIT 1"))
                    print("✓ water_co2 already exists")
                except:
                    print("Adding water_co2 column...")
                    conn.execute(text("ALTER TABLE usage_log ADD COLUMN water_co2 FLOAT DEFAULT 0"))
                    conn.commit()
                    print("✓ Added water_co2")
                
                try:
                    conn.execute(text("SELECT energy_co2 FROM usage_log LIMIT 1"))
                    print("✓ energy_co2 already exists")
                except:
                    print("Adding energy_co2 column...")
                    conn.execute(text("ALTER TABLE usage_log ADD COLUMN energy_co2 FLOAT DEFAULT 0"))
                    conn.commit()
                    print("✓ Added energy_co2")
                
                try:
                    conn.execute(text("SELECT waste_co2 FROM usage_log LIMIT 1"))
                    print("✓ waste_co2 already exists")
                except:
                    print("Adding waste_co2 column...")
                    conn.execute(text("ALTER TABLE usage_log ADD COLUMN waste_co2 FLOAT DEFAULT 0"))
                    conn.commit()
                    print("✓ Added waste_co2")
                
                print("\n✅ Database migration completed successfully!")
                print("You can now run your app with: python app.py")
                
        except Exception as e:
            print(f"\n❌ Migration failed: {e}")
            print("\nAlternative: Delete sdgos.db and restart fresh")
            print("WARNING: This will delete all existing data!")

if __name__ == "__main__":
    migrate_database()