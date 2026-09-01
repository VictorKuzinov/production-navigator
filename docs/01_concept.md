# Производственный навигатор

## Статус документа

Этот файл входит в candidate documentation set этапа `MVP DOCUMENTATION
REALIGNMENT`. Он не описывает TARGET MVP как уже реализованный и не заменяет
рабочий `docs/01_concept.md` до отдельного решения об интеграции.

Во всём документе используются три статуса:

- **CURRENT** — подтверждённое состояние текущего репозитория;
- **TARGET MVP** — утверждённая граница первого работающего продукта;
- **LATER** — возможное развитие после первого объяснимого TOP-10.

## 1. Продуктовая идея

**Производственный навигатор** помогает производственному предприятию описать
реальные возможности и получить ранжированный список подходящих рыночных
возможностей.

Принцип проекта:

> Находим не тендеры, а возможности для производства.

Первый обязательный user value:

> **ОБЪЯСНИМЫЙ TOP-10 РЫНОЧНЫХ ВОЗМОЖНОСТЕЙ.**

Система не обещает, что каждая найденная закупка выгодна или исполнима без
дополнительной проверки. Она детерминированно показывает степень
совместимости, полноту данных и причины результата.

## 2. Пользователь и решаемая проблема

Целевые пользователи — малые и средние производственные предприятия,
контрактные производства, мастерские и компании, ищущие новые заказы или
кооперацию.

Основные проблемы:

- сведения о продукции, оборудовании, материалах и технологиях разрознены;
- предприятие не видит, какие внешние возможности соответствуют его профилю;
- отсутствие данных часто ошибочно воспринимается как отсутствие capability;
- простой список закупок не объясняет техническую совместимость;
- раннее погружение в CRM/ERP не даёт первого рыночного результата.

## 3. Главный сценарий TARGET MVP

1. Пользователь вводит данные предприятия.
2. Система формирует производственный профиль.
3. Подготовленный файл, fixture или ручной импорт создаёт независимый набор
   внешних `ProcurementOpportunity`.
4. Детерминированный matching сравнивает структурированные требования с
   подтверждёнными возможностями профиля.
5. Система рассчитывает compatibility и coverage.
6. Неотклонённые opportunities ранжируются.
7. Пользователь получает TOP-10 и для каждого результата видит:
   - почему возможность подходит;
   - какие требования доказанно несовместимы;
   - какие ограничения можно устранить;
   - каких данных и capabilities не хватает.

Целевой поток:

```text
EnterpriseProfile
→ ProcurementOpportunity
→ deterministic matching
→ compatibility + coverage
→ ranking
→ TOP-10
→ explanations / limitations / missing data
```

## 4. CURRENT

В текущем репозитории уже существует широкая backend-foundation
производственного профиля: ORM/migrations и vertical slices для ряда профильных
сущностей, включая `EnterpriseProfile`, `Equipment`, `Product`, материалы,
инфраструктуру, качество и связанные справочники.

Также существуют ORM-модель, migration foundation и relationships
`ProductionOrder`. Часть текущего Product lifecycle запрещает изменение и
удаление Product, если на него ссылается `ProductionOrder`.

При этом end-to-end цепочка от внешней рыночной возможности до объяснимого
TOP-10 ещё не реализована. В частности, CURRENT не содержит утверждённого
runtime flow `ProcurementOpportunity → matching → ranking → TOP-10`.

`ProductionOrder` не является внешней закупкой: он принадлежит
`EnterpriseProfile`, ссылается на внутренний `Product` и не сохраняет
provenance внешнего источника.

## 5. TARGET MVP

В TARGET MVP входят только компоненты критического пути:

- достаточный для matching `EnterpriseProfile`;
- `Product` / `ProductType` как небольшой сигнал существующего опыта;
- equipment, material, technology, quality, certificate и region facts;
- отдельный внешний объект `ProcurementOpportunity` со стабильной identity и
  provenance;
- подготовленный файловый/ручной ingestion и нормализация требований;
- deterministic Matching v1;
- раздельные compatibility и coverage;
- статусы `NOT_ELIGIBLE`, `INCOMPATIBLE`, `POTENTIAL`,
  `INSUFFICIENT_DATA`, `LOW_MATCH`, `MATCH`;
- объяснения, ограничения, missing data/capabilities;
- deterministic ranking и TOP-10.

Первый MVP допускает prepared/manual/file import. Live ЕИС и коммерческие
интеграции не являются prerequisite.

Управление исполнением заказа, production scheduling и экономическая оценка не
входят в TARGET MVP.

## 6. Граница ProductionOrder

### CURRENT

- ORM-модель и migration foundation `ProductionOrder` существуют;
- `OrderType` обслуживает внутреннюю order-модель;
- Product lifecycle частично зависит от ссылок `ProductionOrder`.

### TARGET MVP

- `ProductionOrder` и `OrderType` не участвуют в ingestion, matching, scoring,
  ranking или TOP-10;
- `ProductionOrder` не переименовывается в закупку и не подменяет
  `ProcurementOpportunity`;
- vertical slice и Stage 2/3 заморожены;
- существующий код на этапе документационного realignment не удаляется.

### LATER

После первого TOP-10 `ProductionOrder` может быть переосмыслен в отдельном
execution/ERP bounded context. Такое решение потребует самостоятельного design
stage и не следует автоматически из TARGET MVP.

## 7. Основные продуктовые принципы

1. Внешняя возможность независима от профиля предприятия.
2. UNKNOWN не означает несовместимость.
3. Hard conflict требует доказанного обязательного требования и доказанного
   несовместимого факта без допустимого устранения.
4. Market eligibility отделена от production compatibility:
   `NOT_ELIGIBLE ≠ INCOMPATIBLE`.
5. Matching v1 детерминирован и воспроизводим; ML/LLM/fuzzy scoring не нужен.
6. Положительный score не скрывает недостаточную coverage.
7. Каждое решение объясняется структурированными facts и rules.
8. Расширение профиля допускается только когда оно улучшает первый TOP-10.

## 8. LATER

После подтверждения end-to-end ценности могут рассматриваться:

- live ЕИС и коммерческие площадки;
- AI/LLM normalization неструктурированного текста;
- fuzzy/semantic matching;
- Product ↔ OKPD2 mapping, если необходимость доказана fixture;
- capacity, availability и execution feasibility;
- production scheduling и execution/ERP context;
- CRM, договоры, счета и document flow;
- profitability и расширенная рыночная аналитика;
- authentication, authorization и multi-tenancy после отдельного решения.

Ни один пункт LATER не является условием первого объяснимого TOP-10.
