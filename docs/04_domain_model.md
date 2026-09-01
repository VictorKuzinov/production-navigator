# Доменная модель

## 1. Назначение и статус

Документ задаёт логическую модель **TARGET MVP** и отдельно фиксирует
подтверждённые **CURRENT** facts и **LATER** concepts. Он не утверждает новые
ORM classes, tables, migrations, cascades или API routes.

## 2. TARGET MVP domain tree

```text
PROFILE DOMAIN
└── EnterpriseProfile
    ├── Product → ProductType / MaterialItem → Material
    ├── Equipment → EquipmentType
    ├── ProfileTechnologyCapability → TechnologyType
    ├── ProfileMaterialCapability → MaterialGroup / Material
    ├── QualityCapability
    ├── EnterpriseCertificate → CertificateType
    ├── Region
    └── ProfileSectionCompleteness

MARKET OPPORTUNITY DOMAIN
└── ProcurementOpportunity
    ├── provenance + external identity
    ├── display / market fields
    └── structured requirements

MATCHING APPLICATION DOMAIN
├── MatchAssessment
│   └── CriterionResult / explanation
└── Ranked TOP-10 projection

EXECUTION / ERP DOMAIN — LATER
└── ProductionOrder (CURRENT foundation, frozen semantics pending redesign)
```

`ProcurementOpportunity` не является дочерним объектом `EnterpriseProfile`.
`MatchAssessment` связывает inputs логически только на время оценки; способ его
хранения не утверждён.

## 3. CURRENT domain facts

В рабочей ORM существуют:

- `EnterpriseProfile` и регистрационные/классификационные связи;
- `ProductionFacility`, `Equipment`, `Warehouse`, `LiftingEquipment`,
  `Transport`;
- `Material`, `MaterialItem`, `Product`;
- `QualityCapability`, `EnterpriseCertificate`;
- `ProductionOrder` и `OrderType`.

`ProductionOrder` принадлежит профилю и ссылается на Product. Он не содержит
provenance внешнего источника и не представляет закупку до matching. Product
lifecycle CURRENT частично зависит от наличия `ProductionOrder`.

В CURRENT отсутствуют runtime concepts `ProcurementOpportunity`, profile
technology/material capability links, section completeness и end-to-end
matching/TOP-10.

## 4. EnterpriseProfile в TARGET MVP

`EnterpriseProfile` остаётся root profile domain. Для Matching v1 используются
только факты с понятной семантикой и происхождением:

- Product/ProductType — небольшой опытный signal;
- Equipment — подтверждённые типы и технические limits;
- Technology capability;
- Material capability;
- QualityCapability;
- EnterpriseCertificate;
- Region;
- section completeness metadata.

OKVED и Industry не являются доказательством production capability и не входят
в scoring v1.

## 5. ProfileTechnologyCapability — TARGET logical concept

Минимальный логический контракт:

| Fact | Назначение |
|------|------------|
| profile identity | Владелец capability |
| `TechnologyType.code` | Нормализованная технология |
| state: `SUPPORTED/UNSUPPORTED/UNKNOWN` | Подтверждённый capability outcome |
| optional evidence/notes | Объяснение без отдельного workflow |

Окончательные model/table names и привязка к Equipment/Facility не утверждены.

## 6. ProfileMaterialCapability — TARGET logical concept

Минимальный логический контракт:

| Fact | Назначение |
|------|------------|
| profile identity | Владелец capability |
| `MaterialGroup` и optional конкретный `Material` | Грубая или точная область обработки |
| state: `SUPPORTED/UNSUPPORTED/UNKNOWN` | Подтверждённый capability outcome |
| optional evidence/notes | Объяснение |

Material form, stock, thickness range и полная геометрия не добавляются без
потребности первой fixture.

## 7. ProfileSectionCompleteness — TARGET logical concept

Минимальные states:

```text
CONFIRMED_COMPLETE
PARTIAL
UNKNOWN
```

Concept относится к section/scope/snapshot, имеет human confirmer и timestamp.
Import, seed, default, row count и progress percentage не создают
`CONFIRMED_COMPLETE`. Изменение подтверждённого section переводит его в
`PARTIAL`.

Persistence и UI confirmation flow будут спроектированы отдельно; semantics
уже утверждена.

## 8. ProcurementOpportunity — TARGET MVP

`ProcurementOpportunity` представляет одну независимо оцениваемую внешнюю
закупку, lot или коммерческий запрос.

Он:

- не принадлежит `EnterpriseProfile`;
- не является `Product`;
- не является `ProductionOrder`;
- не является выигранным контрактом;
- сохраняет provenance и external identity;
- содержит требования внешнего заказчика.

### 8.1 Identity

```text
(canonical_source, exact_external_id)
```

Один технически самостоятельный lot получает собственный stable external id.
Изменение title, price, deadlines, status или URL обновляет тот же source
snapshot и не создаёт новую identity.

### 8.2 Минимальные required fields

- `source`;
- `external_id`;
- `title`;
- explicit `status`, включая допустимый `UNKNOWN`;
- минимум один непустой structured matching signal.

Условно обязательны currency при price, unit при quantity, canonical units для
числовых requirements и `requirement_strength` для каждого item.

### 8.3 Optional fields

- procurement number, customer, source URL;
- OKPD2 и ProductType context;
- price/currency;
- region;
- quantity/unit;
- application/execution deadlines;
- procurement type;
- material, technology, equipment, dimensions/mass, quality и certificate
  requirements.

Optional field может быть UNKNOWN. Import не синтезирует значение.

### 8.4 Requirement blocks

Минимальные logical values:

- material: `MaterialGroup`, optional `Material`, form/size только при явном
  требовании;
- technology: `TechnologyType.code`;
- equipment: `EquipmentType.code` и заявленные CNC/axes/work-zone/diameter;
- dimensions/mass: canonical length/width/height/diameter/mass;
- quality: IT grade, maximum Ra, measuring/CMM requirements;
- certificate: `CertificateType.code`, optional explicit
  `required_by/valid_through`;
- strength каждого item: `MANDATORY/PREFERRED/UNKNOWN`.

Полная ORM decomposition requirement blocks не утверждена.

## 9. MatchAssessment — TARGET logical result

Один assessment сравнивает один profile snapshot и одну opportunity snapshot.
Он должен позволять получить:

- `match_status`;
- `compatibility_score` или `null`;
- `coverage`;
- `ranking_score`;
- `eligibility_reasons[]`;
- `positive_reasons[]`;
- `hard_conflicts[]`;
- `remediable_limitations[]`;
- `missing_data[]`;
- `missing_capabilities[]`;
- воспроизводимый criterion trace.

`MatchAssessment` может вычисляться по запросу или сохраняться. Решение о
persistence, revisioning и cleanup не принято.

## 10. CriterionResult / explanation

Каждый criterion result содержит минимум:

- criterion code;
- procurement requirement value и strength;
- сравниваемый profile fact и его confirmation/completeness;
- outcome: positive, hard conflict, remediable, unknown или not applicable;
- contribution value `0..1` либо UNKNOWN/NOT_APPLICABLE;
- человекочитаемое explanation.

Свободный текст без rule/facts не является достаточным объяснением.

## 11. Ranked TOP-10 projection

Projection создаётся после оценки всего входного набора:

1. исключить `NOT_ELIGIBLE` и `INCOMPATIBLE`;
2. отсортировать по ranking score, coverage и утверждённому tie-break;
3. вернуть первые десять или меньше, если доступных записей меньше.

Projection не является saved list, CRM lead или execution order. Persistence
не утверждена.

## 12. ProductionOrder boundary

### CURRENT

- ORM, migration, relationships и indexes существуют;
- `OrderType` классифицирует внутренний характер производственного заказа;
- Product lifecycle использует ссылку ProductionOrder как guard.

### TARGET MVP

- сущность исключена из runtime critical path;
- не принимает внешние закупки;
- не участвует в matching/ranking;
- Stage 2/3 и Builder не продолжаются;
- CURRENT foundation не удаляется этим realignment.

### LATER

Возможен отдельный execution/ERP bounded context после TOP-10. Ownership,
lifecycle, transition из выигранной opportunity и даже имя сущности должны
быть пересмотрены отдельно.

`OrderType` не является vocabulary закупочной процедуры.

## 13. Processing limits и availability

Отдельная обязательная `ProcessingEnvelope` entity не утверждается.
Matching v1 строит read-only projection из подтверждённых Equipment fields.
Отсутствующий max workpiece mass остаётся UNKNOWN.

Capacity и availability не являются prerequisite первого TOP-10. Пока нет
сопоставимых facts, quantity и execution deadline дают UNKNOWN и explanations.

## 14. LATER concepts

- live source adapters;
- AI/LLM normalization;
- detailed capacity/availability;
- routing, scheduling, shifts and personnel;
- execution/ERP lifecycle;
- CRM/contracts/invoices;
- profitability and advanced analytics;
- authentication/authorization/multi-tenancy;
- persistent assessment history, если будет доказана необходимость.
