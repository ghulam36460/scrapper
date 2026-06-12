"""
Sender account ka password dobara set karo current SECRET_KEY se.
Run: python fix_password.py
"""
import os
import sys
import asyncio
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), '..', '..', '.env'))
load_dotenv(os.path.join(os.path.dirname(__file__), '.env'))

from sqlalchemy import select
from database import AsyncSessionLocal
from models import SenderAccount
from crypto import encrypt_password, decrypt_password

async def fix():
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(SenderAccount))
        senders = result.scalars().all()

        if not senders:
            print("[FAIL] Koi sender nahi mila.")
            return

        for s in senders:
            print(f"\nSender: {s.email}")
            # Test if current password works
            try:
                decrypt_password(s.smtp_password_enc)
                print("  SMTP password: OK (already works)")
            except Exception:
                print("  SMTP password: BROKEN - naya password enter karo")
                new_pass = input("  Naya SMTP/App Password: ").strip()
                if new_pass:
                    s.smtp_password_enc = encrypt_password(new_pass)
                    print("  SMTP password updated.")

            try:
                decrypt_password(s.imap_password_enc)
                print("  IMAP password: OK (already works)")
            except Exception:
                print("  IMAP password: BROKEN - naya password enter karo (Enter dabao skip karne ke liye)")
                new_pass = input("  Naya IMAP Password (ya Enter skip): ").strip()
                if new_pass:
                    s.imap_password_enc = encrypt_password(new_pass)
                    print("  IMAP password updated.")
                else:
                    # Same as SMTP
                    try:
                        smtp_pass = decrypt_password(s.smtp_password_enc)
                        s.imap_password_enc = encrypt_password(smtp_pass)
                        print("  IMAP password: SMTP wala use kar liya.")
                    except Exception:
                        pass

        await db.commit()
        print("\n[OK] Done! Ab campaign run karo.")

asyncio.run(fix())
