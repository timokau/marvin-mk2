from typing import Any
from typing import Dict
from typing import List

from gidgethub.aiohttp import GitHubAPI


async def search_issues(
    gh: GitHubAPI, token: str, query_parameters: List[str],
) -> Dict[str, Any]:
    """Search github issues and pull requests.

    As documented here:
    https://developer.github.com/v3/search/#search-issues-and-pull-requests

    A common query string is likely "repo:NixOS/nixpkgs".
    """
    query = "+".join(query_parameters)
    return await gh.getitem(
        f"https://api.github.com/search/issues?q={query}", oauth_token=token
    )
