import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.database import engine
from sqlalchemy import text

def fix_db():
    with engine.connect() as conn:
        conn.execute(text("ALTER TABLE subscriptions ADD COLUMN IF NOT EXISTS individual_id INTEGER REFERENCES individuals(id) ON DELETE CASCADE;"))
        conn.execute(text("ALTER TABLE email_logs ADD COLUMN IF NOT EXISTS individual_id INTEGER REFERENCES individuals(id) ON DELETE CASCADE;"))
        conn.commit()
        print("DB fixed")

if __name__ == "__main__":
    fix_db()
