# Модели SQLAlchemy

## 1. Назначение и граница

Документ разделяет **CURRENT ORM**, **TARGET MVP MODEL NEEDS** и
**NOT YET DESIGNED / LATER**. Он не проектирует новую ORM, не меняет working
models и не является migration specification.

## 2. CURRENT ORM

Рабочая ORM включает:

- reference models на базе `PNCBaseReference`;
- `EnterpriseProfile`, `EnterpriseCertificate`, `EnterpriseIndustry`,
  `EnterpriseOKVED`, `QualityCapability`;
- `ProductionFacility`, `Equipment`, `Warehouse`, `LiftingEquipment`,
  `Transport`;
- `Material`, `MaterialItem`, `Product`;
- `ProductionOrder`;
- отдельную иерархическую model `OKVED`.

Наличие model/migration не означает, что конкретная database upgraded или что
все vertical slices одинаково реализованы.

### 2.1 CURRENT profile facts relevant to matching

| Model | Available fields/facts | Matching limitation |
|-------|------------------------|---------------------|
| `EnterpriseProfile` | company identity, `region_code`, relationships | Не доказывает capability сам по себе |
| `Product` | ProductType, MaterialItem, name, weight, required IT/Ra | Experience signal; нет OKPD2 mapping |
| `Equipment` | type, model, CNC, axes, quantity, diameter, work zones | Нет max mass/capacity/availability; CNC default needs confirmation |
| `QualityCapability` | best IT/Ra, measuring tools, CMM, notes | Boolean defaults не равны confirmed absence |
| `EnterpriseCertificate` | type, issue/expiry dates | Нужны completeness, remediability и required date |
| `Material` / `MaterialItem` | Shared material vocabulary and catalog variants | Нет profile material capability link |
| `TechnologyType` | Reference vocabulary | Нет profile technology capability link |
| `Transport` / `Region` | Logistics context | Только soft/optional matching |

### 2.2 CURRENT ProductionOrder

`ProductionOrder` ORM существует и содержит owned relationship с
`EnterpriseProfile`, обязательную ссылку на `Product`, `OrderType`, Industry,
number, quantity и deadline.

CURRENT relationships:

- `EnterpriseProfile.orders`;
- `Product.orders`;
- corresponding reference back-populates.

Product service/repository lifecycle использует наличие orders для in-use
guard. Это CURRENT implementation fact.

В TARGET MVP `ProductionOrder` frozen и не используется как external
procurement, match assessment или TOP-10 result. Stage 2/3 и Builder не
продолжаются; model/migration не удаляются этим candidate.

`OrderType` не является procurement procedure vocabulary.

## 3. TARGET MVP logical model needs

Следующие names обозначают concepts, а не утверждённые SQLAlchemy classes:

### 3.1 ProcurementOpportunity

Нужен независимый external market object с:

- provenance;
- identity `(canonical_source, exact_external_id)`;
- title/status и optional display fields;
- structured requirements;
- tri-state UNKNOWN semantics;
- idempotent import behavior.

Не утверждены storage decomposition, columns, indexes beyond identity need,
relationships и CRUD.

### 3.2 ProfileTechnologyCapability

Нужна logical profile ↔ `TechnologyType` связь со state
`SUPPORTED/UNSUPPORTED/UNKNOWN` и optional evidence.

### 3.3 ProfileMaterialCapability

Нужна logical profile ↔ `MaterialGroup`/optional `Material` связь со state
`SUPPORTED/UNSUPPORTED/UNKNOWN`.

Material/MaterialItem остаются shared master data и не получают profile
ownership.

### 3.4 ProfileSectionCompleteness

Нужны logical facts:

- section/scope/snapshot;
- `CONFIRMED_COMPLETE/PARTIAL/UNKNOWN`;
- explicit human confirmer/time;
- invalidation to PARTIAL after changes.

Persistence design и confirmation API не утверждены.

### 3.5 MatchAssessment / CriterionResult / TOP-10

Эти logical application results необходимы, но ORM persistence не утверждена.
Compute-on-demand является допустимым первым вариантом. Нельзя проектировать
таблицы assessment как скрытый internal order lifecycle.

## 4. Read-only matching projection

TARGET Matching v1 может читать существующие ORM facts через отдельную
application projection:

```text
EnterpriseProfile + related current entities
→ normalized confirmed matching input
```

Projection:

- не создаёт отдельную `ProcessingEnvelope` entity;
- использует только relevant Equipment work zones/diameter/axes/CNC;
- не агрегирует несопоставимое оборудование;
- не выводит production capacity из `Equipment.quantity`;
- сохраняет отсутствующие limits как UNKNOWN;
- применяет section completeness и confirmation поверх technical defaults.

## 5. CURRENT ORM that remains optional to Matching v1

`ProductionFacility`, `Warehouse`, `LiftingEquipment`, `Transport`,
CompanySize, Industry/EnterpriseIndustry и OKVED/EnterpriseOKVED остаются
реальными models. Их отсутствие в core criteria не означает удаление.

Они подключаются только к approved rule с соответствующим opportunity
requirement. В first narrow fixture они не являются blockers.

## 6. NOT YET DESIGNED

Без отдельного ORM design stage не утверждать:

- окончательные class and table names;
- полный column set и types;
- relationship ownership/back-populates/cascades;
- delete/update lifecycle;
- unique/index/check constraints beyond logical identity need;
- JSON vs normalized requirement models;
- import batch/revision models;
- MatchAssessment persistence;
- API schemas, CRUD, routes and response contracts;
- concurrency and locking;
- migrations, seeds and backfill.

Target concepts не должны появляться в code snippets как уже существующие
`Mapped` classes до реализации.

## 7. Blocking model gaps

До first meaningful TOP-10 необходимо спроектировать и реализовать только:

1. profile technology capability;
2. profile material capability;
3. section completeness mechanism.

Opportunity persistence/ingestion и matching implementation, разумеется,
нужны для end-to-end flow, но среди **profile** gaps blocking list ограничен
этими тремя.

Не блокируют profile readiness:

- Product ↔ OKPD2;
- missing equipment processing limits/max workpiece mass;
- capacity/availability;
- execution feasibility;
- region mapping;
- unconfirmed certificate absence;
- technical boolean defaults.

## 8. LATER

- live-source persistence metadata;
- assessment history;
- capacity and availability models;
- execution/ERP redesign ProductionOrder;
- scheduling/routes/shifts/personnel;
- CRM/contracts/invoices;
- authentication/authorization/multi-tenancy.

Ни один LATER model не должен добавляться в следующий Builder scope без нового
decision/design stage.
