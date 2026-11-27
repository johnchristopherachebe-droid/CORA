# Integration guide

## 1. Copy the brain foundation

Copy the files in `cora/` to the CORA project root (or adjust Python import paths consistently). Preserve the existing `cora_memory.py`; the brain foundation imports `looks_like_secret` from it.

The SQL file `cora/001_brain_foundation.sql` is the reference migration. Confirm the actual migration path expected by `cora_brain_db.py` before running it against production.

## 2. Add the extension modules

Keep `cora/` as a Python package. The modules are intentionally provider-agnostic:
- `research_workspace.py` expects injected search and optional video discovery functions.
- `local_model.py` expects an operator-configured OpenAI-compatible endpoint.
- `upgrade_manager.py` must point to a disposable development workspace, never the live source tree.
- `security.py` requires a strong `CORA_APPROVAL_SECRET` (32+ characters).

## 3. Mount the API router

Example (adapt to the project's actual dependency and database patterns):

```python
from cora.extensions_api import build_router
from cora.research_workspace import ResearchWorkspace
from cora.upgrade_manager import UpgradeManager

research = ResearchWorkspace(
    db_path="cora_research.db",
    search_fn=your_existing_search_function,
    video_fn=your_existing_video_search_function,
)
upgrades = UpgradeManager(
    workspace="/srv/cora-dev-workspace",
    proposal_dir="/srv/cora-dev-workspace/.cora-proposals",
)
app.include_router(build_router(
    require_owner=your_existing_owner_auth_dependency,
    research_workspace=research,
    upgrade_manager=upgrades,
))
```

Do not replace `your_existing_owner_auth_dependency` with a user-supplied name or a boolean from an HTTP request. It must validate the authenticated session and return the authenticated owner identity.

For applying a proposal, call `ApprovalAuthority.verify()` server-side using an approval token issued only after re-authentication. Then call `UpgradeManager.approve_and_apply()` only against the isolated workspace. This bundle intentionally does not expose an apply endpoint.

## 4. Local model

Set `CORA_LOCAL_MODEL_URL` to an operator-managed local endpoint, `CORA_LOCAL_MODEL_NAME` to its model identifier, and optionally `CORA_LOCAL_MODEL_API_KEY`. For non-local hosts use HTTPS. A model server must be deployed separately; Vercel serverless functions are not a suitable place to host persistent model weights.

## 5. Interface

Copy `public/cora-control-centre.html` to a route or embed its sections in the existing CORA dashboard. It is a preview, not a replacement for the current dashboard. The research action expects `/cora/research` and an authenticated same-origin session.

## 6. Verify before deployment

1. Run the new extension tests.
2. Run the existing Phase 1 tests in the complete CORA repository with its real `cora_memory.py`.
3. Test SQLite and PostgreSQL separately.
4. Test the router with authentication and provider fakes.
5. Review path restrictions and deployment workspace isolation.
6. Run the complete existing CORA regression suite.
7. Back up production data and use a staging deployment first.
