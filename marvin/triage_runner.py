import asyncio
from typing import Dict
from typing import Optional

import aiohttp
from gidgethub import apps
from gidgethub.aiohttp import GitHubAPI

from marvin import constants
from marvin import triage


class TriageRunner:
    """Run regular triage.

    Triage is run at least once every max_delay_seconds or whenever requested.
    """

    def __init__(
        self,
        installation_id: str,
        gh_app_id: str,
        gh_private_key: str,
        min_delay_seconds: int,
        max_delay_seconds: int,
    ) -> None:
        self.installation_id = installation_id
        self.gh_app_id = gh_app_id
        self.gh_private_key = gh_private_key
        self.max_delay_seconds = max_delay_seconds
        self.min_delay_seconds = min_delay_seconds
        self.sleep_task: Optional[asyncio.Task] = None

    async def _get_installation_access_token(self, gh: GitHubAPI) -> str:
        # Valid for an hour, needs to be re-generated regularly.
        result = await apps.get_installation_access_token(
            gh,
            installation_id=self.installation_id,
            app_id=self.gh_app_id,
            private_key=self.gh_private_key,
        )
        return result["token"]

    def start(self) -> None:
        """Start running regular triage."""

        async def loop() -> None:
            print("Starting triage runner")
            while True:
                async with aiohttp.ClientSession() as session:
                    gh = GitHubAPI(session, constants.BOT_NAME)
                    token = await self._get_installation_access_token(gh)
                    await triage.run_triage(gh, token)
                try:
                    self.sleep_task = asyncio.create_task(
                        asyncio.sleep(self.max_delay_seconds)
                    )
                    await asyncio.sleep(self.min_delay_seconds)
                    await self.sleep_task
                    self.sleep_task = None
                except asyncio.CancelledError:
                    print("Running triage early")

        asyncio.create_task(loop())

    def run_soon(self, gh: GitHubAPI, token: str) -> None:
        """Request a new triage run soon if none is already in progress."""
        print("Requesting triage")
        # Use the requester's authentication for the next triage.
        if self.sleep_task is not None:
            self.sleep_task.cancel()


runners: Dict[str, TriageRunner] = dict()
