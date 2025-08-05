{
  description = "Tamarin Prover 1.10.0 with Maude for batch-tamarin Docker execution";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/a421ac6595024edcfbb1ef950a3712b89161c359";
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
