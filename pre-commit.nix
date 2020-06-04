let
  inherit (import ./definitions.nix {}) pkgs pythonenv nix-pre-commit-hooks;
in nix-pre-commit-hooks.run {
 src = ./.;
 hooks = {
   # https://github.com/psf/black/blob/master/.pre-commit-hooks.yaml
   black = {
     enable = true;
     name = "black";
     description = "Format Python files";
     entry = "${pythonenv.pkgs.black}/bin/black --check";
     types = ["python"];
   };
   # https://github.com/sqlalchemyorg/zimports/blob/master/.pre-commit-hooks.yaml
   zimports = {
     enable = true;
     name = "zimports";
     description = "Python import rewriter";
     entry = "${(pythonenv.withPackages (pkgs: with pkgs; [zimports setuptools]))}/bin/zimports";
     types = ["python"];
   };
   # https://gitlab.com/pycqa/flake8/-/blob/master/.pre-commit-hooks.yaml
   flake8 = {
     enable = true;
     name = "flake8";
     description = "Command-line utility for enforcing style consistency across Python projects";
     entry = "${(pythonenv.withPackages (pkgs: with pkgs; [flake8]))}/bin/flake8";
     types = ["python"];
   };
   # https://github.com/PyCQA/doc8/blob/master/.pre-commit-hooks.yaml
   doc8 = {
     enable = true;
     name = "doc8";
     description = "For linting docs";
     entry = "${(pythonenv.withPackages (pkgs: with pkgs; [doc8]))}/bin/doc8";
     files = "\\.rst$";
   };
 };
}
