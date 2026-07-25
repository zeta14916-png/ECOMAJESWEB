---
name: Imported Python dependencies
description: Runtime dependency availability for imported Python projects
---

Imported Python projects can have a complete `requirements.txt` while the active
workflow environment still lacks those packages. A workflow failure such as
`No module named streamlit` is an environment setup issue, not necessarily an
application defect.

**Why:** The first runtime check of this imported ECOMAJES project failed before
the app executed because Streamlit was not installed, even though the required
packages were declared.

**How to apply:** When an imported Python workflow fails at module import time,
compare the missing module with `requirements.txt`, install the declared
dependency through the package-management flow, then restart the workflow
before debugging application code. Keep dependency files deduplicated.