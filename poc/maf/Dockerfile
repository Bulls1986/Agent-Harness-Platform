# POC-only isolated *agent runtime container*, not a production Coding Sandbox.
FROM python:3.11-slim
WORKDIR /workspace
COPY poc/maf/requirements.txt /workspace/poc/maf/requirements.txt
RUN python -m pip install --no-cache-dir -r /workspace/poc/maf/requirements.txt
COPY poc/maf/ /workspace/poc/maf/
CMD ["python", "poc/maf/session_probe.py"]
