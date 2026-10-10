ARG PYTHON_BASE_IMAGE=python:3.12-slim
FROM ${PYTHON_BASE_IMAGE}
WORKDIR /app
ARG PIP_INDEX_URL=https://pypi.org/simple
RUN python -m pip install --no-cache-dir --index-url "${PIP_INDEX_URL}" \
    'hatchet-sdk==1.42.1' 'pydantic-ai-slim==2.54.0' \
    'openai-agents==0.23.1' 'psycopg[binary]>=3.2,<4' \
    'fastapi>=0.115,<1' 'uvicorn>=0.30,<1' 'httpx>=0.27,<1'
COPY poc /app/poc