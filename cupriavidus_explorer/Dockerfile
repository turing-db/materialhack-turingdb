# Cupriavidus necator explorer — single-container deploy (TuringDB + gated UI).
# Build context = repo root (needs cupriavidus_necator/*.parquet and cupriavidus_explorer/).
#   docker build -f cupriavidus_explorer/Dockerfile -t cnec-explorer .
FROM node:20-bookworm-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
      git ca-certificates curl xz-utils && rm -rf /var/lib/apt/lists/*

# uv → pinned Python 3.12 + the turingdb wheel (server + turing-parquet CLI), in a venv.
RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/root/.local/bin:/opt/venv/bin:${PATH}"
RUN uv venv -p 3.12 /opt/venv && uv pip install --python /opt/venv/bin/python turingdb

WORKDIR /app

# 1) Bake the cupriavidus_necator graph. turing-parquet writes the graph files
#    directly (no running server needed), so it works at image-build time.
COPY cupriavidus_necator/nodes.parquet cupriavidus_necator/edges.parquet /app/cnec/
RUN turing-parquet -nodes /app/cnec/nodes.parquet -edges /app/cnec/edges.parquet \
      -props properties -edgetype relation -out /app -graph cupriavidus_necator \
    && rm -rf /app/cnec

# 2) Build the UI: clone the pinned visualizer, apply the overlay, npm build.
COPY cupriavidus_explorer /app/cupriavidus_explorer
RUN cd /app/cupriavidus_explorer && ./setup.sh && cd app && npm run build
RUN chmod +x /app/cupriavidus_explorer/start.sh

ENV TURING_API_PORT=6666 READONLY_GRAPHS=cupriavidus_necator
EXPOSE 8080
CMD ["/app/cupriavidus_explorer/start.sh"]
