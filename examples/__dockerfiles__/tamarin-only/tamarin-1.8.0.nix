{
  description = "Tamarin Prover 1.8.0 with Maude for batch-tamarin Docker execution";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/4ae2e647537bcdbb82265469442713d066675275";
    flake-utils.url = "github:numtide/flake-utils";
  };

  outputs = { self, nixpkgs, flake-utils }:
    flake-utils.lib.eachDefaultSystem (system:
      let
        pkgs = nixpkgs.legacyPackages.${system};
      in
      {
        packages.default = pkgs.buildEnv {
          name = "tamarin-prover-env";
          paths = with pkgs; [
            tamarin-prover
            graphviz
            coreutils
            bash
          ];
        };
      });
}
