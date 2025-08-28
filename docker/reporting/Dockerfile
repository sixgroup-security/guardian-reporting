# Stage 1: Build and install dependencies
FROM pandoc/extra:3.3.0.0 AS base

ENV VIRTUAL_ENV=/app/venv \
    PATH="/app/venv/bin:${PATH}" \
    PYTHONPATH=/app

# Set the working directory
WORKDIR /app


# Create dedicated stage for building
FROM base AS builder

# Set environment variables
ENV POETRY_VERSION=1.8.3 \
    POETRY_NO_INTERACTION=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Copy Poetry files
COPY --chmod=644 poetry.lock pyproject.toml /app/

# Install Poetry and dependencies
RUN python3 -m venv /app/venv \
    && . /app/venv/bin/activate \
    && pip install --no-cache-dir "poetry==$POETRY_VERSION" \
    && poetry install --no-ansi \
    && pip uninstall -y poetry


# Stage 2: Create final stage containing only the necessary code
FROM base AS final

# Copy the virtual environment from the builder stage
COPY --from=builder /app/venv /app/venv

# Option 1: Perform online installation of missing packages
RUN /opt/texlive/texdir/bin/x86_64-linuxmusl/tlmgr install pgfplots lastpage siunitx
# Option 2: Perform offline installation of missing packages
# To create the latex-extra.tar file run the following command:
# find / -iname "pgfplots" -or -iname "lastpage" -o -iname "siunitx" | xargs tar -cjf /app/tmp/latex-extra.tar.bz2
# COPY docker/reporting/latex-extra.tar /tmp/latex-extra.tar

# Copy the application code to the container
COPY --chmod=755 app /app

# Create a non-root user 'guardian'
RUN addgroup -g 1001 guardian \
    && adduser -u 1001 -H -D -G guardian guardian \
    && mkdir /app/logs \
    && chown -R guardian:guardian /app/logs
# Option 2: Perform offline installation of missing packages
# texhash updates the ls-R files after installing extra LaTeX packages.
# RUN tar -xf /tmp/latex-extra.tar -C / \
#     && rm /tmp/latex-extra.tar \
#     && /opt/texlive/texdir/bin/x86_64-linuxmusl/texhash

# Use the non-root user to run the application
USER guardian

ENTRYPOINT ["python", "main.py"]
