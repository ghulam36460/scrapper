"""
Run: python set_password.py
Directly saves Gmail App Password to DB with correct encryption key.
"""
import os, sys, sqlite3
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), '..', '..', '.env'))

key = os.environ.get('SECRET_KEY', '')
if not key:
    print('ERROR: SECRET_KEY not found in .env')
    sys.exit(1)

print('SECRET_KEY loaded, prefix:', key[:15])

from cryptography.fernet import Fernet
f = Fernet(key.encode())

new_pass = input('\nGmail App Password (16 chars, no spaces): ').strip()
if len(new_pass) < 10:
    print('Too short, aborted.')
    sys.exit(1)

enc = f.encrypt(new_pass.encode()).decode()

db_path = (Path(__file__).resolve().parent / 'asagus.db').resolve()
if not db_path.exists():
    db_path = (Path(__file__).resolve().parent.parent / 'asagus.db').resolve()
conn = sqlite3.connect(str(db_path))
conn.execute('UPDATE sender_accounts SET smtp_password_enc=?, imap_password_enc=? WHERE id=1', (enc, enc))
conn.commit()

# Verify
r = conn.execute('SELECT smtp_password_enc FROM sender_accounts WHERE id=1').fetchone()
dec = f.decrypt(r[0].encode()).decode()
conn.close()

if dec == new_pass:
    print('SUCCESS! Password saved and verified correctly.')
    print('Ab campaign run karo - emails jayenge.')
else:
    print('ERROR: Verification failed!')
