FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY docs ./docs
COPY sql ./sql
COPY README.md ./README.md

# RUN mkdir -p /app/media/food /app/media/temp

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

FROM centos as centos  COPY --from=centos  /usr/share/zoneinfo/Asia/Shanghai /etc/localtime RUN echo "Asia/Shanghai" > /etc/timezone