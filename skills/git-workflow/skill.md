
### 9. `git-workflow/SKILL.md`

```markdown
# Git Workflow SKILL

**Purpose:** Standardize the Git branching/commit process for collaborative development.

## Rules
- **Use feature branches:** Develop new features or fixes in their own branch (named descriptively, e.g. `feature/proxy-rotation`, `bugfix/timeout-handling`).  
- **Frequent commits:** Commit small, logical chunks with clear messages. Follow a conventional format like “\<type\>(\<scope\>): \<description\>” (e.g. `feat(crawler): add proxy retry logic`).  
- **Pull requests and code review:** Always open a PR for integration to main. PRs should have descriptions linking to issues and mention SKILL compliance.  
- **Branch protection:** Main branch should be protected with required status checks (e.g. lint/test) before merging.  
- **Issue tracking:** Reference issue numbers in commit/PR descriptions.  
- **Tag releases:** Optionally tag releases (`v1.0`, etc.) if deploying or packaging. Maintain a CHANGELOG.

## Examples
- **Good commit message:** `test(parser): add test for empty page result`  
- **Bad commit message:** `Fixed a lot of stuff` (too vague).  
- **Branch naming:** `feature/add-playwright` not `newbranch`.

## Do
- ✓ **Do** pull from main/rebase regularly to avoid large merge conflicts.  
- ✓ **Do** use `.gitignore` to exclude data files (logs, scraped dumps) and environment files.  
- ✓ **Do** update `requirements.txt` or `environment.yml` when adding dependencies.

## Avoid
- ✗ **Avoid** committing API keys or passwords; use `.env` or config that is **not** checked in.  
- ✗ **Avoid** force-pushing to shared branches.  
- ✗ **Avoid** large binary files in the repo (e.g. raw data, images); store them externally or ignore.

## Token-Saving Tips
- 📌 **Branch shorthand:** Refer to tasks by branch name (e.g. “Implement the feature on `branch X`”) so the LLM doesn’t need the full context again.  
- 📌 **Minimal context in prompts:** Tell the model only the needed file diff or commit message, since SKILL.md has already set the style conventions.  
- 📌 **Use PR templates:** Have a pull request template with checkboxes for tests, documentation, etc. The model can then just tick them off without restating rules.
