FROM python:3.12.8-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN addgroup --system sscre \
    && adduser --system --ingroup sscre sscre

COPY requirements-docker.txt ./
COPY pyproject.toml ./
COPY src ./src
COPY migrations ./migrations

RUN pip install -r requirements-docker.txt \
    && pip install --no-deps .

USER sscre

EXPOSE 8000

CMD ["uvicorn", "sscre.app:app", "--host", "0.0.0.0", "--port", "8000"]
