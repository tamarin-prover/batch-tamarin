{
  description = "Tamarin Prover 1.4.1 with Maude for batch-tamarin Docker execution";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-25.05";
    flake-utils.url = "github:numtide/flake-utils";
  };

  outputs = { self, nixpkgs, flake-utils }:
    flake-utils.lib.eachDefaultSystem (system:
      let
        pkgs = nixpkgs.legacyPackages.${system};
        pkgs-old = import (builtins.fetchTarball {
          url = "https://github.com/NixOS/nixpkgs/archive/fc159594a768143812be50e73a95a610cdb97a47.tar.gz";
          sha256 = "0g17j4px4hi1jlybwbvq88g1lq537b2lxb9cw0kiw79mxnzma3gp";
        }) { inherit system; };
      in
      {
        packages.default = pkgs.buildEnv {
          name = "tamarin-prover-env";
          paths = with pkgs-old; [
            tamarin-prover
            graphviz
            coreutils
            bash
          ];
        };
      });
}
