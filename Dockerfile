FROM node:20-slim AS frontend-build

WORKDIR /frontend

COPY frontend/package*.json ./
RUN npm ci

COPY frontend ./
RUN npm run build

FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        default-libmysqlclient-dev \
        pkg-config \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml manage.py ./
COPY max_support_desk ./max_support_desk
COPY support ./support
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir "."

COPY . .
COPY --from=frontend-build /frontend/dist /app/frontend/dist

RUN python manage.py collectstatic --noinput

EXPOSE 8000

CMD ["daphne", "-b", "0.0.0.0", "-p", "8000", "max_support_desk.asgi:application"]
