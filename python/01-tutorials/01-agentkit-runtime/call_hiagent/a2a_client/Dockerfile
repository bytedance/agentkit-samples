FROM agentkit-prod-public-cn-beijing.cr.volces.com/base/py-simple:python3.13-bookworm-slim-latest

ENV UV_SYSTEM_PYTHON=1 UV_COMPILE_BYTECODE=1 PYTHONUNBUFFERED=1 HOST=0.0.0.0 PORT=8000
WORKDIR /app
COPY requirements.txt ./
RUN uv pip install -r requirements.txt
COPY a2a_server.py a2a_tool.py remote_agentcard.json ./

EXPOSE 8000
CMD ["python", "a2a_server.py"]
