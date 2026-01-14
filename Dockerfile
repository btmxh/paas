# Use a specialized uv image that includes the uv binary
# We use a python base image and install uv, or a multi-stage build.
# For simplicity and following "docker image from uv", we can use ghcr.io/astral-sh/uv:python3.12-bookworm-slim
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

# Set the working directory
WORKDIR /app

# Enable bytecode compilation
ENV UV_COMPILE_BYTECODE=1

# Copy from the cache instead of linking since it's a container
ENV UV_LINK_MODE=copy

# Install the project's dependencies from the lockfile
# First, copy the lockfile and pyproject.toml
COPY pyproject.toml uv.lock ./

# Install dependencies
# --no-install-project ensures we don't install the project itself yet
RUN uv sync --frozen --no-install-project --no-dev

# Copy the rest of the application
COPY . .

# Install the project itself
RUN uv sync --frozen --no-dev

# Place /app/.venv/bin at the beginning of PATH
ENV PATH="/app/.venv/bin:$PATH"

# Run the application by default
CMD ["python", "-m", "paas.main"]
