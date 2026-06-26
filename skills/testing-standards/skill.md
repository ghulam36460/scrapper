
### 8. `testing-standards/SKILL.md`

```markdown
# Testing Standards SKILL

**Purpose:** Define how to write and run tests for the scraper code.

## Rules
- **Use Pytest (or equivalent):** Write unit tests for each function/module and run via pytest (or your chosen framework).  
- **Mock external calls:** Do not perform real web requests in unit tests. Use `pytest-mock` or `unittest.mock.patch` to simulate HTTP responses.  
- **Test edge cases:** Include tests for empty results, malformed HTML, network errors (simulate with mocks).  
- **Integration tests:** Write end-to-end tests that run the full pipeline on a small, controlled dataset (e.g. a saved HTML page or a test server).  
- **Continuous integration:** Run tests on each commit (e.g. via GitHub Actions). Require tests to pass before merging.  
- **Code coverage:** Aim for high coverage on parsing and data-cleaning functions. Use a tool (e.g. `coverage.py`) to enforce.

## Examples
- **Unit test with mock:**  
  ```python
  from scraper import get_page_content
  import pytest
  from unittest.mock import patch

  @patch("scraper.requests.get")
  def test_get_page_content_success(mock_get):
      mock_response = mock_get.return_value
      mock_response.content = b"<html><body>Hi</body></html>"
      mock_response.status_code = 200
      result = get_page_content("http://example.com")
      assert result == "<html><body>Hi</body></html>"
