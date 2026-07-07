from asagus.services.formatting import DataFormatter

def test_formatter():
    phone = DataFormatter.format_phone("923211234567", "PK")
    print(f"DEBUG: phone={phone}")
    assert phone == "+92 321 1234567"
    assert DataFormatter.format_boolean("yes") == "✅"
    assert DataFormatter.format_boolean("no") == "❌"
    assert DataFormatter.format_score(0.83) == "83%"
    assert DataFormatter.format_url("https://www.google.com/") == "google.com"
    assert DataFormatter.format_country("PK") == "Pakistan"
    print("All tests passed!")

if __name__ == "__main__":
    test_formatter()
