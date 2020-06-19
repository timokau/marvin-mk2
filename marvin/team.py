import random
from typing import Awaitable
from typing import Callable
from typing import Optional

from gidgethub import aiohttp as gh_aiohttp


class Member:
    def __init__(
        self,
        gh_name: str,
        request_allowed: Callable[[gh_aiohttp.GitHubAPI], Awaitable[bool]],
        can_merge: bool = False,
    ):
        self.gh_name = gh_name
        self.request_allowed = request_allowed
        self.can_merge = can_merge


async def fetch_gist_content(gh: gh_aiohttp.GitHubAPI, gist_id: str) -> str:
    """Fetch the content of a one-file github gist using the API."""
    gist_response = await gh.getitem(f"https://api.github.com/gists/{gist_id}")
    # We only support one file per gist, just pick the first one
    gist_file = list(gist_response["files"].values())[0]
    return gist_file["content"]


def gist_controlled(gist_id: str,) -> Callable[[gh_aiohttp.GitHubAPI], Awaitable[bool]]:
    """Make a decision function that defers its decision to a github gist.

    This enables decentralized control. People can decide to enable or disable
    review request at any time, without having to go through a PR and deploy
    process.
    """

    async def control_function(gh: gh_aiohttp.GitHubAPI) -> bool:
        return (await fetch_gist_content(gh, gist_id)).strip() == "enable"

    return control_function


TEAM = {
    Member(
        gh_name="timokau",
        request_allowed=gist_controlled("5f50d3eab2a14b77dbdb65d2bb2df544"),
        can_merge=True,
    ),
}


async def get_reviewer(
    gh: gh_aiohttp.GitHubAPI, merge_permission_needed: bool
) -> Optional[str]:
    """Attempt to find a random reviewer that is currently allowing requests."""

    candidates = TEAM
    if merge_permission_needed:
        candidates = {member for member in candidates if member.can_merge}

    print(
        f"Selecting reviewer from candidates: {[candidate.gh_name for candidate in candidates]}"
    )

    # Go through candidates in random order and return the first that is
    # willing to review.
    for candidate in random.sample(candidates, len(candidates)):
        print(f"Testing {candidate.gh_name}")
        if await candidate.request_allowed(gh):
            return candidate.gh_name

    return None
