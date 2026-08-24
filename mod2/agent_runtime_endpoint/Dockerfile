FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8080

# BedrockAgentCoreApp 版で起動
# OTel 自動計装で Observability を有効化
CMD ["opentelemetry-instrument", "python", "agent_endpoint_bedrock_agentcore.py"]
