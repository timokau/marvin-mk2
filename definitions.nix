{ # `git ls-remote https://github.com/nixos/nixpkgs-channels nixos-unstable`
  nixpkgs-rev ? "700eed636c99de8a2a5f23cc20e745fc13a44bc2"
, pkgsPath ? builtins.fetchTarball {
    name = "nixpkgs-${nixpkgs-rev}";
    url = "https://github.com/nixos/nixpkgs/archive/${nixpkgs-rev}.tar.gz";
  }
, pkgs ? import pkgsPath {}
}:
{
  pythonenv = pkgs.python3.withPackages(ps: with ps; [
    aiohttp
    gidgethub
    pytest
    mypy
    pytest-asyncio
    pytest-aiohttp
  ]);
  pkgs = pkgs;
  # git ls-remote https://github.com/cachix/pre-commit-hooks.nix master
  nix-pre-commit-hooks = import (builtins.fetchTarball "https://github.com/cachix/pre-commit-hooks.nix/tarball/f709c4652d4696dbe7c6a8354ebd5938f2bf807b");
}
