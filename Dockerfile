FROM python:3.13-slim

# 2. Рабочая папка
WORKDIR /app

# 3. Системные утилиты
RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*

# 4. Ставим Poetry
RUN curl -sSL https://install.python-poetry.org | python3 -
ENV PATH="/root/.local/bin:$PATH"

# 5. Копируем файлы
COPY pyproject.toml poetry.lock ./
COPY . .

# 6. Ставим библиотеки
RUN poetry config virtualenvs.create false \
&& poetry install --no-interaction --no-ansi --no-root
# 7. Запуск (по умолчанию, но docker-compose его переопределит)
CMD ["python", "app/run_polling.py"]
