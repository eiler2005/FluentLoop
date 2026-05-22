FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY pyproject.toml ./
COPY alembic.ini ./
COPY src ./src
COPY scripts ./scripts
COPY migrations ./migrations

RUN pip install --no-cache-dir -e .

VOLUME ["/app/data"]

CMD ["python", "-m", "fluentloop"]
