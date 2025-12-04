---
description: Automate Phase 4 (Git Ops) validation and commit
---

1. Validate Phase 4 (Git Ops Status)
// turbo
powershell -ExecutionPolicy Bypass -File scripts/validate-phase-4.ps1

2. If validation passes, prompt user for commit message and commit (This step is manual for safety)
echo "Validation passed. Please run: git commit -m 'your message' && git push"
