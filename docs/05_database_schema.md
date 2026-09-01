# Схема данных: CURRENT и TARGET MVP needs

## 1. Назначение

Документ отделяет фактическую **CURRENT DATABASE** foundation от логических
**TARGET MVP PERSISTENCE NEEDS** и **LATER**. Он не является migration plan и
не утверждает новые table/column names.

## 2. CURRENT DATABASE

### 2.1 Фактическая ORM/migration foundation

Текущий backend использует SQLAlchemy 2, Alembic и PostgreSQL. В коде и
migration history представлены группы таблиц:

- profile and registration: `pnc_enterprise_profile`, company size, region,
  industry, enterprise-industry, certificate, quality capability, OKVED и
  enterprise-OKVED;
- production infrastructure: production facility, equipment, warehouse,
  lifting equipment, transport и соответствующие references;
- material/product catalog: material group, material form, material,
  material item, product type и product;
- order foundation: order type и `pnc_production_order`;
- technology vocabulary: `pnc_technology_type`.

Наличие migration файла не доказывает его применение к конкретной БД. Этот
candidate не проводит database inspection, upgrade или downgrade.

### 2.2 CURRENT ProductionOrder

`pnc_production_order` уже существует в ORM/migration foundation и логически
содержит:

- owner `profile_id`;
- `order_type_code`;
- обязательный `product_id`;
- `industry_code`;
- `order_number`, `quantity`, `deadline`.

Identity текущего internal order ограничена профилем и номером. Такая модель не
подходит для внешней procurement identity: она profile-owned, зависит от
Product и не хранит provenance источника.

Product lifecycle CURRENT использует наличие ProductionOrder как in-use guard.
Эта связанность честно сохраняется как current fact, но не продолжается в
TARGET MVP market flow.

### 2.3 CURRENT profile gaps

В текущей схеме отсутствуют утверждённые persistence concepts для:

- внешней `ProcurementOpportunity`;
- profile technology capability link;
- profile material capability link;
- section completeness metadata;
- matching assessment/result/explanations;
- ranked TOP-10 projection.

`TechnologyType` — только reference table. `Material`/`MaterialItem` —
shared/master data, а не capability конкретного profile.

## 3. TARGET MVP PERSISTENCE NEEDS

Ниже перечислены потребности, а не окончательная schema.

### 3.1 ProcurementOpportunity

Persistence должна поддержать:

- независимость от `EnterpriseProfile` ownership;
- provenance `source`;
- exact stable external id;
- логическую уникальность `(canonical_source, exact_external_id)`;
- idempotent repeat import;
- update того же source snapshot при изменении mutable fields;
- display fields и structured requirements с UNKNOWN semantics;
- explicit market status;
- минимум один structured matching signal для попадания в matching pool.

Окончательные table names, JSON vs normalized requirement tables, indexes кроме
необходимости stable identity, FK/cascades и revision history не утверждены.

### 3.2 ProfileTechnologyCapability

Нужно логически хранить связь profile с `TechnologyType.code` и state
`SUPPORTED/UNSUPPORTED/UNKNOWN`. Evidence/notes могут быть optional.

Не утверждены:

- имя таблицы и surrogate key;
- связь с Equipment/Facility;
- uniqueness/index design;
- cascade behavior.

### 3.3 ProfileMaterialCapability

Нужно логически хранить связь profile с `MaterialGroup` и optional конкретным
`Material`, а также state `SUPPORTED/UNSUPPORTED/UNKNOWN`.

Material master data не получает `profile_id`. Capability link не превращает
`MaterialItem` в stock или inventory.

### 3.4 ProfileSectionCompleteness

Нужно хранить или надёжно предоставлять matching input со следующими facts:

- section code;
- state `CONFIRMED_COMPLETE/PARTIAL/UNKNOWN`;
- scope/snapshot identity;
- human confirmer;
- confirmation timestamp;
- invalidation до `PARTIAL` после изменения section.

Способ persistence и UI confirmation mechanism проектируются отдельно.

### 3.5 Matching result

TARGET MVP требует логический `MatchAssessment`, `CriterionResult` и TOP-10
projection, но **не требует доказанно persistent tables**. Compute-on-demand и
stored snapshots остаются открытой альтернативой.

Нельзя добавлять таблицу assessment только ради сходства с
`ProductionOrder`: assessment не является execution lifecycle.

## 4. Identity и deduplication need

Утверждённое правило:

```text
opportunity identity = (canonical_source, exact_external_id)
```

- source приводится к stable lowercase code;
- external id trim-ится по краям, но source-defined case сохраняется;
- title, customer, price, deadlines, status и URL mutable;
- дубль identity с одинаковым canonical payload — no-op;
- дубль identity с изменённым payload — update того же snapshot;
- две конфликтующие строки одной identity в одном batch — import conflict;
- hash всей строки не является primary dedup key.

Как именно enforce-ить правило транзакционно, будет решено design stage.

## 5. NULL / UNKNOWN persistence semantics

Scalar `NULL` означает, что источник или профиль не дал надёжного значения.
Для requirement collection логически различаются:

```text
null = неизвестно, было ли требование
[]   = явно подтверждено отсутствие requirements
[x]  = требования известны
```

Persistence design обязан сохранить различие `null` и `[]`. Technical default
не должен превращать UNKNOWN в confirmed false/zero.

Особенно это относится к CURRENT boolean defaults `Equipment.cnc`,
`QualityCapability.measuring_tools`, `QualityCapability.cim_machine` и
infrastructure fields: matching использует confirmation semantics поверх
технической schema.

## 6. CURRENT tables that remain outside critical path

CURRENT tables инфраструктуры, OKVED/Industry и ProductionOrder не удаляются.
Они могут обслуживать существующие vertical slices, но не становятся
prerequisites TARGET MVP.

В частности:

- OKVED остаётся registration context;
- Industry остаётся context;
- warehouses/lifting/transport/facilities остаются optional profile depth;
- ProductionOrder и OrderType frozen вне market runtime.

## 7. NOT YET DESIGNED

До отдельного persistence design запрещено считать утверждёнными:

- окончательные class/table/column names;
- полный set constraints/FKs/indexes;
- cascade and delete lifecycle;
- requirement storage decomposition;
- import batch/revision tables;
- MatchAssessment persistence;
- API CRUD and routing;
- concurrency/locking architecture;
- migrations and backfill strategy.

## 8. LATER

Отдельные решения могут добавить:

- raw payload archive и revision history;
- live adapter cursors/polling state;
- persistent matching history;
- capacity and availability snapshots;
- execution/ERP tables;
- contracts, invoices and CRM entities;
- authentication/authorization/multi-tenancy storage.

Ничто из этого не блокирует first TOP-10.

## 9. Database realignment rule

Документационный realignment не изменяет ORM, migrations, seeds или БД.
Следующий design stage должен начинаться с утверждённых logical needs этого
набора, а не с продолжения `ProductionOrder` Stage 2/3.
