
### 2. `scraper-style-guide/SKILL.md`

```markdown
# Scraper Style Guide SKILL

**Purpose:** Enforces coding style and conventions (PEP8, readability, maintainability). Use for all code generation.

## Rules
- Follow PEP8: 4-space indents, snake_case for variables/functions, PascalCase for classes.
- Add type hints to function signatures and return types for clarity and to leverage static checks.
- Write clear docstrings (one-liners for methods, block comments for complex logic).
- Limit line length to ~80-100 chars (break long expressions).
- Use f-strings for string formatting.
- Use list/dict comprehensions instead of verbose loops where appropriate.
- Commit to a code formatter (like Black or `yapf`) and linter (flake8) and fix all errors.
- Use **logging** (e.g. `logger.info(…)`) instead of prints; remove debug prints from final code.
- Handle exceptions explicitly (catch specific exceptions, not bare `except:`).
- Validate assumptions and assert invariants (e.g. `assert price >= 0` after parsing).

## Examples
- **Bad (inconsistent naming):**
  ```python
  def GetPrice():  # wrong: function name should be snake_case
      ...
