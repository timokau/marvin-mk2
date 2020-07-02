from datetime import datetime
from datetime import timezone
from typing import Any

from gidgethub.aiohttp import GitHubAPI

from marvin import gh_util
from marvin.command_router import CommandRouter
from marvin.status import set_issue_status

command_router = CommandRouter()

AWAITING_REVIEWER_TIMEOUT_SECONDS = 60 * 60 * 24 * 3  # three days


async def timeout_awaiting_reviewer(
    gh: GitHubAPI, token: str, repository_name: str
) -> None:
    print("Timing out awaiting_reviewer PRs")
    search_results = gh_util.search_issues(
        gh,
        token,
        query_parameters=[
            f"repo:{repository_name}",
            "label:awaiting_reviewer",
            "sort:updated-asc",  # stale first
        ],
    )
    async for issue in search_results:
        last_updated = datetime.strptime(issue["updated_at"], "%Y-%m-%dT%H:%M:%S%z")
        age = datetime.now(timezone.utc) - last_updated
        if age.total_seconds() < AWAITING_REVIEWER_TIMEOUT_SECONDS:
            break

        print(
            f"awaiting_reviewer -> needs_reviewer: #{issue['number']} ({issue['title']})"
        )
        await set_issue_status(issue, "needs_reviewer", gh, token)


@command_router.register_command("/marvin triage")
async def run_triage(gh: GitHubAPI, token: str, **kwargs: Any) -> None:
    repositories = await gh_util.get_installation_repositories(gh, token)
    for repository in repositories:
        repository_name = repository["full_name"]
        print(f"Running triage on {repository_name}")
        await timeout_awaiting_reviewer(gh, token, repository_name)
