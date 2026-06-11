import asyncio
import shlex
from typing import Tuple

# keep git imports but handle absence of valid repo gracefully
from git import Repo
from git.exc import GitCommandError, InvalidGitRepositoryError

import config

from ..logging import LOGGER


def install_req(cmd: str) -> Tuple[str, str, int, int]:
    async def install_requirements():
        args = shlex.split(cmd)
        process = await asyncio.create_subprocess_exec(
            *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await process.communicate()
        return (
            stdout.decode("utf-8", "replace").strip(),
            stderr.decode("utf-8", "replace").strip(),
            process.returncode,
            process.pid,
        )

    return asyncio.get_event_loop().run_until_complete(install_requirements())


def git():
    """
    Safe git updater:
    - Tries to use Repo() for VPS/local environments.
    - If repository is invalid or required refs are missing (Heroku), it logs and returns without crashing.
    This preserves update behaviour where possible, and prevents crashes on Heroku (no .git).
    """
    REPO_LINK = getattr(config, "UPSTREAM_REPO", None)
    if not REPO_LINK:
        LOGGER(__name__).info("No UPSTREAM_REPO configured; skipping git updates.")
        return

    # Build authenticated URL if token present
    if getattr(config, "GIT_TOKEN", None):
        try:
            GIT_USERNAME = REPO_LINK.split("com/")[1].split("/")[0]
            TEMP_REPO = REPO_LINK.split("https://")[1]
            UPSTREAM_REPO = f"https://{GIT_USERNAME}:{config.GIT_TOKEN}@{TEMP_REPO}"
        except Exception:
            UPSTREAM_REPO = config.UPSTREAM_REPO
    else:
        UPSTREAM_REPO = config.UPSTREAM_REPO

    try:
        repo = Repo()
    except InvalidGitRepositoryError:
        # No .git folder (typical on Heroku) — do not attempt to initialize or access refs
        LOGGER(__name__).info("No valid git repository found (likely Heroku). Skipping git updates.")
        return
    except Exception as e:
        LOGGER(__name__).warning(f"Unexpected error while opening Repo(): {e!r}. Skipping git updates.")
        return

    LOGGER(__name__).info("Git repository detected — attempting update check (VPS mode).")

    try:
        # ensure origin remote exists
        try:
            origin = repo.remotes.origin
        except Exception:
            origin = repo.create_remote("origin", UPSTREAM_REPO)

        # fetch origin safely
        try:
            origin.fetch()
        except Exception as e:
            LOGGER(__name__).warning(f"Failed to fetch from origin: {e!r}")

        branch = getattr(config, "UPSTREAM_BRANCH", "master")

        # Try to safely access the remote branch reference
        try:
            remote_ref = None
            # origin.refs may be a list of refs; try to find matching one
            for r in getattr(origin, "refs", []):
                # r.name can be 'origin/master' or similar, r.remote_head may exist
                if getattr(r, "name", "").endswith("/" + branch) or getattr(r, "remote_head", "") == branch:
                    remote_ref = r
                    break
            # if not found, try direct indexing (may raise IndexError)
            if remote_ref is None:
                try:
                    remote_ref = origin.refs[branch]
                except Exception:
                    # as a final fallback, try FETCH_HEAD
                    remote_ref = None

            if remote_ref is None:
                LOGGER(__name__).warning(f"Upstream branch '{branch}' not found on origin. Skipping branch operations.")
                return

            # create local branch if missing
            if branch not in [h.name for h in repo.heads]:
                try:
                    repo.create_head(branch, remote_ref)
                except Exception as e:
                    LOGGER(__name__).warning(f"Could not create local head {branch}: {e!r}")

            # Set tracking and checkout
            try:
                repo.heads[branch].set_tracking_branch(remote_ref)
                repo.heads[branch].checkout(True)
            except Exception as e:
                LOGGER(__name__).warning(f"Failed to set tracking/checkout for {branch}: {e!r}")

            # Pull latest changes
            try:
                origin.pull(branch)
            except GitCommandError:
                try:
                    repo.git.reset("--hard", "FETCH_HEAD")
                except Exception as e:
                    LOGGER(__name__).warning(f"Failed to reset to FETCH_HEAD: {e!r}")

            # Install requirements after update (best effort)
            try:
                install_req("pip3 install --no-cache-dir -r requirements.txt")
            except Exception as e:
                LOGGER(__name__).warning(f"Failed to install requirements: {e!r}")

            LOGGER(__name__).info("Fetching updates from upstream repository (completed).")
        except Exception as e:
            LOGGER(__name__).warning(f"Error while working with origin refs: {e!r}. Aborting git update.")
            return

    except Exception as e:
        LOGGER(__name__).warning(f"Unexpected git update error: {e!r}")
        return
