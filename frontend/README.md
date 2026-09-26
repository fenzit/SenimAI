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

## Расширенный контракт для explainability

Все поля ниже опциональны: если backend их не передаёт, базовые карточки продолжают работать.

- `ClaimResult.original_quote`, `start_char`, `end_char` — подсвечивают точный фрагмент исходного ответа и ведут к нужной карточке claim.
- `ClaimResult.why_verdict` — массив шагов или строка с объяснением для блока **Ask Why**.
- `Source.stance` — `SUPPORTS`, `CONTRADICTS`, `NEUTRAL` или `INSUFFICIENT`; отображается как позиция источника по отношению к claim.
- `ClaimResult.evidence_sufficiency` — классификация силы доказательств: `DIRECT`, `COMBINED`, `INDIRECT` или `INSUFFICIENT`. Она выводится в карточке claim и попадает в Markdown-отчёт; при отсутствии поля старые ответы остаются совместимы.
- `AnalyzeResponse.processing_time_ms` и `timestamp` — показываются в summary и попадают в экспортируемый Markdown-отчёт.

После анализа пользователь может скопировать готовый Markdown-отчёт или скачать его как `.md`.
