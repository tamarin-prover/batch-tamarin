# WARNING: This Dockerfile has been made to compile tamarin-prover based on August 2025
# tamarin-prover development branch, with current dependencies. Compiling older versions
# may be difficult, while probably possible, you may want to downgrade debian to an older
# version to downgrade dependencies versions. Legacy version pipelines are built with nix
# packages, this is not applicable here, as this method is broken for the development branch.
# I have no reproducibility guaranties for this pipeline : I recommend to try to build the
# image by yourself and then give the dockerfile to batch-tamarin.

# Tamarin Prover Local Build using Debian Sid (debian:sid is used for getting the
# latest versions of dependencies, especially for maude. debian-sid maude was v3.4
# in Aug 2025, you can find older "pinned" versions with debian:bullseye -> maude v3.1
# and debian:bookworm -> maude v3.2, when I write this, debian:trixie with maude v3.4
# will be launched soon. There is no older version available with apt).
# Built for batch-tamarin Docker execution using Stack from local source

############################################################################################
# USAGE:
# 1. Place your tamarin-prover source code in the same directory as this Dockerfile
# 2. Rename your tamarin source directory to "tamarin-prover" (or change the COPY line below)
# 3. Build with: docker build -f local-tamarin.Dockerfile -t tamarin-prover:{version_tag} .

# You can replace {version_tag} with a tag of your choice, i.e. tamarin-prover:local
############################################################################################

FROM debian:sid AS builder

# Set environment variables for non-interactive installation
ENV DEBIAN_FRONTEND=noninteractive \
    LC_ALL=C.UTF-8 \
    LANG=C.UTF-8

# Install all required dependencies in one layer
RUN apt-get update && apt-get install -y --no-install-recommends \
    # Essential build tools
    build-essential \
    pkg-config \
    # Haskell development
    haskell-stack \
    ghc \
    # Tamarin runtime dependencies
    maude \
    graphviz \
    # Development utilities
    ca-certificates \
    # GHC dependencies
    libffi-dev \
    libgmp-dev \
    zlib1g-dev \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user for building
RUN groupadd -r tamarin && useradd -r -g tamarin -s /bin/bash -m tamarin
USER tamarin
WORKDIR /home/tamarin

# Copy local tamarin-prover source
# CHANGE THIS LINE if you want to name your source an other way
COPY --chown=tamarin:tamarin tamarin-prover/ /home/tamarin/tamarin-prover/

# Build tamarin-prover with stack
WORKDIR /home/tamarin/tamarin-prover
RUN stack setup && \
    stack build --system-ghc && \
    stack install --system-ghc --local-bin-path /home/tamarin/.local/bin

# Verify the build
RUN /home/tamarin/.local/bin/tamarin-prover test

# Runtime stage
FROM debian:sid AS runtime

# Set environment variables
ENV DEBIAN_FRONTEND=noninteractive \
    LC_ALL=C.UTF-8 \
    LANG=C.UTF-8 \
    TAMARIN_VERSION=local

# Install only runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    maude \
    graphviz \
    ca-certificates \
    # Runtime libraries
    libffi8 \
    libgmp10 \
    zlib1g \
    libnuma1 \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN groupadd -r tamarin && useradd -r -g tamarin -s /bin/bash -m tamarin

# Copy built binary from builder stage
COPY --from=builder --chown=tamarin:tamarin /home/tamarin/.local/bin/tamarin-prover /usr/local/bin/tamarin-prover

# Switch to non-root user
USER tamarin
WORKDIR /workspace

# Create workspace volume
VOLUME /workspace

# Verify installation works
RUN tamarin-prover test

# Default command
CMD ["tamarin-prover", "--help"]
