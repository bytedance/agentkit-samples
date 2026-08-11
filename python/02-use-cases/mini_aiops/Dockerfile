FROM agentkit-prod-public-cn-beijing.cr.volces.com/base/py-simple:python3.12-bookworm-slim-latest

ENV UV_SYSTEM_PYTHON=1 \
    UV_COMPILE_BYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DOCKER_CONTAINER=1

WORKDIR /app

# requirements.txt contains a local editable dependency. Copy it before
# installing requirements so uv can resolve ./mcp_server_ccapi.
COPY requirements.txt ./
COPY mcp_server_ccapi ./mcp_server_ccapi
RUN uv pip install -r requirements.txt

COPY . .

EXPOSE 8000
CMD ["python", "-m", "agent"]
