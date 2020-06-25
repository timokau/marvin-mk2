# General Usage

This bot allows everybody to change a PRs status with a simple comment of the form `/status <new_status_here>`. The right status of a PR depends on which group of people it is currently *actionable* to. The right status is

- `needs_reviewer`, if the PR is ready for review and needs a new reviewer (because it does not yet have one or the reviewer is unresponsive)
- `awaiting_reviewer`, if the PR is in review (i.e. at least one reviewer is involved in the discussion or requested) and is blocked on feedback from the reviewer.
- `awaiting_changes` if the PR in its current form is not ready yet. Issues of this state are usually only actionable to the PR author, although outside help is of course also possible.
- `needs_merger` can be set by reviewers who do not have merge permission but *would merge this PR if they could*. Think of this as a merge-button by proxy. PRs of this state are actionable for contributors with merge permission. These contributors may have further feedback, but the reviewer should make an honest effort to anticipate the feedback and get all issues resolved *before* setting the state to `needs_merger`.

# Tips for Reviewers

As explained in the previous section, any PR with the `awaiting_reviewer` label should be actionable for any reviewer. There are cases where you may feel that it is not actionable for you. Here are some tips how to proceed:

- If you don't understand parts of the changes: Give a review and ask the PR author for clarifications! The PR author should then usually add the clarifications as comments to the nix expression. This is very valuable feedback. In fact, sometimes it is useful to be a bit naive on purpose. All source code should be well-documented and commented.

- If you think somebody with a very specific expertise should look at the PR: Try to find out who that could be (for example by looking at similar files and who has changed them in the past) and ping them. Delegation is also an action, and often the best one. If you have done so, set the state back to `awaiting_changes` since the PR is no longer actionable to any reviewer. If the person you pinged is unresponsive, the PR author can set the state back to `awaiting_reviewer` after some reasonable amount of time (usually something in the order of 3 days to a week).
