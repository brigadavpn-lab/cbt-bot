FROM python:3.13-slim

# 2. Рабочая папка
WORKDIR /app

# 3. Системные утилиты
RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*

# 4. Копируем файлы
COPY . .

# 5. Ставим библиотеки через pip
RUN pip install --no-cache-dir \
    aiogram==3.22.0 \
    fastapi==0.123.4 \
    uvicorn==0.38.0 \
    sqlalchemy==2.0.44 \
    asyncpg==0.31.0 \
    alembic==1.17.2 \
    redis==7.1.0 \
    pydantic-settings==2.12.0 \
    anthropic==0.40.0 \
    greenlet==3.2.4 \
    python-json-logger==4.0.0

# 6. Создаём непривилегированного пользователя и передаём ему владение /app
RUN useradd --system --create-home --uid 1000 --shell /bin/bash botuser \
    && chown -R botuser:botuser /app

# 7. Переключаем контекст выполнения на непривилегированного пользователя
USER botuser
