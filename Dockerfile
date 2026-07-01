FROM python:3.14-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY web_app.py edhrec_backend.py ./

EXPOSE 8501
# Prometheus metrics endpoint scraped by Grafana Alloy
EXPOSE 8502

CMD ["streamlit", "run", "web_app.py", "--server.address=0.0.0.0", "--server.port=8501"]
