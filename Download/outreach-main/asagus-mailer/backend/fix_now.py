"""
Run: python fix_now.py YOUR_APP_PASSWORD
Example: python fix_now.py abcdefghijklmnop
"""
import os, sys, sqlite3
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), '..', '..', '.env'))

key = os.environ.get('SECRET_KEY', '')
if not key:
    print('ERROR: SECRET_KEY not found')
    sys.exit(1)

if len(sys.argv) < 2:
    print('Usage: python fix_now.py YOUR_APP_PASSWORD')
    print('Example: python fix_now.py abcdefghijklmnop')
    sys.exit(1)

new_pass = sys.argv[1].strip().replace(' ', '')
print('Password length:', len(new_pass))

from cryptography.fernet import Fernet
f = Fernet(key.encode())
enc = f.encrypt(new_pass.encode()).decode()

db_path = (Path(__file__).resolve().parent / 'asagus.db').resolve()
if not db_path.exists():
    db_path = (Path(__file__).resolve().parent.parent / 'asagus.db').resolve()
conn = sqlite3.connect(str(db_path))
conn.execute('UPDATE sender_accounts SET smtp_password_enc=?, imap_password_enc=? WHERE id=1', (enc, enc))

# Also reset campaign and leads
conn.execute("UPDATE campaigns SET status='draft', pause_reason=NULL, sent_count=0, current_lead_index=0, total_targets=0, started_at=NULL, completed_at=NULL")
conn.execute("UPDATE leads SET status='pending'")

from datetime import date
conn.execute('UPDATE sender_accounts SET sent_today=0, last_reset_date=? WHERE id=1', (str(date.today()),))
conn.commit()

# Verify
r = conn.execute('SELECT smtp_password_enc FROM sender_accounts WHERE id=1').fetchone()
dec = f.decrypt(r[0].encode()).decode()
conn.close()

if dec == new_pass:
    print('SUCCESS! Password saved correctly.')
    print('Campaign reset to draft, leads reset to pending.')
    print('Ab backend restart karo phir campaign Run karo.')
else:
    print('ERROR: Mismatch!')
