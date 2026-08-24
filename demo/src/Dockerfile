FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8080

# OTelのPython SDK経由でアプリを起動（自動計装を有効化）
CMD ["opentelemetry-instrument", "python", "agent_production.py"]
