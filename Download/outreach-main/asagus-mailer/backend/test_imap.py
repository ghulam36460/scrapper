"""
Test IMAP reply detection manually.
Run: python test_imap.py
"""
import asyncio
import os
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), '..', '..', '.env'))

from database import AsyncSessionLocal
from services.imap_service import poll_all_accounts
from sqlalchemy import select
from models import Reply, SenderAccount

async def test():
    print('Starting IMAP poll test...')
    
    async with AsyncSessionLocal() as db:
        # Check sender
        result = await db.execute(select(SenderAccount))
        senders = result.scalars().all()
        print(f'Found {len(senders)} sender(s):')
        for s in senders:
            print(f'  - {s.email} | IMAP: {s.imap_host}:{s.imap_port} | Active: {s.is_active}')
        
        # Check existing replies
        result = await db.execute(select(Reply))
        existing = result.scalars().all()
        print(f'\nExisting replies in DB: {len(existing)}')
        
    # Poll
    print('\nPolling IMAP for new replies...')
    try:
        await poll_all_accounts()
        print('Poll completed successfully!')
    except Exception as e:
        print(f'Poll failed: {type(e).__name__}: {e}')
        import traceback
        traceback.print_exc()
    
    # Check new replies
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Reply))
        all_replies = result.scalars().all()
        print(f'\nTotal replies after poll: {len(all_replies)}')
        
        if len(all_replies) > len(existing):
            print(f'NEW REPLIES FOUND: {len(all_replies) - len(existing)}')
            for r in all_replies[len(existing):]:
                print(f'  From: {r.from_email}')
                print(f'  Subject: {r.subject}')
                print(f'  Match: {r.match_method} (confidence: {r.match_confidence})')
                print(f'  Body preview: {r.body[:100]}...')
                print()
        else:
            print('No new replies detected.')
            print('\nTroubleshooting:')
            print('1. Check if reply email is in Gmail inbox (not spam)')
            print('2. Make sure reply is UNREAD')
            print('3. Check if IMAP password is correct')
            print('4. Try sending reply again and wait 1 minute')

asyncio.run(test())
