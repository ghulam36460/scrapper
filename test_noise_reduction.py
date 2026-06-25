import re
import json

# Sample of corrupted data provided by user
raw_records = [
    {
        "name": "Best Restaurants in Lahore | 2026 Top 10 List",
        "phone": "9.23005E+11",
        "email": "info@thecarnivore.com",
        "rating": "4.7"
    },
    {
        "name": "Home | Bundu Khan",
        "phone": "42111444411",
        "email": "info@bundukhan.pk",
        "rating": None
    },
    {
        "name": "Restaurants in Lahore â€“ Restaurants in Lahore",
        "phone": "1   2   3",
        "email": "st@s.wp",
        "rating": None
    },
    {
        "name": "ReserveKaru",
        "phone": "5.0                                                                ( 2",
        "email": "reservekaru@gmail.com",
        "rating": "5.0"
    },
    {
        "name": "Restaurants in Lahore - Pakistan.",
        "phone": "9.23219E+13",
        "email": "navig@or.useragent",
        "rating": None
    }
]

def test_noise_reproduction():
    print("--- Phase 1: Noise Reproduction Test ---")
    for i, record in enumerate(raw_records):
        print(f"\nRecord {i+1}: {record['name']}")
        
        # Check Phone
        phone = str(record['phone'])
        if 'E+' in phone or len(phone.split()) > 1:
            print(f"  [!] Noise detected in Phone: {phone}")
            
        # Check Email
        email = record['email']
        if 'useragent' in email or len(email.split('@')[0]) < 3:
            print(f"  [!] Noise detected in Email: {email}")
            
        # Check Name/Encoding
        name = record['name']
        if 'â€“' in name:
            print(f"  [!] Encoding issue detected in Name: {name}")

if __name__ == "__main__":
    test_noise_reproduction()
