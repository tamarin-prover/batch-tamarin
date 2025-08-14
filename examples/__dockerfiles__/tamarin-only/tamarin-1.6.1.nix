{
  description = "Tamarin Prover 1.6.1 with Maude for batch-tamarin Docker execution";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/a63a64b593dcf2fe05f7c5d666eb395950f36bc9";
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
