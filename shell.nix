let
  inherit (import ./definitions.nix {}) pkgs pythonenv;
in
pkgs.mkShell {
  buildInputs = [
    pythonenv
  ];
}
