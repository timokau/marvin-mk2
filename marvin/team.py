from datetime import date
from datetime import timedelta
import random
from typing import Any
from typing import Awaitable
from typing import Callable
from typing import Dict
from typing import Optional

from gidgethub import aiohttp as gh_aiohttp

from marvin import gh_util


class Member:
    def __init__(
        self,
        gh_name: str,
        request_allowed: Callable[[gh_aiohttp.GitHubAPI, str], Awaitable[bool]],
        can_merge: bool = False,
    ):
        self.gh_name = gh_name
        self.request_allowed = request_allowed
        self.can_merge = can_merge


async def fetch_gist_content(gh: gh_aiohttp.GitHubAPI, gist_id: str) -> str:
    """Fetch the content of a one-file github gist using the API."""
    # Not authenticated on purpose
    # https://github.community/t/github-apps-gist-api/13806. This may lead to
    # rate limiting issues in the future.
    gist_response = await gh.getitem(f"https://api.github.com/gists/{gist_id}")
    # We only support one file per gist, just pick the first one
    gist_file = list(gist_response["files"].values())[0]
    return gist_file["content"]


def active_prs_below_limit(
    user: str, days: int, limit: int
) -> Callable[[gh_aiohttp.GitHubAPI, str], Awaitable[bool]]:
    """Determine whether a given active PR limit over a timeframe has already been reached.

    This searches GitHub for recently active nixpkgs PRs the user is involved
    in (ignoring any activity after the PR was merged) and compares the number
    of results to a limit. This is useful when you want to only get a request
    for new reviews when your current open-source work "plate" is not yet full.
    """

    async def decision_function(gh: gh_aiohttp.GitHubAPI, token: str) -> bool:
        # days-1 since today is automatically counted
        timeframe_start = (date.today() - timedelta(days=days - 1)).strftime("%Y-%m-%d")
        num_results = await gh_util.num_search_results(
            gh,
            token,
            query_parameters=[
                "repo:NixOS/nixpkgs",
                f"involves:{user}",
                f"updated:>={timeframe_start}",
                f"-merged:<{timeframe_start}",
            ],
        )
        return num_results < limit

    return decision_function


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
    Member(
        gh_name="timokau",
        request_allowed=gist_controlled("5f50d3eab2a14b77dbdb65d2bb2df544"),
        can_merge=True,
    ),
    Member(
        gh_name="timokau",
        request_allowed=active_prs_below_limit("timokau", days=1, limit=1),
    ),
    Member(
        gh_name="ryantm",
        request_allowed=active_prs_below_limit("ryantm", days=1, limit=1),
    ),
    Member(
        gh_name="fgaz", request_allowed=active_prs_below_limit("fgaz", days=5, limit=7),
    ),
    Member(
        gh_name="glittershark",
        request_allowed=active_prs_below_limit("glittershark", days=7, limit=2),
    ),
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
