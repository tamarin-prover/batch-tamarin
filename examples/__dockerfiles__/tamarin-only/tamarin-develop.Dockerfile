# Tamarin Prover Develop Branch using Debian Sid
# Built for batch-tamarin Docker execution using Stack
#
# Build with: docker build -f tamarin-develop.Dockerfile -t tamarin-develop .

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
    git \
    curl \
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

# Clone tamarin-prover develop branch
RUN git clone https://github.com/tamarin-prover/tamarin-prover.git && \
    cd tamarin-prover && \
    git checkout develop

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
    TAMARIN_VERSION=develop

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
