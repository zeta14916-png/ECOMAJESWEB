---
name: Streamlit (non-Node app) in artifact-router mode
description: How to make a repo-root Streamlit/Python app previewable + deployable when the repl uses application-router mode
---

# Serving a repo-root Streamlit app through the artifact router

**Context/Why:** This repl uses `[deployment] router = "application"` in `.replit`. In that mode BOTH the dev preview and deployment go through the router at `localhost:80`, which only serves paths that belong to a registered artifact. The repo-root Streamlit app was healthy on port 5000 but the router returned its dark "404 — no previewable artifacts" page at `/` (looks blank). CORS/XSRF tweaks alone do NOT fix this — the root path must be a registered artifact.

**The fix (routing):** Register the app as a `web` artifact at `previewPath = "/"`.
- `createArtifact` has NO python/streamlit type, so hand-create `artifacts/streamlit/.replit-artifact/artifact.toml` via bash (the write/edit tools are guarded against writing `artifact.toml` directly). Then validate with `verifyAndReplaceArtifactToml({tempFilePath, artifactTomlPath})` (it requires the target `artifact.toml` to already exist; writing a sibling `artifact.edit.toml` and pointing tempFilePath at it works).
- After a successful `verifyAndReplaceArtifactToml`, the artifact shows in `listArtifacts()` and the router picks up the new `/` route WITHOUT a manual router restart.

**How to apply — cwd gotcha:** The auto-generated artifact workflow runs from the ARTIFACT dir (`artifacts/streamlit`), not the repo root, so `streamlit run app.py` fails with "File does not exist: app.py". Run commands must cd to repo root:
- dev `run = "cd /home/runner/workspace && streamlit run app.py --server.port 5000"`
- prod `args = ["bash","-lc","cd /home/runner/workspace && exec streamlit run app.py --server.port 5000 --server.address 0.0.0.0 --server.headless true"]`
- `localPort` must equal the `--server.port` (5000). Health startup path `/_stcore/health`.

**How to apply — one workflow only:** A repl-native `[workflows]` entry in `.replit` (e.g. legacy "Streamlit App") AND the artifact's auto-generated workflow both bind 5000 and collide on restart. Remove the legacy one with `removeWorkflow` (it clears the `.replit [workflows]` entry) and let the single artifact-managed workflow own 5000.

**Security note:** Once served same-origin through the router at `/`, Streamlit does NOT need `enableCORS=false`/`enableXsrfProtection=false`. Leave XSRF protection ON in `.streamlit/config.toml`.
