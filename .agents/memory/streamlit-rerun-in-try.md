---
name: st.rerun() inside try/except
description: Streamlit rerun raises an exception that a broad except will swallow
---

`st.rerun()` works by raising `RerunException`. If you call it inside a `try:` block whose `except Exception:` catches broadly, the rerun is swallowed and the page silently does not rerun.

**Why:** we needed "run import in try → on failure restore backup → then rerun". Putting `st.rerun()` after the try/except (never inside) keeps failure handling and rerun separate.

**How to apply:** in any Streamlit flow that does risky work in try/except and then reruns, set the outcome into `st.session_state` inside the try/except and call `st.rerun()` once, AFTER the block — never inside the try.
