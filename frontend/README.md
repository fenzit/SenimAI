# Senim AI frontend

Красивый адаптивный React-интерфейс для MVP проверки достоверности ответов ИИ.

## Запуск

```bash
pnpm install
pnpm dev
```

По умолчанию доступен устойчивый демо-режим: он показывает готовый сценарий с Эйфелевой башней без API-ключей и интернета.

## Подключение FastAPI

Создайте `.env` из `.env.example` и укажите адрес backend-а:

```bash
VITE_API_BASE_URL=http://localhost:8000
```

После этого в интерфейсе станет активен переключатель `Live API`. Он отправляет `POST /api/v1/analyze` с телом:

```json
{ "text": "...", "language": "ru", "max_claims": 8 }
```

Интерфейс ожидает контракт из технического задания: `summary`, `claims`, `verdict`, `confidence`, `explanation`, `sources`.
