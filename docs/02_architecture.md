# Архитектура Production Navigator

## Статус и границы

Документ разделяет **CURRENT**, **TARGET MVP** и **LATER**. TARGET MVP —
утверждённое направление, а не заявление о наличии реализации. Окончательные
ORM/API-контракты новых concepts требуют отдельного design stage.

## 1. Архитектурная цель TARGET MVP

```text
EnterpriseProfile
→ Capability Profile
→ ProcurementOpportunity ingestion / normalization
→ Matching Engine
→ Explainability
→ Scoring / Ranking
→ TOP-10
```

Первый value slice принимает подготовленный набор opportunities, сравнивает
его с одним профилем и возвращает воспроизводимый TOP-10. Live source adapter,
frontend, execution lifecycle и ML не являются prerequisite.

### 1.1 Ограничение выполнения первой версии: один оператор

Целевая модель выполнения первой версии — один оператор и последовательное
изменение производственного профиля. Одновременное конкурентное редактирование
одного профиля несколькими пользователями не поддерживается.

В первой версии не проектируются `User`, Auth, RBAC, роли и permissions,
пользовательские сессии, optimistic locking, механизмы конфликтов конкурентного
редактирования, audit log и multi-tenancy. Это LATER scope, а не постоянное
архитектурное ограничение системы.

Однопользовательская граница не отменяет обычную целостность данных. В первой
версии обязательны:

- одна transaction для одной бизнес-операции, изменяющей несколько связанных
  записей;
- DB constraints `FK`, `UNIQUE` и `CHECK`;
- rollback всех связанных изменений при ошибке;
- согласованное изменение состояния полноты раздела вместе с изменением его
  данных.

Обычная транзакционная целостность не является многопользовательской функцией и
не переносится в LATER. Архитектура не должна намеренно препятствовать будущему
многопользовательскому режиму, но его механизмы не реализуются заранее и не
являются условием первого TOP-10.

## 2. CURRENT architecture

Текущий backend — асинхронное FastAPI-приложение на Python 3.12+ с SQLAlchemy
2, Alembic, PostgreSQL/`asyncpg`, Pydantic, `httpx` и слоистой структурой:

```text
API → schemas → services → repositories → ORM/database
                     ↘ integrations
```

Реализованы profile-oriented vertical slices и reference data foundation.
Существуют `ProductionOrder` ORM/migration и связанные Product lifecycle
guards. Реализованного end-to-end market opportunity matching flow нет.

`backend/app/integrations/fns/client.py` относится к регистрационному lookup и
не является адаптером закупок. Наличие этого клиента не означает live ЕИС.

## 3. TARGET MVP bounded contexts

### 3.1 PROFILE DOMAIN

Отвечает на вопрос: «Что предприятие подтверждённо способно производить?»

Использует существующие profile facts и минимально добавляет логические
capabilities:

- `ProfileTechnologyCapability`;
- `ProfileMaterialCapability`;
- `ProfileSectionCompleteness`.

Profile domain не хранит внешние закупки и не выводит capabilities из ОКВЭД.

### 3.2 MARKET OPPORTUNITY DOMAIN

Отвечает на вопрос: «Что требует независимая внешняя рыночная возможность?»

Корневой concept — `ProcurementOpportunity`. Он:

- не принадлежит `EnterpriseProfile`;
- сохраняет `(canonical_source, exact_external_id)`;
- хранит provenance и display data источника;
- содержит нормализованные structured requirements;
- допускает неизвестные поля без синтетических defaults.

Первый ingestion boundary — prepared CSV/JSON/fixture/manual import.
Нормализация выполняется до matching. Raw source format не должен проникать в
profile domain.

### 3.3 MATCHING APPLICATION DOMAIN

Оркестрирует read-only сравнение одного профиля и одной opportunity:

```text
market eligibility
→ criterion evaluators
→ hard conflict / remediability / unknown classification
→ compatibility + coverage
→ match status
→ explanations
```

После оценки набора opportunities домен сортирует неотклонённые результаты и
строит TOP-10 projection.

Matching application domain не создаёт `ProductionOrder` и не управляет
исполнением.

### 3.4 EXECUTION / ERP DOMAIN — LATER

Будущий bounded context может включать выигранные контракты, внутренние
производственные заказы, календарь, маршруты, загрузку, документы и расчёты.
Текущий `ProductionOrder` frozen и может быть переосмыслен только после
отдельного решения.

## 4. Target components

| Компонент | Ответственность | Статус |
|-----------|-----------------|--------|
| Profile matching projection | Собирает подтверждённые profile facts без изменения источников | TARGET MVP |
| Prepared opportunity importer | Валидирует identity, provenance, units и structured requirements | TARGET MVP |
| Opportunity repository/collection | Даёт idempotent snapshot внешней возможности | TARGET need; persistence design не утверждён |
| Criterion evaluators | Возвращают positive/hard/remediable/unknown outcomes | TARGET MVP |
| Score calculator | Считает compatibility, coverage и ranking score | TARGET MVP |
| Explainability assembler | Формирует reasons с criterion code и сравниваемыми facts | TARGET MVP |
| TOP-10 projector | Применяет exclusion и deterministic tie-break | TARGET MVP |
| Live ЕИС/commercial adapters | Получают raw external data | LATER |
| AI normalization | Извлекает structured requirements из текста | LATER |
| Execution/ERP services | Управляют исполнением выигранного заказа | LATER |

## 5. Structured requirements и UNKNOWN

Requirement collections используют три состояния:

```text
null = неизвестно, было ли требование
[]   = источник подтвердил отсутствие требования
[x]  = известны конкретные requirements
```

Requirement item имеет strength `MANDATORY`, `PREFERRED` или `UNKNOWN`.

UNKNOWN:

- не создаёт hard conflict;
- не даёт положительного match;
- исключается из compatibility denominator;
- остаётся в ожидаемом coverage denominator;
- обязательно превращается в `missing_data` explanation.

Импорт не заменяет blank на `0`, `false`, `[]` или выдуманный code.

## 6. Market eligibility и compatibility

Проверка доступности рынка выполняется раньше production matching:

```text
CLOSED / CANCELLED / AWARDED / definitely expired
→ NOT_ELIGIBLE
```

`NOT_ELIGIBLE` не означает производственную несовместимость и не записывается
в `hard_conflicts`. Причина относится к `eligibility_reasons`.

`INCOMPATIBLE` возможен только после прохождения market eligibility, когда
есть доказанный production/compliance hard conflict.

## 7. Deterministic Matching v1

Matching v1 использует versioned, прозрачные rules. Hard outcome допустим
только для комбинации:

```text
подтверждённое MANDATORY requirement
+ подтверждённый несовместимый profile fact
+ отсутствие допустимого устранения, когда rule его допускает
```

ML/LLM, embeddings, fuzzy title matching и скрытая перекалибровка не входят в
Matching v1. AI может позже помогать нормализации, но не заменяет rule engine.

## 8. Explainability contract

Логический `MatchAssessment` должен позволять получить:

- `match_status`;
- `compatibility_score`;
- `coverage`;
- `ranking_score`;
- `eligibility_reasons[]`;
- `positive_reasons[]`;
- `hard_conflicts[]`;
- `remediable_limitations[]`;
- `missing_data[]`;
- `missing_capabilities[]`;
- trace criterion codes и использованных facts.

Persistence `MatchAssessment` не утверждена: compute-on-demand и хранение
snapshot остаются отдельным решением.

## 9. Ranking boundary

`NOT_ELIGIBLE` и `INCOMPATIBLE` исключаются. Остальные результаты сортируются:

```text
ranking_score DESC
→ coverage DESC
→ application_deadline ASC NULLS LAST
→ source ASC
→ external_id ASC
```

TOP-10 содержит не более десяти фактических результатов; искусственное
дополнение запрещено.

## 10. Profile readiness boundary

До первого meaningful TOP-10 блокируют только:

1. profile technology capability;
2. profile material capability;
3. section completeness semantics/mechanism.

Не блокируют и могут остаться UNKNOWN: Product ↔ OKPD2, недостающие equipment
limits, max workpiece mass, capacity, availability, execution feasibility,
region mapping, неподтверждённое отсутствие сертификата и technical boolean
defaults.

`ProcessingEnvelope` не является обязательной target entity. Доступные
dimensions/diameter/axes/CNC читаются как projection из подтверждённых
`Equipment` facts.

## 11. CURRENT / TARGET / LATER boundary table

| Тема | CURRENT | TARGET MVP | LATER |
|------|---------|------------|-------|
| Profile | Реализована широкая foundation | Закрыть три blocking gaps | Глубокий паспорт |
| External market object | Отсутствует | `ProcurementOpportunity` | Live multi-source ecosystem |
| Matching | End-to-end отсутствует | Deterministic rule engine | AI-assisted normalization |
| Ranking | TOP-10 отсутствует | Provisional baseline + tie-break | Recalibration after fixtures |
| ProductionOrder | ORM/migration и guards существуют | Frozen, вне runtime MVP | Возможный execution context |
| Source integration | Нет live ЕИС | Prepared import | ЕИС/commercial adapters |
| Operating model | Нет user/auth domain | Один оператор; последовательное изменение профиля | User/Auth/RBAC, concurrent editing, multi-tenancy |

## 12. Intentionally unresolved

До отдельного design stage не утверждаются:

- окончательные ORM class/table/column names новых concepts;
- API routes и CRUD;
- persistence `MatchAssessment`;
- architecture LATER user/auth/RBAC/multi-tenancy;
- LATER locking/conflict model для совместного редактирования одного профиля;
- live adapter scheduling/retries;
- detailed capacity and production scheduling.
