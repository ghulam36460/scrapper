"""
Fix IMAP passwords for all senders.
Run: python fix_imap.py SENDER_ID APP_PASSWORD

Example:
  python fix_imap.py 1 abcdefghijklmnop
  python fix_imap.py 2 xyzkabcdefghijkl
"""
import os, sys, sqlite3
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), '..', '..', '.env'))

key = os.environ.get('SECRET_KEY', '')
if not key:
    print('ERROR: SECRET_KEY not found')
    sys.exit(1)

if len(sys.argv) < 3:
    print('Usage: python fix_imap.py SENDER_ID APP_PASSWORD')
    print('\nCurrent senders:')
    conn = sqlite3.connect('asagus.db')
    for r in conn.execute('SELECT id, email FROM sender_accounts').fetchall():
        print(f'  [{r[0]}] {r[1]}')
    conn.close()
    sys.exit(1)

sender_id = int(sys.argv[1])
new_pass = sys.argv[2].strip().replace(' ', '')

print(f'Setting password for sender ID {sender_id}')
print(f'Password length: {len(new_pass)}')

from cryptography.fernet import Fernet
f = Fernet(key.encode())
enc = f.encrypt(new_pass.encode()).decode()

db_path = (Path(__file__).resolve().parent / 'asagus.db').resolve()
if not db_path.exists():
    db_path = (Path(__file__).resolve().parent.parent / 'asagus.db').resolve()
conn = sqlite3.connect(str(db_path))

# Get sender email
r = conn.execute('SELECT email FROM sender_accounts WHERE id=?', (sender_id,)).fetchone()
if not r:
    print(f'ERROR: Sender ID {sender_id} not found')
    conn.close()
    sys.exit(1)

email = r[0]
print(f'Sender: {email}')

# Update both SMTP and IMAP passwords
conn.execute('UPDATE sender_accounts SET smtp_password_enc=?, imap_password_enc=? WHERE id=?', 
             (enc, enc, sender_id))
conn.commit()

# Verify
r = conn.execute('SELECT smtp_password_enc FROM sender_accounts WHERE id=?', (sender_id,)).fetchone()
dec = f.decrypt(r[0].encode()).decode()
conn.close()

if dec == new_pass:
    print('SUCCESS! Password saved and verified.')
    print(f'Now test IMAP: python test_imap.py')
else:
    print('ERROR: Verification failed!')
