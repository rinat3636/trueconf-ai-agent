# Архитектура системы: Корпоративный ИИ-агент ТД "Мир Мороженого"

> **Версия:** 1.0  
> **Дата:** 22 июня 2026  
> **Статус:** Архитектурный проект (RFC)

---

## Содержание

1. [Анализ бизнес-домена](#1-анализ-бизнес-домена)
2. [Общая архитектура системы](#2-общая-архитектура-системы)
3. [ER-диаграмма и структура PostgreSQL](#3-er-диаграмма-и-структура-postgresql)
4. [Структура Qdrant](#4-структура-qdrant)
5. [Структура API](#5-структура-api)
6. [Архитектура ИИ-агента](#6-архитектура-ии-агента)
7. [Архитектура админ-панели](#7-архитектура-админ-панели)
8. [Очереди фоновых задач](#8-очереди-фоновых-задач)
9. [Безопасность](#9-безопасность)
10. [Roadmap разработки](#10-roadmap-разработки)
11. [Возможные проблемы и решения](#11-возможные-проблемы-и-решения)

---

## 1. Анализ бизнес-домена

### 1.1 О компании

ООО ТД "Мир Мороженого" — дистрибьютор мороженого и продуктов питания на территории Владимирской области. Компания является поставщиком-производителем мороженого и полуфабрикатов под собственными ТМ и официальным дистрибьютором крупных производителей.

**Собственные ТМ (производство Айс-Групп, г. Омск / Сибхолод / АО Перспектива):**
- "На Двойных сливках" (пломбир, премиум-сегмент)
- "Dessert Club" / "Dessert Club Classic" (десерты, торты, рожки)
- "Зайчик" (классическое мороженое, ранее АО Перспектива)
- "Страна Вкусняшкино" (десерты, торты, фруктовый лёд)
- "Neon Club" (молодёжная линейка, фруктовый лёд, энергетические)
- "ГОСТ" (молочное мороженое в стаканчиках)
- "Kawaii" (десерты с необычными вкусами)
- "Капибара" (фруктовые десерты)
- "Лабубука" (детское мороженое)
- "Pro Fit" (без сахара, веган-линейка)
- "Омский Пломбир" (пломбир в шоколадной глазури)
- "Снежка" (десерты в стаканчиках)
- "В гостях у сказки" (детское эскимо)
- "Школа волшебства" (детское эскимо)
- "Фиксики" (лицензионная детская линейка)
- "Монстры на каникулах" (лицензионная)

**Дистрибуция:**
- ТД "Ренна" (Коровка из Кореновки)
- Планета Мириталь (Французские блины)
- Мираторг (полуфабрикаты)
- Арнест Юнирусь (Инмарко)

### 1.2 Анализ приложенных документов

| Документ | Тип | Категория знаний | Ключевое содержание |
|---|---|---|---|
| Логист. данные Айс-групп 2026 (XLS, 5 листов) | Справочник продукции | `product_catalog`, `logistics` | 170+ SKU: артикул, состав, штрихкоды, размеры, паллетизация, декларации, БЗМЖ/ЗМЖ, пищевая ценность, срок годности, ставка НДС. Листы: TDSheet (старый каталог), 2026 (актуальный), Десерты (описания), новинки 2025 |
| Каталог Айс-Групп 2026 (PDF, 44 стр.) | Маркетинговый каталог | `product_catalog` | Визуальный каталог продукции с фото (PDF со сканами — текст не извлекается программно, требует OCR) |
| Книга продаж АГ 2019 (PDF, 56 стр.) | Руководство по продажам | `sales_methodology` | Методология продаж, стандарты работы с клиентами (PDF со сканами — текст не извлекается, требует OCR) |
| Коммерческое предложение (DOCX) | Шаблон КП | `commercial`, `company_info` | Описание компании, условия сотрудничества, преимущества, ассортимент, логистика доставки |
| Политика управления ПДЗ (DOCX, ~23 000 символов) | Регламент | `policy`, `debt_management` | Полная политика управления дебиторской задолженностью: кредитные лимиты (сезонные: лето 40 тыс / зима 20 тыс), проверка СБ, отсрочки (7/14/14+ дней), стоп-листы, порядок взыскания, работа с ХО |
| Декларации РЕННА (PDF, 7 стр.) | Сертификация | `certification` | Декларации соответствия на продукцию Коровка из Кореновки (PDF со сканами) |
| Классификация мороженого (PPTX, 5 слайдов) | Обучение | `product_knowledge` | Классификация: молочное / сливочное / пломбир / ЗМЖ / кисломолочное / десерты замороженные / сорбет / щербет / фруктовый лёд |
| Внутренние номера (DOCX) | Справочник | `contacts` | Телефонный справочник филиала Кольчугино: 20 сотрудников, внутренние номера 601-708 |
| Электронные почты (DOCX) | Справочник | `contacts` | Корпоративная почта ice-mir.ru: директора, РУП, ТП, бухгалтеры, логисты, координаторы |
| Отчёт по ТП (DOCX) | Аналитический отчёт | `sales_analytics` | Анализ ТП и клиентской базы: структура по ФИО, ключевые категории (Другое, Стаканчики, Эскимо), топ-клиенты по ТП |
| Валовая прибыль (XLS, 22 165 строк) | Отчёт из 1С | `sales_data` | Период 01.05-21.05.2026, филиал Кольчугино. Иерархия: ТП → Клиент → Номенклатура. Метрики: кол-во (ед.хр.), тоннаж, выручка с НДС, валовая прибыль, рентабельность %. ~26 ТП, сотни клиентов, тысячи SKU-строк |

### 1.3 Структура отчёта из 1С (ключевой формат)

```
Иерархия строк:
├── Уровень 0: ТП (ФИО) → [qty, tonnage, revenue, profit, margin%]
│   ├── Уровень 1: Клиент (название + адрес) → [qty, tonnage, revenue, profit, margin%]
│   │   ├── Уровень 2: Номенклатура (SKU) → [qty, tonnage, revenue, profit, margin%]
│   │   └── ...
│   └── ...
└── Итого → [qty, tonnage, revenue, profit, margin%]

Колонки (7):
  [0]: (пусто или спец. заголовок)
  [1]: Наименование (ТП / Клиент / SKU)
  [2]: Количество (ед. хранения)
  [3]: Тоннаж
  [4]: Стоимость продажи с НДС (руб.)
  [5]: Валовая прибыль (руб.)
  [6]: Рентабельность (%)
```

### 1.4 Определённые категории знаний

| Категория | Код | Описание | Приоритет |
|---|---|---|---|
| Каталог продукции | `product_catalog` | SKU, состав, штрихкоды, БЗМЖ/ЗМЖ, пищевая ценность | Высокий |
| Логистика | `logistics` | Размеры, паллетизация, объёмы коробок, условия хранения | Высокий |
| Политики и регламенты | `policy` | ПДЗ, кредитные лимиты, отсрочки, стоп-листы | Высокий |
| Коммерческие условия | `commercial` | КП, условия сотрудничества, бонусы, акции | Средний |
| Сертификация | `certification` | Декларации соответствия, ГОСТы, ТН ВЭД | Средний |
| Классификация продукции | `product_knowledge` | Типы мороженого, ЗМЖ/БЗМЖ, жирность | Средний |
| Контакты | `contacts` | Телефоны, email, должности сотрудников | Средний |
| Методология продаж | `sales_methodology` | Стандарты работы с клиентами, техники продаж | Средний |
| Данные о продажах | `sales_data` | Выгрузки из 1С, отчёты по валовой прибыли | Высокий |
| Аналитика продаж | `sales_analytics` | Анализ ТП, клиентов, продуктов | Высокий |

---

## 2. Общая архитектура системы

### 2.1 Компонентная диаграмма

```
┌─────────────────────────────────────────────────────────────────────┐
│                         LINUX VPS                                   │
│                                                                     │
│  ┌──────────────┐    ┌──────────────────────────────────────────┐   │
│  │  TrueConf     │    │              FastAPI Backend              │   │
│  │  Server       │◄──►│                                          │   │
│  │  (Chatbot     │    │  ┌────────┐ ┌────────┐ ┌──────────────┐ │   │
│  │   Connector)  │    │  │ Auth   │ │  Chat  │ │  Knowledge   │ │   │
│  └──────────────┘    │  │ Router │ │ Router │ │  Router      │ │   │
│                       │  └────────┘ └────────┘ └──────────────┘ │   │
│  ┌──────────────┐    │  ┌────────┐ ┌────────┐ ┌──────────────┐ │   │
│  │  React SPA   │◄──►│  │Analytics│ │Moderatn│ │  Monitoring  │ │   │
│  │  Admin Panel  │    │  │ Router │ │ Router │ │  Router      │ │   │
│  └──────────────┘    │  └────────┘ └────────┘ └──────────────┘ │   │
│                       │                                          │   │
│                       │  ┌──────────────────────────────────┐    │   │
│                       │  │        SERVICE LAYER              │    │   │
│                       │  │  ┌──────┐ ┌────────┐ ┌────────┐  │    │   │
│                       │  │  │ RAG  │ │ Sales  │ │ Self-  │  │    │   │
│                       │  │  │Engine│ │Analyst │ │Learning│  │    │   │
│                       │  │  └──────┘ └────────┘ └────────┘  │    │   │
│                       │  │  ┌──────┐ ┌────────┐ ┌────────┐  │    │   │
│                       │  │  │Trace │ │Conflict│ │ Excel  │  │    │   │
│                       │  │  │Engine│ │Resolver│ │Parser  │  │    │   │
│                       │  │  └──────┘ └────────┘ └────────┘  │    │   │
│                       │  └──────────────────────────────────┘    │   │
│                       └──────────────────────────────────────────┘   │
│                                          │                           │
│            ┌────────────┬────────────────┼────────────┐              │
│            ▼            ▼                ▼            ▼              │
│  ┌──────────────┐ ┌──────────┐  ┌──────────────┐ ┌────────┐        │
│  │  PostgreSQL   │ │  Qdrant  │  │    Redis     │ │ Groq/  │        │
│  │  (данные,     │ │ (векторы,│  │  (кэш,       │ │ OpenAI │        │
│  │   аудит,      │ │  эмбед.) │  │   очереди,   │ │  API   │        │
│  │   история)    │ │          │  │   сессии)    │ │        │        │
│  └──────────────┘ └──────────┘  └──────────────┘ └────────┘        │
└─────────────────────────────────────────────────────────────────────┘
```

### 2.2 Стек технологий

| Компонент | Технология | Обоснование |
|---|---|---|
| Backend | FastAPI + uvicorn | Async, OpenAPI docs, production-ready |
| DB | PostgreSQL 16 + asyncpg + SQLAlchemy 2.0 (async) | ACID, параллельная запись, JSON-поля |
| Vector DB | Qdrant | Фильтрация по метаданным, payload indexing, snapshot backup |
| Cache / Queue | Redis 7 + arq (async task queue) | Кэш ответов, очереди задач, rate limiting, сессии |
| LLM | Groq (llama-3.3-70b / llama-4-scout) + fallback OpenAI (gpt-4.1-mini) | Groq — быстрый inference; OpenAI — fallback при ошибках |
| Embeddings | text-embedding-3-small (OpenAI) или nomic-embed-text (локальный fallback) | 1536-dim, русский язык |
| TrueConf | TrueConf Chatbot Connector (REST API + WebSocket) | Корпоративный мессенджер |
| Frontend | React 18 + Vite + TailwindCSS + Shadcn/UI | Быстрая разработка, доступная UI-библиотека |
| Reverse Proxy | Nginx | SSL, rate limiting, static files |
| Containerization | Docker Compose | Все сервисы в одном compose |
| OCR | Tesseract + pytesseract (для PDF-сканов) | Книга продаж, декларации |

### 2.3 Потоки данных

```
Сотрудник в TrueConf
       │
       ▼
TrueConf Chatbot Connector (WebSocket)
       │
       ▼
FastAPI: POST /api/chat/ask
       │
       ├──► Redis: проверка кэша (вопрос → SHA256)
       │          hit? → вернуть кэш
       │
       ├──► PostgreSQL: загрузка корпоративной памяти
       │    (rules с priority DESC)
       │
       ├──► PostgreSQL: проверка точных коррекций
       │    (correction.question ≈ user_question, cosine > 0.92)
       │          hit? → вернуть correction.answer + trace
       │
       ├──► Qdrant: RAG-поиск
       │    1. embed(question) → vector
       │    2. search(vector, filter={category, status=approved}, limit=10)
       │    3. rerank по score, приоритету категории
       │    4. отсечение по threshold (score > 0.35)
       │
       ├──► LLM: генерация ответа
       │    system_prompt = corporate_memory + rules
       │    context = RAG_results + corrections
       │    user_message = question
       │
       ├──► PostgreSQL: сохранение trace (sources, rules, scores)
       │
       └──► TrueConf: отправка ответа + источники
```

---

## 3. ER-диаграмма и структура PostgreSQL

### 3.1 ER-диаграмма

```
┌──────────────┐       ┌──────────────────┐       ┌──────────────────┐
│    users      │       │    documents     │       │ knowledge_items  │
├──────────────┤       ├──────────────────┤       ├──────────────────┤
│ id (PK)      │       │ id (PK)          │       │ id (PK)          │
│ username     │  1:N  │ uploaded_by (FK) │  1:N  │ document_id (FK) │
│ email        │◄─────│ filename         │◄─────│ title            │
│ full_name    │       │ file_type        │       │ content          │
│ role         │       │ file_path        │       │ category         │
│ trueconf_id  │       │ file_size        │       │ status           │
│ password_hash│       │ category         │       │ version          │
│ is_active    │       │ status           │       │ qdrant_point_id  │
│ created_at   │       │ error_message    │       │ priority         │
│ updated_at   │       │ metadata (JSONB) │       │ approved_by (FK) │
└──────────────┘       │ checksum_sha256  │       │ source_chunk     │
       │               │ created_at       │       │ metadata (JSONB) │
       │               │ processed_at     │       │ created_at       │
       │               └──────────────────┘       │ updated_at       │
       │                                          └──────────────────┘
       │                                                   │
       │        ┌──────────────────┐                       │
       │        │ corporate_rules  │               ┌───────┴────────┐
       │        ├──────────────────┤               │knowledge_      │
       │   1:N  │ id (PK)          │               │conflicts       │
       ├───────│ created_by (FK)  │               ├────────────────┤
       │        │ rule_type        │               │ id (PK)        │
       │        │ title            │               │ new_item_id FK │
       │        │ content          │               │ existing_item  │
       │        │ priority (1-100) │               │ _id (FK)       │
       │        │ is_active        │               │ conflict_type  │
       │        │ category         │               │ resolution     │
       │        │ created_at       │               │ resolved_by FK │
       │        │ updated_at       │               │ resolved_at    │
       │        └──────────────────┘               │ notes          │
       │                                           │ created_at     │
       │        ┌──────────────────┐               └────────────────┘
       │        │answer_corrections│
       │        ├──────────────────┤       ┌──────────────────────┐
       │   1:N  │ id (PK)          │       │ moderation_queue     │
       ├───────│ created_by (FK)  │       ├──────────────────────┤
       │        │ original_question│       │ id (PK)              │
       │        │ original_answer  │       │ item_type            │
       │        │ corrected_answer │       │ item_id              │
       │        │ correction_type  │       │ action               │
       │        │ question_embed   │       │ payload (JSONB)      │
       │        │ priority (1-100) │       │ status               │
       │        │ linked_knowledge │       │ created_by (FK)      │
       │        │ _item_id (FK)    │       │ reviewed_by (FK)     │
       │        │ is_active        │       │ reviewed_at          │
       │        │ created_at       │       │ review_notes         │
       │        └──────────────────┘       │ created_at           │
       │                                   └──────────────────────┘
       │
       │        ┌──────────────────┐       ┌──────────────────────┐
       │        │  chat_messages   │       │  chat_sessions       │
       │        ├──────────────────┤       ├──────────────────────┤
       │   1:N  │ id (PK)          │  N:1  │ id (PK)              │
       ├───────│ session_id (FK)  │◄─────│ user_id (FK)         │
       │        │ role             │       │ channel              │
       │        │ content          │       │ trueconf_chat_id     │
       │        │ trace (JSONB)    │       │ started_at           │
       │        │ feedback         │       │ last_activity_at     │
       │        │ feedback_comment │       └──────────────────────┘
       │        │ response_time_ms │
       │        │ created_at       │
       │        └──────────────────┘
       │
       │        ┌──────────────────┐       ┌──────────────────────┐
       │        │  sales_reports   │       │  sales_records       │
       │        ├──────────────────┤       ├──────────────────────┤
       │   1:N  │ id (PK)          │  1:N  │ id (PK)              │
       ├───────│ uploaded_by (FK) │◄─────│ report_id (FK)       │
       │        │ filename         │       │ level                │
       │        │ period_start     │       │ parent_id (FK, self) │
       │        │ period_end       │       │ name                 │
       │        │ branch           │       │ quantity             │
       │        │ status           │       │ tonnage              │
       │        │ file_path        │       │ revenue              │
       │        │ metadata (JSONB) │       │ gross_profit         │
       │        │ created_at       │       │ margin_pct           │
       │        │ processed_at     │       │ metadata (JSONB)     │
       │        └──────────────────┘       │ created_at           │
       │                                   └──────────────────────┘
       │
       │        ┌──────────────────┐
       │        │  audit_log       │
       │        ├──────────────────┤
       │   1:N  │ id (PK)          │
       └───────│ user_id (FK)     │
                │ action           │
                │ entity_type      │
                │ entity_id        │
                │ old_value (JSONB)│
                │ new_value (JSONB)│
                │ ip_address       │
                │ created_at       │
                └──────────────────┘
```

### 3.2 SQL DDL (PostgreSQL)

```sql
-- ==========================================
-- USERS & AUTH
-- ==========================================

CREATE TYPE user_role AS ENUM ('super_admin', 'admin', 'manager', 'employee');

CREATE TABLE users (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    username        VARCHAR(100) UNIQUE NOT NULL,
    email           VARCHAR(255) UNIQUE,
    full_name       VARCHAR(255),
    role            user_role NOT NULL DEFAULT 'employee',
    trueconf_id     VARCHAR(255) UNIQUE,    -- TrueConf user ID для связки
    password_hash   VARCHAR(255) NOT NULL,
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_users_trueconf ON users(trueconf_id) WHERE trueconf_id IS NOT NULL;
CREATE INDEX idx_users_role ON users(role);

-- ==========================================
-- DOCUMENTS & KNOWLEDGE BASE
-- ==========================================

CREATE TYPE document_status AS ENUM ('pending', 'processing', 'processed', 'error');
CREATE TYPE document_category AS ENUM (
    'product_catalog', 'logistics', 'policy', 'commercial',
    'certification', 'product_knowledge', 'contacts',
    'sales_methodology', 'sales_data', 'sales_analytics', 'other'
);

CREATE TABLE documents (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    uploaded_by     UUID NOT NULL REFERENCES users(id),
    filename        VARCHAR(500) NOT NULL,
    file_type       VARCHAR(20) NOT NULL,       -- pdf, docx, xlsx, xls, csv, txt, pptx
    file_path       VARCHAR(1000) NOT NULL,
    file_size       BIGINT NOT NULL,
    category        document_category NOT NULL DEFAULT 'other',
    status          document_status NOT NULL DEFAULT 'pending',
    error_message   TEXT,
    metadata        JSONB DEFAULT '{}',         -- {pages, sheets, encoding, ocr_used, ...}
    checksum_sha256 VARCHAR(64) NOT NULL,       -- дедупликация
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    processed_at    TIMESTAMPTZ
);

CREATE INDEX idx_documents_status ON documents(status);
CREATE INDEX idx_documents_category ON documents(category);
CREATE INDEX idx_documents_checksum ON documents(checksum_sha256);

CREATE TYPE knowledge_status AS ENUM ('draft', 'pending_review', 'approved', 'rejected', 'archived');

CREATE TABLE knowledge_items (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id     UUID REFERENCES documents(id) ON DELETE SET NULL,
    title           VARCHAR(500) NOT NULL,
    content         TEXT NOT NULL,
    category        document_category NOT NULL,
    status          knowledge_status NOT NULL DEFAULT 'pending_review',
    version         INT NOT NULL DEFAULT 1,
    qdrant_point_id VARCHAR(100),               -- ID точки в Qdrant
    priority        INT NOT NULL DEFAULT 50 CHECK (priority BETWEEN 1 AND 100),
    approved_by     UUID REFERENCES users(id),
    source_chunk    TEXT,                        -- оригинальный фрагмент документа
    metadata        JSONB DEFAULT '{}',         -- {page, sheet, row_range, ...}
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_knowledge_status ON knowledge_items(status);
CREATE INDEX idx_knowledge_category ON knowledge_items(category);
CREATE INDEX idx_knowledge_qdrant ON knowledge_items(qdrant_point_id);
CREATE INDEX idx_knowledge_document ON knowledge_items(document_id);

-- Версионирование знаний
CREATE TABLE knowledge_item_versions (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    item_id         UUID NOT NULL REFERENCES knowledge_items(id) ON DELETE CASCADE,
    version         INT NOT NULL,
    title           VARCHAR(500) NOT NULL,
    content         TEXT NOT NULL,
    changed_by      UUID NOT NULL REFERENCES users(id),
    change_reason   TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_ki_versions ON knowledge_item_versions(item_id, version);

-- ==========================================
-- CORPORATE MEMORY (высший приоритет)
-- ==========================================

CREATE TYPE rule_type AS ENUM (
    'communication',        -- правила общения
    'terminology',          -- терминология компании
    'preferred_phrasing',   -- предпочтительные формулировки
    'restriction',          -- ограничения ответов
    'business_rule',        -- бизнес-правила
    'system_prompt'         -- добавки к системному промпту
);

CREATE TABLE corporate_rules (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    created_by      UUID NOT NULL REFERENCES users(id),
    rule_type       rule_type NOT NULL,
    title           VARCHAR(500) NOT NULL,
    content         TEXT NOT NULL,
    priority        INT NOT NULL DEFAULT 50 CHECK (priority BETWEEN 1 AND 100),
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    category        document_category,          -- к какой области относится
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_rules_active ON corporate_rules(is_active) WHERE is_active = TRUE;
CREATE INDEX idx_rules_type ON corporate_rules(rule_type);

-- ==========================================
-- ANSWER CORRECTIONS (обучение через исправление)
-- ==========================================

CREATE TYPE correction_type AS ENUM (
    'answer_fix',           -- просто исправление ответа
    'new_knowledge',        -- из исправления извлечено новое знание
    'new_rule',             -- из исправления извлечено новое правило
    'knowledge_update'      -- исправление обновляет существующее знание
);

CREATE TABLE answer_corrections (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    created_by              UUID NOT NULL REFERENCES users(id),
    original_question       TEXT NOT NULL,
    original_answer         TEXT NOT NULL,
    corrected_answer        TEXT NOT NULL,
    correction_type         correction_type NOT NULL DEFAULT 'answer_fix',
    question_embedding      BYTEA,              -- сериализованный вектор для быстрого поиска
    priority                INT NOT NULL DEFAULT 90 CHECK (priority BETWEEN 1 AND 100),
    linked_knowledge_item_id UUID REFERENCES knowledge_items(id),
    is_active               BOOLEAN NOT NULL DEFAULT TRUE,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_corrections_active ON answer_corrections(is_active) WHERE is_active = TRUE;

-- ==========================================
-- KNOWLEDGE CONFLICTS
-- ==========================================

CREATE TYPE conflict_resolution AS ENUM ('pending', 'replace_old', 'keep_old', 'merge');

CREATE TABLE knowledge_conflicts (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    new_item_id     UUID NOT NULL REFERENCES knowledge_items(id),
    existing_item_id UUID NOT NULL REFERENCES knowledge_items(id),
    conflict_type   VARCHAR(100) NOT NULL,      -- 'contradiction', 'duplicate', 'partial_overlap'
    similarity_score FLOAT,
    new_content_preview TEXT,
    existing_content_preview TEXT,
    resolution      conflict_resolution NOT NULL DEFAULT 'pending',
    resolved_by     UUID REFERENCES users(id),
    resolved_at     TIMESTAMPTZ,
    notes           TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_conflicts_pending ON knowledge_conflicts(resolution) WHERE resolution = 'pending';

-- ==========================================
-- MODERATION QUEUE (единая очередь задач)
-- ==========================================

CREATE TYPE moderation_item_type AS ENUM (
    'new_knowledge',        -- новое знание из документа
    'self_learned',         -- знание из самообучения
    'correction_review',    -- исправление ответа на review
    'conflict',             -- конфликт знаний
    'bad_feedback'          -- негативный отзыв от пользователя
);

CREATE TYPE moderation_status AS ENUM ('pending', 'approved', 'rejected');

CREATE TABLE moderation_queue (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    item_type       moderation_item_type NOT NULL,
    item_id         UUID,                       -- FK к соответствующей таблице
    action          VARCHAR(100) NOT NULL,       -- 'approve_knowledge', 'resolve_conflict', ...
    payload         JSONB NOT NULL DEFAULT '{}', -- детали (вопрос, ответ, контекст)
    status          moderation_status NOT NULL DEFAULT 'pending',
    created_by      UUID REFERENCES users(id),
    reviewed_by     UUID REFERENCES users(id),
    reviewed_at     TIMESTAMPTZ,
    review_notes    TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_moderation_pending ON moderation_queue(status, created_at) WHERE status = 'pending';
CREATE INDEX idx_moderation_type ON moderation_queue(item_type);

-- ==========================================
-- CHAT
-- ==========================================

CREATE TABLE chat_sessions (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID NOT NULL REFERENCES users(id),
    channel         VARCHAR(50) NOT NULL DEFAULT 'trueconf',  -- 'trueconf', 'web', 'api'
    trueconf_chat_id VARCHAR(255),
    started_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_activity_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_sessions_user ON chat_sessions(user_id);
CREATE INDEX idx_sessions_trueconf ON chat_sessions(trueconf_chat_id);

CREATE TYPE message_role AS ENUM ('user', 'assistant', 'system');
CREATE TYPE feedback_type AS ENUM ('useful', 'not_useful');

CREATE TABLE chat_messages (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id      UUID NOT NULL REFERENCES chat_sessions(id) ON DELETE CASCADE,
    role            message_role NOT NULL,
    content         TEXT NOT NULL,
    trace           JSONB DEFAULT '{}',         -- {sources: [...], rules: [...], scores: [...]}
    feedback        feedback_type,
    feedback_comment TEXT,
    response_time_ms INT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_messages_session ON chat_messages(session_id, created_at);
CREATE INDEX idx_messages_feedback ON chat_messages(feedback) WHERE feedback IS NOT NULL;

-- ==========================================
-- SALES ANALYTICS
-- ==========================================

CREATE TYPE report_status AS ENUM ('pending', 'processing', 'processed', 'error');

CREATE TABLE sales_reports (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    uploaded_by     UUID NOT NULL REFERENCES users(id),
    filename        VARCHAR(500) NOT NULL,
    period_start    DATE,
    period_end      DATE,
    branch          VARCHAR(255),               -- филиал (Кольчугино, Владимир, ...)
    status          report_status NOT NULL DEFAULT 'pending',
    file_path       VARCHAR(1000) NOT NULL,
    metadata        JSONB DEFAULT '{}',         -- {sheets, total_rows, total_reps, ...}
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    processed_at    TIMESTAMPTZ
);

CREATE TYPE sales_level AS ENUM ('rep', 'client', 'product');

CREATE TABLE sales_records (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    report_id       UUID NOT NULL REFERENCES sales_reports(id) ON DELETE CASCADE,
    level           sales_level NOT NULL,
    parent_id       UUID REFERENCES sales_records(id),  -- self-referencing hierarchy
    name            TEXT NOT NULL,
    quantity        FLOAT,                      -- ед. хранения
    tonnage         FLOAT,
    revenue         FLOAT,                      -- стоимость продажи с НДС
    gross_profit    FLOAT,                      -- валовая прибыль
    margin_pct      FLOAT,                      -- рентабельность %
    metadata        JSONB DEFAULT '{}',         -- {address, sku_code, brand, ...}
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_sales_report ON sales_records(report_id);
CREATE INDEX idx_sales_level ON sales_records(level);
CREATE INDEX idx_sales_parent ON sales_records(parent_id);
CREATE INDEX idx_sales_margin ON sales_records(margin_pct) WHERE level = 'rep';

-- ==========================================
-- AUDIT LOG
-- ==========================================

CREATE TABLE audit_log (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID REFERENCES users(id),
    action          VARCHAR(100) NOT NULL,       -- 'login', 'upload_document', 'approve_knowledge', ...
    entity_type     VARCHAR(100),                -- 'document', 'knowledge_item', 'rule', ...
    entity_id       UUID,
    old_value       JSONB,
    new_value       JSONB,
    ip_address      INET,
    user_agent      TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_audit_user ON audit_log(user_id, created_at);
CREATE INDEX idx_audit_entity ON audit_log(entity_type, entity_id);
CREATE INDEX idx_audit_action ON audit_log(action, created_at);

-- Партиционирование по месяцам (для больших объёмов)
-- CREATE TABLE audit_log (...) PARTITION BY RANGE (created_at);

-- ==========================================
-- SCHEDULED TASKS & SYSTEM
-- ==========================================

CREATE TABLE system_settings (
    key             VARCHAR(100) PRIMARY KEY,
    value           JSONB NOT NULL,
    updated_by      UUID REFERENCES users(id),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Начальные настройки
INSERT INTO system_settings (key, value) VALUES
    ('llm_provider', '{"primary": "groq", "fallback": "openai"}'),
    ('llm_model', '{"chat": "llama-3.3-70b-versatile", "analysis": "llama-3.3-70b-versatile", "embeddings": "text-embedding-3-small"}'),
    ('rag_config', '{"top_k": 10, "score_threshold": 0.35, "rerank": true}'),
    ('self_learning_enabled', 'true'),
    ('max_context_tokens', '8000');
```

---

## 4. Структура Qdrant

### 4.1 Коллекции

```yaml
collections:
  # === Основная коллекция знаний ===
  knowledge_base:
    vectors:
      size: 1536          # text-embedding-3-small
      distance: Cosine
    optimizers:
      indexing_threshold: 20000
    payload_schema:
      knowledge_item_id:  keyword   # UUID из PostgreSQL
      document_id:        keyword   # UUID документа-источника
      category:           keyword   # product_catalog, logistics, policy, ...
      status:             keyword   # approved, pending_review, ...
      priority:           integer   # 1-100
      title:              text      # для full-text search
      content_preview:    text      # первые 500 символов
      version:            integer
      created_at:         datetime
      metadata:           keyword   # JSON-строка с доп. данными

  # === Коллекция коррекций ответов ===
  answer_corrections:
    vectors:
      size: 1536
      distance: Cosine
    payload_schema:
      correction_id:      keyword
      original_question:  text
      corrected_answer:   text
      correction_type:    keyword
      priority:           integer
      is_active:          bool
      created_at:         datetime

  # === Коллекция для поиска конфликтов ===
  # (используется та же knowledge_base, но с фильтрами)
```

### 4.2 Стратегия RAG-поиска

```
STEP 1: Query Analysis
  ├── Определение intent: knowledge_query | sales_query | analytics_query
  ├── Определение category: product_catalog | policy | contacts | ...
  └── Извлечение entities: SKU, ТП имя, клиент, период

STEP 2: Correction Check (HIGHEST PRIORITY)
  ├── Embed(question) → search answer_corrections (cosine > 0.92)
  ├── Hit? → return correction.answer + trace{type: "correction", id}
  └── Miss? → continue

STEP 3: Corporate Rules Loading (HIGH PRIORITY)
  ├── SELECT * FROM corporate_rules WHERE is_active=true ORDER BY priority DESC
  └── Inject into system prompt (rules with highest priority first)

STEP 4: Vector Search
  ├── Embed(question) → vector
  ├── Qdrant search: knowledge_base
  │     filter: {status: "approved", category: [detected_categories]}
  │     limit: 10
  │     score_threshold: 0.35
  ├── Results sorted by: (qdrant_score * 0.6) + (priority * 0.004)
  │     (priority 100 → +0.4 boost, priority 50 → +0.2 boost)
  └── Deduplicate by content similarity (>0.95 cosine → keep highest score)

STEP 5: Context Assembly
  ├── corporate_rules (всегда включены в system prompt)
  ├── top-N RAG results (N=5-8, в зависимости от score)
  ├── Total context ≤ 8000 tokens
  └── If sales_query → add structured sales data from PostgreSQL

STEP 6: LLM Generation
  ├── System: "Ты корпоративный ИИ-ассистент ТД Мир Мороженого. {rules}
  │            Отвечай ТОЛЬКО на основе предоставленного контекста.
  │            Если информации нет — скажи: 'Информация отсутствует в базе знаний.'
  │            Указывай источники информации."
  ├── Context: "{RAG_results}"
  ├── User: "{question}"
  └── Generate with temperature=0.1

STEP 7: Tracing
  └── Save to chat_messages.trace:
      {
        "sources": [{"doc_id", "title", "score", "chunk_preview"}],
        "rules_applied": [{"rule_id", "title", "priority"}],
        "corrections_checked": true/false,
        "correction_used": null | {"id", "score"},
        "rag_scores": [0.78, 0.65, ...],
        "model": "llama-3.3-70b",
        "tokens_used": 1234,
        "response_time_ms": 890
      }
```

### 4.3 Стратегия чанкинга

```python
CHUNKING_CONFIG = {
    # Документы (DOCX, PDF text)
    "text_documents": {
        "method": "semantic",           # разбиение по смысловым блокам
        "chunk_size": 800,              # ~800 токенов
        "overlap": 100,                 # перекрытие
        "separators": ["\n\n", "\n", ". ", "; "],
    },
    # Таблицы продуктов (XLS/XLSX)
    "product_table": {
        "method": "row_based",          # каждая строка = 1 chunk
        "template": "Продукт: {name}. Артикул: {article}. "
                    "Состав: {composition}. "
                    "БЗМЖ/ЗМЖ: {zmj}. Срок годности: {shelf_life} мес. "
                    "Штрихкод: {barcode}. Пищевая ценность: {nutrition}. "
                    "Энергетическая ценность: {energy}. "
                    "Паллетизация: {pallet_qty} шт/паллет. "
                    "Декларация: {declaration}.",
    },
    # Политики и регламенты
    "policy_documents": {
        "method": "section_based",       # разбиение по разделам (1., 2., ...)
        "max_chunk_size": 1200,
        "preserve_headers": True,
    },
    # Контакты
    "contacts": {
        "method": "row_based",
        "template": "{name}, {position}, email: {email}, тел: {phone}",
    },
}
```

---

## 5. Структура API

### 5.1 Маршруты

```yaml
# ==========================================
# AUTH
# ==========================================
POST   /api/auth/login              # JWT login
POST   /api/auth/refresh            # Refresh token
GET    /api/auth/me                 # Current user
POST   /api/auth/change-password    # Change password

# ==========================================
# CHAT (TrueConf + Web)
# ==========================================
POST   /api/chat/ask                # Задать вопрос (+ trace)
POST   /api/chat/feedback           # Оценка ответа (useful/not_useful)
GET    /api/chat/history            # История чата
GET    /api/chat/sessions           # Список сессий
GET    /api/chat/messages/{session_id}  # Сообщения сессии

# ==========================================
# TRUECONF WEBHOOK
# ==========================================
POST   /api/trueconf/webhook        # Incoming messages from TrueConf
GET    /api/trueconf/status         # Статус подключения к TrueConf

# ==========================================
# KNOWLEDGE BASE (Admin)
# ==========================================
# Документы
POST   /api/knowledge/documents/upload   # Загрузка документа
GET    /api/knowledge/documents          # Список документов
GET    /api/knowledge/documents/{id}     # Детали документа
DELETE /api/knowledge/documents/{id}     # Удаление документа
POST   /api/knowledge/documents/{id}/reprocess  # Переобработка

# Знания
GET    /api/knowledge/items              # Список знаний (фильтр по category, status)
GET    /api/knowledge/items/{id}         # Детали знания
PUT    /api/knowledge/items/{id}         # Редактирование знания
DELETE /api/knowledge/items/{id}         # Удаление (soft delete → archived)
GET    /api/knowledge/items/{id}/versions  # История версий

# Поиск
POST   /api/knowledge/search            # Поиск по базе знаний (vector + text)
POST   /api/knowledge/reindex           # Полная переиндексация Qdrant

# ==========================================
# CORPORATE MEMORY (Admin)
# ==========================================
GET    /api/rules                        # Список правил
POST   /api/rules                        # Создание правила
PUT    /api/rules/{id}                   # Редактирование
DELETE /api/rules/{id}                   # Удаление
PATCH  /api/rules/{id}/toggle            # Вкл/выкл правило

# ==========================================
# ANSWER CORRECTIONS (Admin)
# ==========================================
GET    /api/corrections                  # Список коррекций
POST   /api/corrections                  # Создание коррекции (из чата)
PUT    /api/corrections/{id}             # Редактирование
DELETE /api/corrections/{id}             # Удаление

# ==========================================
# MODERATION QUEUE (Admin)
# ==========================================
GET    /api/moderation                   # Очередь на модерацию
GET    /api/moderation/{id}              # Детали задачи
POST   /api/moderation/{id}/approve      # Одобрить
POST   /api/moderation/{id}/reject       # Отклонить
GET    /api/moderation/stats             # Статистика очереди

# ==========================================
# KNOWLEDGE CONFLICTS (Admin)
# ==========================================
GET    /api/conflicts                    # Список конфликтов
GET    /api/conflicts/{id}               # Детали конфликта
POST   /api/conflicts/{id}/resolve       # Разрешение (replace/keep/merge)

# ==========================================
# SALES ANALYTICS (Admin + Manager)
# ==========================================
# Отчёты
POST   /api/sales/reports/upload         # Загрузка отчёта
GET    /api/sales/reports                # Список отчётов
GET    /api/sales/reports/{id}           # Детали отчёта
DELETE /api/sales/reports/{id}           # Удаление

# Аналитика
GET    /api/sales/analytics/overview     # Общий обзор (revenue, profit, margin)
GET    /api/sales/analytics/reps         # Анализ ТП
GET    /api/sales/analytics/reps/{id}    # Детали по ТП
GET    /api/sales/analytics/clients      # Анализ клиентов
GET    /api/sales/analytics/products     # Анализ продуктов
GET    /api/sales/analytics/trends       # Тренды (при наличии нескольких периодов)

# ИИ-аналитика
POST   /api/sales/ai/recommendations     # AI-рекомендации
POST   /api/sales/ai/ask                 # Свободный вопрос к данным продаж

# ==========================================
# MONITORING & ADMIN
# ==========================================
GET    /api/monitoring/stats              # Общая статистика системы
GET    /api/monitoring/health             # Health check
GET    /api/monitoring/usage              # Использование LLM (токены, стоимость)
GET    /api/audit                         # Лог аудита (фильтр по action, user, date)

# ==========================================
# USERS (Super Admin)
# ==========================================
GET    /api/users                         # Список пользователей
POST   /api/users                         # Создание пользователя
PUT    /api/users/{id}                    # Редактирование
DELETE /api/users/{id}                    # Деактивация
PATCH  /api/users/{id}/role               # Смена роли
```

### 5.2 Схемы запросов/ответов (ключевые)

```python
# POST /api/chat/ask
class ChatRequest(BaseModel):
    question: str
    session_id: Optional[UUID] = None
    channel: str = "web"  # "trueconf" | "web"

class ChatResponse(BaseModel):
    answer: str
    session_id: UUID
    message_id: UUID
    sources: list[SourceInfo]       # документы-источники
    rules_applied: list[RuleInfo]   # применённые правила
    confidence: float               # 0-1
    response_time_ms: int

class SourceInfo(BaseModel):
    document_id: UUID
    document_title: str
    relevance_score: float
    chunk_preview: str              # первые 200 символов

class RuleInfo(BaseModel):
    rule_id: UUID
    title: str
    rule_type: str
    priority: int

# POST /api/corrections
class CorrectionCreate(BaseModel):
    message_id: UUID                # ID сообщения с ошибочным ответом
    corrected_answer: str
    correction_type: str = "auto_detect"  # система определит тип автоматически
    notes: Optional[str] = None

# POST /api/conflicts/{id}/resolve
class ConflictResolve(BaseModel):
    resolution: str                 # "replace_old" | "keep_old" | "merge"
    merged_content: Optional[str]   # обязательно при "merge"
    notes: Optional[str] = None
```

---

## 6. Архитектура ИИ-агента

### 6.1 Многоуровневая система приоритетов

```
ПРИОРИТЕТ (от высшего к низшему):

1. КОРРЕКЦИИ АДМИНИСТРАТОРА (priority 90-100)
   └── Если вопрос совпадает с существующей коррекцией (cosine > 0.92)
       → вернуть исправленный ответ, пропустить RAG

2. КОРПОРАТИВНАЯ ПАМЯТЬ (priority по полю, всегда в system prompt)
   ├── system_prompt rules (формируют "личность" ИИ)
   ├── restrictions (запреты, ограничения)
   ├── terminology (обязательные термины)
   ├── preferred_phrasing (предпочтительные формулировки)
   ├── communication rules (стиль общения)
   └── business_rules (бизнес-логика)

3. ЗНАНИЯ ИЗ БАЗЫ ЗНАНИЙ (priority по полю, score > 0.35)
   ├── category = policy, product_catalog → повышенный приоритет
   └── Отсортированы по (score * 0.6 + priority * 0.004)

4. ДАННЫЕ ИЗ SALES ANALYTICS (если запрос про продажи)
   └── SQL-запрос к PostgreSQL → структурированный ответ

5. FALLBACK
   └── "Информация отсутствует в базе знаний."
```

### 6.2 Архитектура обработки исправлений

```
Администратор нажимает "Исправить ответ" на сообщении в админке
       │
       ▼
POST /api/corrections {message_id, corrected_answer}
       │
       ▼
CorrectionService.create():
  1. Загрузить оригинальное сообщение (question + answer)
  2. Embed(corrected_answer) → vector
  3. Определить correction_type через LLM:
     │
     ├── Промпт: "Проанализируй исправление.
     │            Оригинальный вопрос: {question}
     │            Старый ответ: {original_answer}
     │            Новый ответ: {corrected_answer}
     │            
     │            Определи тип:
     │            - answer_fix: простое исправление формулировки
     │            - new_knowledge: ответ содержит информацию,
     │              отсутствующую в базе знаний
     │            - new_rule: ответ содержит новое правило/ограничение
     │            - knowledge_update: ответ корректирует существующее знание
     │            
     │            Также извлеки:
     │            - suggested_knowledge: текст для добавления в БЗ (если есть)
     │            - suggested_rule: текст правила (если есть)"
     │
     ▼
  4. Сохранить correction в PostgreSQL
  5. Добавить embedding в Qdrant (answer_corrections collection)
  6. Если correction_type != 'answer_fix':
     └── Создать задачу в moderation_queue:
         - new_knowledge → "Подтвердить новое знание из исправления"
         - new_rule → "Подтвердить новое правило из исправления"
         - knowledge_update → "Подтвердить обновление знания"
```

### 6.3 Механизм самообучения

```
TRIGGERS:
  ├── Новый документ загружен → extract_knowledge_task
  ├── Новый чат-сообщение → analyze_message_task (batch, каждые 6 часов)
  └── Новый отчёт загружен → analyze_report_task

extract_knowledge_task(document_id):
  1. Извлечь текст → chunk → embed
  2. Для каждого chunk:
     a. LLM: извлечь структурированные знания
     b. Для каждого извлечённого знания:
        - Search Qdrant: найти похожие (cosine > 0.85)
        - Если найдено похожее:
          └── Создать conflict_check_task
        - Если не найдено:
          └── Создать knowledge_item (status=pending_review)
          └── Создать задачу в moderation_queue
  3. НИКОГДА не добавлять знания автоматически (status != approved)

conflict_check_task(new_item_id, similar_items):
  1. LLM: "Сравни два фрагмента знаний.
           Новый: {new_content}
           Существующий: {existing_content}
           Определи: 'no_conflict', 'contradiction', 'duplicate', 'partial_overlap'"
  2. Если conflict:
     └── Создать knowledge_conflict (resolution=pending)
     └── Создать задачу в moderation_queue (item_type=conflict)

analyze_message_task():
  1. Выбрать сообщения за последние 6 часов
  2. Для сообщений с feedback='not_useful':
     └── Создать задачу в moderation_queue (item_type=bad_feedback)
  3. Для сообщений без match в RAG (confidence < 0.3):
     └── LLM: "Какой информации не хватает для ответа на: {question}?"
     └── Создать задачу в moderation_queue с рекомендацией
```

### 6.4 Система трассировки ответов

Каждый ответ ИИ сопровождается объектом `trace` в JSONB:

```json
{
  "version": 1,
  "timestamp": "2026-06-22T12:00:00Z",
  "model": "llama-3.3-70b-versatile",
  "provider": "groq",
  
  "pipeline": {
    "correction_check": {
      "checked": true,
      "best_match_score": 0.45,
      "used": false
    },
    "rag_search": {
      "query_embedding_model": "text-embedding-3-small",
      "results_count": 8,
      "results_after_threshold": 5,
      "threshold": 0.35,
      "categories_searched": ["product_catalog", "logistics"]
    },
    "rules_loaded": 3,
    "context_tokens": 4200,
    "generation_tokens": 350
  },
  
  "sources": [
    {
      "type": "knowledge_item",
      "id": "uuid-1",
      "document_id": "uuid-doc-1",
      "document_title": "Логист. данные Айс-групп 2026",
      "title": "Брикет На двойных сливках пломбир 80г",
      "category": "product_catalog",
      "score": 0.82,
      "priority": 50,
      "chunk_preview": "Брикет 'На двойных сливках пломбир' 80г*28..."
    },
    {
      "type": "knowledge_item",
      "id": "uuid-2",
      "document_id": "uuid-doc-2",
      "document_title": "Политика управления ПДЗ",
      "title": "Кредитные лимиты розничных клиентов",
      "category": "policy",
      "score": 0.67,
      "priority": 70,
      "chunk_preview": "Кредитные лимиты (лето): до 40 тыс.руб..."
    }
  ],
  
  "rules_applied": [
    {
      "id": "uuid-rule-1",
      "title": "Не выдавать данные конкурентов",
      "type": "restriction",
      "priority": 90
    },
    {
      "id": "uuid-rule-2",
      "title": "Использовать 'Вы' при обращении",
      "type": "communication",
      "priority": 80
    }
  ],
  
  "performance": {
    "embedding_ms": 120,
    "qdrant_search_ms": 45,
    "rules_load_ms": 5,
    "llm_generation_ms": 720,
    "total_ms": 890
  }
}
```

---

## 7. Архитектура админ-панели

### 7.1 Структура страниц

```
SIDEBAR NAVIGATION:

📊 Dashboard (/)
   └── KPI: запросов сегодня, ожидает модерации, средняя оценка, активных ТП

💬 Чаты (/chats)
   ├── Список сессий с фильтрами (канал, дата, пользователь)
   ├── Просмотр диалога с trace (источники, правила, scores)
   └── Кнопка "Исправить ответ" на каждом сообщении assistant

📚 База знаний (/knowledge)
   ├── /knowledge/documents — загрузка, список, статусы обработки
   ├── /knowledge/items — список знаний, фильтр по категории/статусу
   │    └── Редактирование, удаление, просмотр версий
   └── /knowledge/search — тестовый поиск по базе (вектор + текст)

🎓 Обучение (/training)
   ├── /training/rules — корпоративные правила (CRUD, приоритеты, типы)
   ├── /training/corrections — исправления ответов (из чатов + ручные)
   └── /training/reindex — запуск переиндексации Qdrant

✅ Модерация (/moderation)
   ├── Единая очередь (бейдж с кол-вом pending)
   ├── Фильтр по типу: new_knowledge, self_learned, conflict, bad_feedback
   └── Approve / Reject с комментарием

⚡ Конфликты (/conflicts)
   ├── Список нерешённых конфликтов
   └── Карточка конфликта: старое vs новое знание
       └── Действия: заменить / оставить / объединить (с редактором)

📈 Аналитика продаж (/sales)
   ├── /sales/reports — загрузка и список отчётов
   ├── /sales/overview — общий дашборд (выручка, прибыль, маржа)
   ├── /sales/reps — рейтинг ТП (таблица + графики)
   │    └── Детальная карточка ТП (клиенты, продукты, тренды)
   ├── /sales/clients — анализ клиентов
   ├── /sales/products — анализ продуктов
   ├── /sales/ai — AI-рекомендации + свободные вопросы
   └── /sales/compare — сравнение периодов (если несколько отчётов)

📊 Мониторинг (/monitoring)
   ├── Системная статистика (документы, знания, пользователи)
   ├── Использование LLM (токены, стоимость, задержки)
   └── Качество ответов (% полезных, средний score)

👥 Пользователи (/users) — только super_admin
   └── CRUD пользователей, назначение ролей

📋 Аудит (/audit)
   └── Лог всех действий с фильтрами
```

### 7.2 Ролевая модель

| Действие | super_admin | admin | manager | employee |
|---|:---:|:---:|:---:|:---:|
| Задавать вопросы ИИ | + | + | + | + |
| Просматривать чаты | + | + | + | свои |
| Загружать документы | + | + | - | - |
| Управлять знаниями | + | + | - | - |
| Модерация | + | + | - | - |
| Исправлять ответы | + | + | + | - |
| Корпоративные правила | + | + | - | - |
| Загружать отчёты | + | + | + | - |
| Аналитика продаж | + | + | + | - |
| Управлять пользователями | + | - | - | - |
| Аудит | + | + | - | - |
| Системные настройки | + | - | - | - |

---

## 8. Очереди фоновых задач

### 8.1 Архитектура (Redis + arq)

```python
# Worker pools
WORKERS = {
    "document_worker": {
        "concurrency": 2,
        "queue": "documents",
        "tasks": [
            "process_document",      # извлечение текста, OCR, chunking
            "extract_knowledge",     # LLM-извлечение знаний
            "reindex_document",      # переиндексация конкретного документа
        ]
    },
    "analytics_worker": {
        "concurrency": 1,
        "queue": "analytics",
        "tasks": [
            "parse_sales_report",    # парсинг XLS → sales_records
            "generate_recommendations",  # AI-рекомендации
        ]
    },
    "knowledge_worker": {
        "concurrency": 1,
        "queue": "knowledge",
        "tasks": [
            "check_conflicts",       # проверка конфликтов для нового знания
            "full_reindex",          # полная переиндексация Qdrant
            "classify_correction",   # определение типа коррекции через LLM
        ]
    },
    "self_learning_worker": {
        "concurrency": 1,
        "queue": "self_learning",
        "tasks": [
            "analyze_chat_messages",  # анализ чат-сообщений (каждые 6 часов)
            "analyze_new_report",     # анализ нового отчёта
        ]
    }
}
```

### 8.2 Пайплайн обработки документов

```
UPLOAD → validate → enqueue(process_document)

process_document(document_id):
  1. Определить тип файла
  2. Извлечь текст:
     ├── DOCX → python-docx (paragraphs + tables)
     ├── PDF → PyPDF2 (text) → если пусто → Tesseract OCR
     ├── XLSX/XLS → pandas (все sheets) → structured text
     ├── PPTX → python-pptx (slides + shapes)
     ├── CSV → pandas → structured text
     └── TXT → plain read
  3. Определить категорию (LLM или rule-based по ключевым словам)
  4. Chunk по стратегии (см. п. 4.3)
  5. Embed каждый chunk
  6. Для каждого chunk:
     a. Upsert в Qdrant (status=pending_review)
     b. Создать knowledge_item (status=pending_review)
  7. Enqueue(extract_knowledge, document_id)
  8. Обновить document.status = 'processed'

extract_knowledge(document_id):
  1. Загрузить все chunks документа
  2. LLM: "Извлеки ключевые факты, правила и знания из текста.
           Каждое знание оформи как отдельный пункт с title и content."
  3. Для каждого извлечённого знания:
     a. Embed → search Qdrant (top-3 similar, score > 0.85)
     b. Если есть высокопохожие → enqueue(check_conflicts)
     c. Создать knowledge_item (status=pending_review)
     d. Создать moderation_queue entry
```

### 8.3 Пайплайн обработки Excel-отчётов

```
parse_sales_report(report_id):
  1. Загрузить файл (xlrd для .xls, openpyxl для .xlsx)
  2. Определить формат:
     ├── Проверить заголовки (row 7-9): "Основной менеджер", "Покупатель", "Номенклатура"
     ├── Извлечь период из metadata (row 1): "Период: DD.MM.YYYY - DD.MM.YYYY"
     └── Извлечь фильтры (row 4): "Покупатель В группе из списка (КОЛЬЧУГИНО филиал)"
  
  3. Парсинг иерархии (КЛЮЧЕВАЯ ЛОГИКА):
     ├── Детекция уровней по паттернам:
     │   Level 0 (ТП): col[1] содержит ФИО (regex: [А-Я][а-я]+ [А-Я][а-я]+ [А-Я][а-я]+)
     │                  + revenue > 500_000 (порог для ТП)
     │   Level 1 (Клиент): col[1] содержит ООО/ИП/Киоск/Магазин/название (+ адрес в скобках)
     │                      + revenue > 1_000 
     │   Level 2 (SKU): col[1] содержит название продукта (Стак./Рожок/Эскимо/Брикет/...)
     │
     ├── Fallback: использовать outline_levels если xlrd их предоставляет
     │
     └── Валидация: sum(children.revenue) ≈ parent.revenue (±5%)
  
  4. Сохранение в sales_records с parent_id (self-referencing)
  
  5. Расчёт агрегатов:
     ├── По ТП: total_revenue, total_profit, avg_margin, client_count, product_count
     ├── По клиентам: revenue, profit, margin, product_count, top_products
     └── По продуктам: cross-TP popularity, avg_margin, total_tonnage
  
  6. AI-анализ:
     └── LLM: "Проанализируй данные продаж:
              {structured_data}
              Определи:
              - Лучших и слабых ТП (по выручке и маржинальности)
              - Низкомаржинальных клиентов
              - Зависимость от отдельных SKU
              - Точки роста
              - Управленческие рекомендации"
```

---

## 9. Безопасность

### 9.1 Роли и права

```
super_admin (1 пользователь):
  - Полный доступ ко всему
  - Управление пользователями
  - Системные настройки
  - Аудит

admin:
  - Управление базой знаний
  - Модерация
  - Корпоративные правила
  - Аналитика
  - Исправление ответов

manager:
  - Просмотр чатов
  - Загрузка отчётов
  - Аналитика продаж
  - Исправление ответов

employee:
  - Задавать вопросы через TrueConf / Web
  - Просматривать свои чаты
  - Оставлять обратную связь
```

### 9.2 Хранение токенов и секретов

```yaml
# JWT
JWT_ACCESS_TOKEN_EXPIRE: 30 minutes
JWT_REFRESH_TOKEN_EXPIRE: 7 days
JWT_ALGORITHM: HS256
JWT_SECRET: из переменной окружения (32+ random bytes, base64)

# Хранение секретов
Secrets Storage:
  - API keys (Groq, OpenAI): переменные окружения (.env файл, не в git)
  - JWT secret: переменная окружения
  - DB password: переменная окружения
  - TrueConf Bot Token: переменная окружения
  - Redis password: переменная окружения

# Password hashing
Algorithm: bcrypt (rounds=12)
```

### 9.3 Аудит

Все действия логируются в `audit_log`:

```python
AUDITED_ACTIONS = [
    "login", "logout", "login_failed",
    "upload_document", "delete_document",
    "create_knowledge", "update_knowledge", "delete_knowledge",
    "approve_moderation", "reject_moderation",
    "create_rule", "update_rule", "delete_rule",
    "create_correction", "update_correction",
    "resolve_conflict",
    "upload_report",
    "create_user", "update_user", "deactivate_user", "change_role",
    "change_password",
    "reindex_knowledge",
    "change_system_setting",
]
```

### 9.4 Резервное копирование

```bash
# Crontab (ежедневно в 03:00)

# PostgreSQL
0 3 * * * pg_dump -Fc trueconf_agent > /backups/pg/trueconf_agent_$(date +%Y%m%d).dump

# Qdrant snapshots
0 3 * * * curl -X POST http://localhost:6333/collections/knowledge_base/snapshots

# Uploads directory
0 4 * * * tar -czf /backups/uploads/uploads_$(date +%Y%m%d).tar.gz /app/uploads/

# Retention: 30 дней
0 5 * * * find /backups/ -mtime +30 -delete
```

### 9.5 Защита базы знаний

- Все мутации знаний проходят через модерацию (кроме super_admin)
- Soft delete (status → archived), без физического удаления
- Версионирование всех изменений (knowledge_item_versions)
- Rate limiting на API (Redis, 100 req/min для чата, 10 req/min для загрузки)
- Checksumming документов (дедупликация)
- Запрет на изменение знаний через чат (только через админку)

---

## 10. Roadmap разработки

### Фаза 1: Core Infrastructure (2 недели)

```
Week 1:
  ├── Настройка проекта: Docker Compose (PostgreSQL, Qdrant, Redis, FastAPI)
  ├── SQLAlchemy модели + Alembic миграции (все таблицы из п. 3.2)
  ├── Auth: JWT login/refresh, ролевая модель, middleware
  ├── Users CRUD (super_admin)
  └── Audit log middleware

Week 2:
  ├── Redis: подключение, кэш, rate limiter
  ├── arq workers: базовая конфигурация 4-х пулов
  ├── Nginx: reverse proxy, SSL, static
  ├── Health check endpoint
  └── CI/CD: Docker build + deploy script
```

### Фаза 2: Knowledge Base (2 недели)

```
Week 3:
  ├── Document upload + storage
  ├── Document processing pipeline:
  │   ├── DOCX, PDF (text), XLSX/XLS, PPTX, CSV, TXT extractors
  │   ├── OCR pipeline (Tesseract) для PDF-сканов
  │   └── Chunking strategies (text, row_based, section_based)
  ├── Qdrant integration: upsert, search, delete
  └── Embedding service (OpenAI text-embedding-3-small)

Week 4:
  ├── Knowledge items CRUD
  ├── Knowledge versioning
  ├── RAG search pipeline (full flow: embed → search → rerank → threshold)
  ├── Corporate rules CRUD
  ├── Knowledge reindex endpoint
  └── Conflict detection pipeline
```

### Фаза 3: AI Agent (2 недели)

```
Week 5:
  ├── Chat service: full RAG pipeline с приоритетами
  ├── Answer tracing (trace JSONB)
  ├── LLM integration: Groq primary + OpenAI fallback
  ├── Answer corrections: create, classify (LLM), embed
  ├── Correction matching в chat pipeline
  └── Chat sessions & history

Week 6:
  ├── Self-learning pipeline:
  │   ├── Knowledge extraction from documents
  │   ├── Chat message analysis
  │   └── Moderation queue integration
  ├── Conflict resolution flow
  ├── Knowledge conflict detection + merge UI data
  └── Feedback processing (useful/not_useful → moderation)
```

### Фаза 4: Sales Analytics (1.5 недели)

```
Week 7:
  ├── Sales report upload + XLS/XLSX parser
  ├── Hierarchical parser (ТП → Клиент → SKU)
  ├── Sales analytics endpoints (overview, reps, clients, products)
  ├── AI recommendations pipeline
  └── Free-form sales Q&A
```

### Фаза 5: TrueConf Integration (1 неделя)

```
Week 8:
  ├── TrueConf Chatbot Connector: WebSocket + REST
  ├── User mapping: TrueConf ID → users.trueconf_id
  ├── Message routing: TrueConf → chat/ask → TrueConf
  ├── Rich formatting для ответов (markdown → TrueConf)
  └── Connection monitoring + reconnect
```

### Фаза 6: Admin Panel (2 недели)

```
Week 9:
  ├── React project setup (Vite + TailwindCSS + Shadcn/UI)
  ├── Auth pages: login, session management
  ├── Dashboard: KPI cards
  ├── Knowledge: documents list, upload, items list/edit
  ├── Training: rules CRUD, corrections list
  └── Moderation: queue, approve/reject

Week 10:
  ├── Chat viewer: sessions list, dialog view, trace modal, "Исправить" button
  ├── Conflicts: list, detail, resolve (replace/keep/merge editor)
  ├── Sales: report upload, overview dashboard, reps/clients/products tables
  ├── Sales AI: recommendations, free Q&A
  ├── Monitoring: stats, LLM usage, quality metrics
  ├── Users management
  └── Audit log viewer
```

### Фаза 7: Polish & Deploy (1 неделя)

```
Week 11:
  ├── E2E тестирование полного flow
  ├── Загрузка реальных документов в продакшн
  ├── Настройка бэкапов
  ├── Performance tuning (Qdrant indexing, PostgreSQL indexes)
  ├── Мониторинг (Prometheus + Grafana или simple /monitoring)
  └── Документация для администратора
```

**Итого: ~11 недель**

---

## 11. Возможные проблемы и решения

### 11.1 Технические

| Проблема | Решение |
|---|---|
| **PDF-сканы не содержат текста** (Каталог, Книга продаж, Декларации — все scan-based) | Tesseract OCR + pytesseract. Для русского языка: `tessdata_best/rus.traineddata`. Quality check: если OCR confidence < 60% → пометить документ как "требует ручной проверки" |
| **Неструктурированный XLS** (парсинг иерархии ТП→Клиент→SKU без outline_levels) | Эвристический парсер с multi-signal detection: regex ФИО для ТП, ООО/ИП/Киоск для клиентов, SKU-pattern для продуктов + валидация суммами. Fallback: LLM-классификация строк |
| **Groq rate limits / downtime** | Dual-provider: Groq primary → OpenAI fallback. Retry с exponential backoff. Redis queue для batch-операций. Для embeddings: OpenAI (стабильнее) |
| **Qdrant memory** (~170 SKU + будущий рост документов) | При 10K vectors * 1536 dims * 4 bytes = ~60 MB. Qdrant в Docker с 512 MB memory limit достаточно для 100K+ vectors |
| **Долгая обработка больших PDF** (Книга продаж 52 MB, 56 страниц) | Background worker с progress reporting. OCR по страницам с progress (Redis pub/sub). Timeout 10 минут на документ |
| **Конфликтующие ответы при обновлении знаний** | Две линии защиты: 1) Автоматическое обнаружение конфликтов (cosine > 0.85 + LLM-comparison), 2) Все изменения через модерацию |

### 11.2 Бизнес-логика

| Проблема | Решение |
|---|---|
| **ИИ "галлюцинирует" ответы** | Строгий system prompt: "ТОЛЬКО из контекста". Score threshold 0.35. Если ничего не найдено → "Информация отсутствует". temperature=0.1. Обязательная трассировка |
| **Пользователь спрашивает о конкурентах** | Corporate rule (restriction): "Не предоставлять информацию о конкурентах. Перенаправлять к руководителю" |
| **Конфиденциальные данные в ответах** | Corporate rule (restriction): "Не раскрывать внутренние финансовые показатели сотрудникам с ролью employee. Только обобщённые данные" |
| **Разные форматы отчётов** | Configurable parser с template detection. При неизвестном формате → LLM для определения структуры + создание задачи на ревью |
| **Множество филиалов** (Кольчугино, Владимир, ...) | branch field в sales_reports + фильтрация во всех analytics endpoints. Знания могут быть помечены branch-specific metadata |

### 11.3 Масштабирование

| Этап | Нагрузка | Рекомендация |
|---|---|---|
| MVP | <50 пользователей, <1000 знаний | Single VPS (4 CPU, 8 GB RAM), SQLite→PostgreSQL, single Qdrant |
| Production | 50-500 пользователей, <10K знаний | VPS (8 CPU, 16 GB RAM), PostgreSQL с connection pooling (pgbouncer), Redis cluster mode |
| Enterprise | 500+ пользователей, 10K+ знаний | Qdrant cluster, PostgreSQL replica, Redis Sentinel, horizontal scaling workers |
