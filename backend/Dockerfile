FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app ./app
COPY alembic.ini ./alembic.ini
COPY migrations ./migrations
# 0.0.0.0 = aceita conexões vindas de outros containers (o Nginx)
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
