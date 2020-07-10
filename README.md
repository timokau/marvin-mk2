# Marvin MK2

This is a helpful bot that keeps PRs on nixpkgs flowing. See [USAGE.md](USAGE.md) for a usage-focused introduction.

## Testing

To run all linters/check use:

```
$ nix-build pre-commit.nix
```


## Related RFCs
Marvin is basically a trial run of [rfc 30](https://github.com/NixOS/rfcs/pull/30/).

Further readings: 
- https://github.com/NixOS/rfcs/blob/master/rfcs/0039-unprivileged-maintainer-teams.md
- https://github.com/NixOS/rfcs/blob/master/rfcs/0051-mark-stale-issues.md
