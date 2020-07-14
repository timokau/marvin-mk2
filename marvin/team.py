from datetime import datetime
from datetime import timedelta
from datetime import timezone
import random
from typing import Any
from typing import Awaitable
from typing import Callable
from typing import Dict
from typing import Optional

from gidgethub import aiohttp as gh_aiohttp

from marvin import gh_util


class Reviewer:
    def __init__(
        self, gh_name: str, can_merge: bool = False,
    ):
        self.gh_name = gh_name
        self.can_merge = can_merge

    async def request_allowed(self, gh: gh_aiohttp.GitHubAPI, token: str) -> bool:
        return True


class ActivityLimitedReviewer(Reviewer):
    def __init__(self, gh_name: str, days: int, limit: int, can_merge: bool = False):
        super().__init__(gh_name, can_merge)
        self.days = days
        self.limit = limit
        self.cached_no_until = datetime.now(timezone.utc)

    async def request_allowed(self, gh: gh_aiohttp.GitHubAPI, token: str) -> bool:
        """Determine whether a given active PR limit over a timeframe has already been reached.

        This searches GitHub for recently active nixpkgs PRs the user is involved
        in (ignoring any activity after the PR was merged) and compares the number
        of results to a limit. This is useful when you want to only get a request
        for new reviews when your current open-source work "plate" is not yet full.
        """
        if datetime.now(timezone.utc) < self.cached_no_until:
            print(
                f"Cached: Limit ({self.limit}/{self.days}d) exceeded until {self.cached_no_until}."
            )
            return False

        timeframe_start = (
            datetime.now(timezone.utc) - timedelta(days=self.days)
        ).strftime("%Y-%m-%dT%H:%M:%S+00:00")
        search_results = gh_util.search_issues(
            gh,
            token,
            query_parameters=[
                "repo:NixOS/nixpkgs",
                f"involves:{self.gh_name}",
                f"updated:>={timeframe_start}",
                f"-merged:<{timeframe_start}",
            ],
        )
        cur_issue = 0
        async for issue in search_results:
            cur_issue += 1
            if cur_issue == self.limit:
                last_updated = datetime.strptime(
                    issue["updated_at"], "%Y-%m-%dT%H:%M:%S%z"
                )
                # Remember when the PR that pushed us over the limit will "fall
                # out" of the time window.
                self.cached_no_until = last_updated + timedelta(days=self.days)
                print(
                    f"Limit ({self.limit}/{self.days}d) exceeded until {self.cached_no_until}."
                )
                return False

        return True


async def fetch_gist_content(gh: gh_aiohttp.GitHubAPI, gist_id: str) -> str:
    """Fetch the content of a one-file github gist using the API."""
    # Not authenticated on purpose
    # https://github.community/t/github-apps-gist-api/13806. This may lead to
    # rate limiting issues in the future.
    gist_response = await gh.getitem(f"https://api.github.com/gists/{gist_id}")
    # We only support one file per gist, just pick the first one
    gist_file = list(gist_response["files"].values())[0]
    return gist_file["content"]


def gist_controlled(
    gist_id: str,
) -> Callable[[gh_aiohttp.GitHubAPI, str], Awaitable[bool]]:
    """Make a decision function that defers its decision to a github gist.

    This enables decentralized control. People can decide to enable or disable
    review request at any time, without having to go through a PR and deploy
    process.
    """

    async def control_function(gh: gh_aiohttp.GitHubAPI, token: str) -> bool:
        return (await fetch_gist_content(gh, gist_id)).strip() == "enable"

    return control_function


TEAM = {
    ActivityLimitedReviewer(
        gh_name="timokau",
        days=1,
        limit=100,  # practically no limit on merge for now
        can_merge=True,
    ),
    ActivityLimitedReviewer(gh_name="timokau", days=1, limit=1),
    ActivityLimitedReviewer(gh_name="ryantm", days=1, limit=1),
    ActivityLimitedReviewer(gh_name="fgaz", days=5, limit=5),
    ActivityLimitedReviewer(gh_name="glittershark", days=7, limit=2),
    ActivityLimitedReviewer(gh_name="turion", days=7, limit=3),
    ActivityLimitedReviewer(gh_name="symphorien", days=7, limit=3),
}


async def get_reviewer(
    gh: gh_aiohttp.GitHubAPI,
    token: str,
    issue: Dict[str, Any],
    merge_permission_needed: bool,
) -> Optional[str]:
    """Attempt to find a random reviewer that is currently allowing requests."""

    candidates = TEAM
    if merge_permission_needed:
        candidates = {member for member in candidates if member.can_merge}
    else:
        # For now people should sign up with two different "Memeber" listings
        # if they want to review both kinds of PRs. This allows for different
        # rate limits.
        candidates = {member for member in candidates if not member.can_merge}

    print(
        f"Selecting reviewer from candidates: {[candidate.gh_name for candidate in candidates]}"
    )

    pr_author_login = issue["user"]["login"]

    # Go through candidates in random order and return the first that is
    # willing to review.
    for candidate in random.sample(candidates, len(candidates)):
        if candidate.gh_name == pr_author_login:
            print(f"Skipping pr author {pr_author_login}")
            continue
        print(f"Testing {candidate.gh_name}")
        if await candidate.request_allowed(gh, token):
            return candidate.gh_name

    return None
