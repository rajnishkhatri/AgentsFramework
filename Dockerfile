FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt ./agent/requirements.txt
RUN pip install --no-cache-dir -r agent/requirements.txt

COPY . ./agent/
RUN pip install --no-cache-dir -e ./agent/

RUN mkdir -p /app/agent/logs /app/agent/cache

ENV WORKSPACE_DIR=/workspace
ENV TRUST_PROVIDER=local

ENTRYPOINT ["python", "-m", "agent.cli"]
