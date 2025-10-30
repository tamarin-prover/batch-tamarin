# Tamarin Prover 1.8.0 and batch-tamarin with Maude using NixOS
# Multi-architecture support (AMD64/ARM64)

FROM nixos/nix:latest AS nix-environment

# Enable experimental features and configure cache for better performance
RUN echo "experimental-features = nix-command flakes" >> /etc/nix/nix.conf && \
    echo "substituters = https://cache.nixos.org https://nix-community.cachix.org" >> /etc/nix/nix.conf && \
    echo "trusted-public-keys = cache.nixos.org-1:6NCHdD59X431o0gWypbMrAURkbJ16ZPMQFGspcDShjY= nix-community.cachix.org-1:mB9FSh9qf2dCimDSUo8Zy7bkq5CX+/rkCWyvRCYg3Fs=" >> /etc/nix/nix.conf

# Copy flake configuration and install tamarin-prover with dependencies
COPY tamarin-1.8.0-and-batch.nix /tmp/flake.nix
RUN cd /tmp && nix profile add .#default

# Set environment
ENV PATH="/root/.nix-profile/bin:$PATH" \
    TAMARIN_VERSION=1.8.0 \
    LC_ALL=C.UTF-8 \
    LANG=C.UTF-8

# Create workspace
WORKDIR /workspace
VOLUME /workspace

# Verify installation
RUN tamarin-prover test

# Default command
CMD ["zsh"]
