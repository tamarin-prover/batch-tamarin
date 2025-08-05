{
  description = "Tamarin Prover 1.4.0 with Maude for batch-tamarin Docker execution";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-25.05";
    flake-utils.url = "github:numtide/flake-utils";
  };

  outputs = { self, nixpkgs, flake-utils }:
    flake-utils.lib.eachDefaultSystem (system:
      let
        pkgs = nixpkgs.legacyPackages.${system};
        pkgs-old = import (builtins.fetchTarball {
          url = "https://github.com/NixOS/nixpkgs/archive/04002e2b7186c166af87c20da7a7ceb8c0edb021.tar.gz";
          sha256 = "1v4hhh5qak0ngys1g8w7c0rc5fn6jzh8d8ywilxm3nzl3ndyymzk";
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
