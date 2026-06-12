"""
Direct email test - sender account DB se uthao aur test email bhejo.
Run: python test_email.py
"""
import asyncio
import sys
import smtplib
import ssl
from sqlalchemy import select
from database import AsyncSessionLocal
from models import SenderAccount
from crypto import decrypt_password

async def test_send():
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(SenderAccount))
        senders = result.scalars().all()

        if not senders:
            print("[FAIL] Koi sender account nahi mila DB mein!")
            print("   Pehle Senders page pe account add karo.")
            return

        print(f"[OK] {len(senders)} sender(s) mila:")
        for s in senders:
            print(f"   [{s.id}] {s.email} | host={s.smtp_host}:{s.smtp_port} | tls={s.smtp_use_tls} | active={s.is_active}")

        # Pehla active sender use karo
        sender = next((s for s in senders if s.is_active), senders[0])
        print(f"\n[..] Testing sender: {sender.email}")

        try:
            password = decrypt_password(sender.smtp_password_enc)
            print(f"[OK] Password decrypt hua")
        except Exception as e:
            print(f"[FAIL] Password decrypt fail: {e}")
            return

        # SMTP connection test
        to_email = sender.email  # apne aap ko bhejo
        subject = "ASAGUS Test Email"
        body = f"Ye ek test email hai ASAGUS Mailer system se.\n\nSender: {sender.email}\nHost: {sender.smtp_host}:{sender.smtp_port}"

        print(f"\n[..] SMTP connect kar raha hoon {sender.smtp_host}:{sender.smtp_port} ...")

        try:
            ctx = ssl.create_default_context()
            if sender.smtp_use_tls:
                with smtplib.SMTP(sender.smtp_host, sender.smtp_port, timeout=30) as smtp:
                    smtp.ehlo()
                    print("[OK] EHLO OK")
                    smtp.starttls(context=ctx)
                    print("[OK] STARTTLS OK")
                    smtp.ehlo()
                    smtp.login(sender.email, password)
                    print("[OK] Login OK")
                    smtp.sendmail(sender.email, to_email,
                        f"From: {sender.email}\nTo: {to_email}\nSubject: {subject}\n\n{body}")
                    print(f"[OK] EMAIL BHEJ DIYA! Check karo: {to_email}")
            else:
                with smtplib.SMTP_SSL(sender.smtp_host, sender.smtp_port, context=ctx, timeout=30) as smtp:
                    smtp.ehlo()
                    print("[OK] EHLO OK")
                    smtp.login(sender.email, password)
                    print("[OK] Login OK")
                    smtp.sendmail(sender.email, to_email,
                        f"From: {sender.email}\nTo: {to_email}\nSubject: {subject}\n\n{body}")
                    print(f"[OK] EMAIL BHEJ DIYA! Check karo: {to_email}")

        except smtplib.SMTPAuthenticationError as e:
            print(f"[FAIL] AUTH FAIL: {e}")
            print("   Gmail use kar rahe ho? App Password chahiye, normal password nahi.")
            print("   Jao: https://myaccount.google.com/apppasswords")
        except smtplib.SMTPConnectError as e:
            print(f"[FAIL] CONNECT FAIL: {e}")
            print("   Port ya host galat hai, ya firewall block kar raha hai.")
        except smtplib.SMTPException as e:
            print(f"[FAIL] SMTP ERROR: {e}")
        except Exception as e:
            print(f"[FAIL] ERROR: {type(e).__name__}: {e}")

if __name__ == "__main__":
    # .env load karo
    try:
        from dotenv import load_dotenv
        import os
        env_path = os.path.join(os.path.dirname(__file__), '..', '..', '.env')
        load_dotenv(env_path)
        if not os.environ.get("SECRET_KEY"):
            # Try local .env
            load_dotenv(os.path.join(os.path.dirname(__file__), '.env'))
    except ImportError:
        pass

    asyncio.run(test_send())
