# SenimAI Backend — AI Trust Verification Pipeline

Backend сервис для верификации достоверности ответов искусственного интеллекта на основе внешних независимых доказательств (Evidence-based Fact Checking).

---

## 🎯 Ключевые возможности MVP

1. **Atomic Claim Extraction**: LLM разбивает сложный ответ ИИ на атомарные проверяемые утверждения (`factual`, `numerical`, `temporal`, `comparative`, `opinion`).
2. **Multi-Source Evidence Search**: Поиск релевантных источников через Tavily / Serper / DuckDuckGo.
3. **Anti-Prompt Injection Defense**: Санитарная очистка внешнего веб-контента для защиты от инъекций промптов в сниппетах.
4. **Strict Grounded Verification**: LLM используется как аналитик доказательств, а не как источник истины. При отсутствии доказательств возвращается `UNVERIFIED`.
5. **Verdict Classification**:
   - `SUPPORTED` — подтверждено источниками.
   - `CONTRADICTED` — опровергнуто источниками.
   - `PARTIALLY_SUPPORTED` — частично подтверждено.
   - `UNVERIFIED` — недостаточно доказательств.
   - `NOT_FACT_CHECKABLE` — субъективное мнение.
   - `CONFLICTING` — источники противоречат друг другу.
6. **Aggregate Verification Score**: Расчёт прозрачного коэффициента доказательного покрытия (0.0 — 1.0).
7. **Hackathon Mock Mode**: Встроенный режим оффлайн-демонстрации (`MOCK_MODE=true`), гарантирующий безотказную работу на презентации без внешних API.

---

## 🚀 Быстрый старт

### 1. Установка зависимостей

```bash
pip install -r requirements.txt
```

### 2. Настройка окружения

Скопируйте пример файла конфигурации:
```bash
cp .env.example .env
```

Отредактируйте `.env`:
```ini
PROJECT_NAME="SenimAI - AI Trust Fact-Checking API"
MOCK_MODE=false # Либо true для оффлайн демонстрации

# LLM (OpenAI, Groq, DeepSeek или локальная Ollama)
OPENAI_API_KEY=sk-...
LLM_MODEL=gpt-4o-mini

# Поиск
SEARCH_PROVIDER=duckduckgo # Либо tavily / serper при наличии ключа
TAVILY_API_KEY=tvly-...
```

### 3. Запуск сервера

```bash
uvicorn app.main:app --reload --port 8000
```

Сервер будет доступен по адресу: `http://localhost:8000`
Интерактивная Swagger документация: `http://localhost:8000/docs`

---

## 📡 API Контракт

### `POST /api/v1/analyze`

#### Запрос:
```json
{
  "text": "Эйфелева башня была построена в 1889 году и находится в Лондоне.",
  "language": "ru",
  "max_claims": 8
}
```

#### Ответ:
```json
{
  "analysis_id": "analysis_a1b2c3d4e5f6",
  "summary": {
    "total_claims": 2,
    "supported": 1,
    "contradicted": 1,
    "partially_supported": 0,
    "unverified": 0,
    "not_fact_checkable": 0,
    "conflicting": 0,
    "verification_score": 0.5
  },
  "claims": [
    {
      "id": 1,
      "text": "Эйфелева башня была построена в 1889 году.",
      "type": "temporal",
      "verdict": "SUPPORTED",
      "confidence": 0.97,
      "explanation": "Источники подтверждают, что Эйфелева башня была открыта в 1889 году.",
      "sources": [
        {
          "title": "Official Eiffel Tower History",
          "url": "https://www.toureiffel.paris/en/the-monument/history",
          "domain": "toureiffel.paris",
          "snippet": "Built for the 1889 Exposition Universelle...",
          "quality": "HIGH"
        }
      ]
    },
    {
      "id": 2,
      "text": "Эйфелева башня находится в Лондоне.",
      "type": "factual",
      "verdict": "CONTRADICTED",
      "confidence": 0.99,
      "explanation": "Источники опровергают: Эйфелева башня расположена в Париже (Франция), а не в Лондоне.",
      "sources": [
        {
          "title": "Eiffel Tower - Wikipedia",
          "url": "https://en.wikipedia.org/wiki/Eiffel_Tower",
          "domain": "wikipedia.org",
          "snippet": "The Eiffel Tower is located in Paris, France.",
          "quality": "HIGH"
        }
      ]
    }
  ]
}
```

### Дополнительные эндпоинты:
- `GET /api/v1/health` — проверка статуса сервиса и активного провайдера.
- `GET /api/v1/demo-cases` — готовые демо-кейсы для хакатона.

---

## 🧪 Запуск тестов

```bash
pytest backend/tests
```
