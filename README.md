# Marvin - Making sure your PR gets a review and your reviews don't get lost.

Marvin is an experimental bot with the goal of improving the nixpkgs PR workflow. Because its experimental, it only acts on PRs that have explicitly opted-in to it and its behavior may change at any time.

## What can Marvin do for me?

Marvin is supposed to make the life of PR authors and reviewers (with or without commit permission) easier. See [USAGE.md](USAGE.md) and [the bot's profile](https://github.com/apps/marvin-mk2) for details on the usage. This document focuses on the high-level aspects.

### As a PR author

You can [opt-in](https://github.com/apps/marvin-mk2) to use marvin on your PRs. You can only do that on your own PRs. Once your PR is opted-in, as indicated by the "marvin" GitHub label, marvin will

- Semi-automatically keep the **status** of your pull request. Does it currently need a new reviewer (label `needs_review`)? Is it in the middle of the review cycle (label `awaiting_reviewer` or `awaiting_changes`)? Has the reviewer become unresponsive?
- Based on this status, it will **nag the reviewer** in case they forgot to respond to your questions or changes. This happens after three days of inactivity in the `awaiting_reviewer` status. This keeps your PR from being forgotten.
- If the reviewer remains unresponsive, it will **put the PR back in the review queue**. This way the PR will be discovered by a new reviewer eventually.
- If nobody reviews your PR, it will **assign a reviewer** to it. There are limited capacities for assigning reviews, so this might take some time. Reviewers are assigned to `needs_reviewer` PRs on an [oldest-pr-first basis](https://github.com/NixOS/nixpkgs/issues?q=is%3Aopen+label%3Aneeds_reviewer+sort%3Acreated-asc). Your PR will never "drown" in the queue!

If your PR is managed by marvin and you are getting impatient, consider spending some time as a reviewer yourself. That way you can give back to the community and reduce the size of the queue. Smaller queue means more reviewers for your PR. You do not need any permissions or prerequisites for reviewing, just read on.

### As a reviewer without commit permission

If you want to help out with the PR backlog, marvin [makes it easy](https://github.com/NixOS/nixpkgs/issues?q=is%3Aopen+label%3Aneeds_reviewer+sort%3Acreated-asc+) to find a PR that does not have a reviewer yet. Once you have picked a PR to review, marvin [empowers](USAGE.md) you to "merge by proxy".

Do this on a honest best-effort basis. If you **had** the permission, would you push the merge button? If the secondary reviewer has additional feedback, that is perfectly fine. Consider it a learning experience for the next review. You do not need to have review experience to start reviewing PRs.

### As a reviewer with commit permission

If you have the permission to merge PRs yourself, you can still benefit from the discoverability features from marvin. You can [focus on PRs that have already been positively reviewed](https://github.com/NixOS/nixpkgs/issues?q=is%3Aopen+label%3Aneeds_merger+sort%3Acreated-asc+) or simply pick PRs from the [queue of PRs that need a reviewer](https://github.com/NixOS/nixpkgs/issues?q=is%3Aopen+label%3Aneeds_reviewer+sort%3Acreated-asc+).


## What can I do for Marvin (or for nixpkgs)

You can help out.

### Review some PRs

Whoever you are, if you have some minutes to spare you can review a PR. See the sections above for more information.

### Sign up for regular reviews

Marvin can also assign you to PRs to review. This is a nice way to make a sustainable and substantial contribution. Would you review a PR a week if an email invited you to do it? Sign up for it! See [this issue](https://github.com/timokau/marvin-mk2/issues/34) for more information. Keep in mind that the experience is still a bit rough around the edges, especially the rate limiting is a bit unintuitive for now.

### Contribute to Marvin

It is currently difficult to get started with contributions since marvin is hard to test. If you want to get your hands dirty anyway, check out [CONTRIBUTING.md](CONTRIBUTING.md).

## Context: Past, Present, Future

Marvin can be considered trial run of [rfc 30](https://github.com/NixOS/rfcs/pull/30/). It is experimental on an opt-in basis because the behavior is not finalized and there has not been a community decision yet. It will likely remain experimental for a long time since I (@timokau) work on it in my free time (and who has enough of that?). It is not at all certain that it will ever become official. It will require some more experimentation and probably at least a second maintainer.

Once I (or whoever maintains marvin then) think marvin is ready for stabilization, it will go through an RFC process.

Further readings: 
- https://github.com/NixOS/rfcs/blob/master/rfcs/0039-unprivileged-maintainer-teams.md
- https://github.com/NixOS/rfcs/blob/master/rfcs/0051-mark-stale-issues.md
