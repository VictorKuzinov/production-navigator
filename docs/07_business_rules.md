# Бизнес-правила Production Navigator

## 1. Статус и приоритет документа

Это главный нормативный candidate-документ Matching v1. Он разделяет:

- **CURRENT** — уже реализованные validation/lifecycle rules;
- **TARGET MVP** — утверждённые deterministic matching rules;
- **LATER** — возможные расширения.

Weights и thresholds помечены `PROVISIONAL MATCHING V1 BASELINE`: они нужны
для воспроизводимой первой fixture, но подлежат ручной review после неё.

## 2. Общие TARGET MVP rules

### BR_MCH_001 — UNKNOWN не является несовместимостью

UNKNOWN:

- не создаёт hard conflict;
- не даёт positive match;
- не уменьшает compatibility;
- уменьшает coverage;
- обязательно объясняется в `missing_data`.

### BR_MCH_002 — Hard conflict требует доказательств

Hard outcome разрешён только при одновременном выполнении:

```text
подтверждённое MANDATORY requirement
+ подтверждённый несовместимый profile fact
+ отсутствие допустимого устранения, если criterion допускает remediation
```

Отсутствие row в `PARTIAL/UNKNOWN` section не является несовместимым fact.

### BR_MCH_003 — Устранимое ограничение

Если обязательный material/resource/document/operation можно получить,
арендовать, продлить или выполнить по допустимому субподряду, outcome —
`remediable_limitation`, а status не может быть `MATCH`, но opportunity не
отклоняется как невозможная.

### BR_MCH_004 — Determinism

Одинаковые normalized inputs и baseline version дают одинаковые criterion
outcomes, score, status и rank. ML/LLM, embeddings, fuzzy title similarity и
скрытая автокалибровка запрещены в Matching v1.

## 3. ProcurementOpportunity identity

### BR_OPP_001 — Stable identity

```text
identity = (canonical_source, exact_external_id)
```

- source canonicalized до stable lowercase code;
- external id очищается от внешних пробелов, source-defined case сохраняется;
- один независимо оцениваемый lot имеет собственный external id;
- title, customer, price, dates, URL и status не входят в identity.

### BR_OPP_002 — Repeat import

1. Новая identity → новая opportunity.
2. Та же identity + тот же canonical payload → idempotent no-op.
3. Та же identity + изменённый payload → update того же source snapshot и
   повторный matching.
4. Две строки одной identity с разными payload в batch → import conflict.
5. Отсутствующий external id → validation error.
6. Manual id создаётся один раз и сохраняется в файле; новый UUID при каждом
   import запрещён.

Hash всей строки, title, procurement number и URL не являются primary dedup
keys.

## 4. Required/optional opportunity data

Обязательны:

- `source`;
- `external_id`;
- non-blank `title`;
- explicit status (`UNKNOWN` допустим);
- минимум один structured matching signal.

Условно обязательны:

- currency при price;
- unit при quantity;
- canonical unit у числового requirement;
- requirement strength у каждого item.

Все остальные market и requirement fields optional/UNKNOWN.

## 5. Tri-state requirements

### BR_OPP_003 — Collection semantics

```text
null = неизвестно, было ли требование
[]   = источник подтвердил отсутствие requirements
[x]  = известны конкретные requirements
```

Blank/отсутствующая колонка не преобразуется в `[]`, `0` или `false`.

### BR_OPP_004 — Requirement strength

```text
MANDATORY = источник явно требует выполнения
PREFERRED = пожелание/преимущество
UNKNOWN   = requirement известно, но обязательность не подтверждена
```

Только `MANDATORY` может участвовать в hard rule.

## 6. Market eligibility

### BR_ELG_001 — NOT_ELIGIBLE

Opportunity получает `NOT_ELIGIBLE`, если:

- status достоверно `CLOSED`, `CANCELLED` или `AWARDED`; либо
- application deadline достоверно истёк.

Date-only deadline, равный текущей дате, ещё допустим. При неизвестной timezone
нельзя исключать opportunity раньше конца известной даты.

Market exclusion записывается в `eligibility_reasons`, не в
`hard_conflicts`. Поэтому:

```text
NOT_ELIGIBLE ≠ INCOMPATIBLE
```

UNKNOWN status/deadline не исключает opportunity и создаёт warning/missing
data.

## 7. MatchAssessment contract

Результат одного matching содержит:

- `match_status`;
- `compatibility_score: 0..100 | null`;
- `coverage: 0..1`;
- `ranking_score: 0..100`;
- `eligibility_reasons[]`;
- `positive_reasons[]`;
- `hard_conflicts[]`;
- `remediable_limitations[]`;
- `missing_data[]`;
- `missing_capabilities[]`;
- criterion trace с requirement/profile facts и rule code.

`missing_capability` — подтверждённо отсутствующая capability. Она становится
hard conflict только если конкретное MANDATORY rule доказывает невозможность;
иначе может быть remediable.

## 8. Matching v1 matrix

| Criterion | PROCUREMENT FIELD | PROFILE FIELD | RULE | Outcome |
|-----------|-------------------|---------------|------|---------|
| Product experience | `product_type_codes`; title/OKPD2 context | `Product.product_type_code` | Exact category даёт небольшой positive; отсутствие Product — soft zero только здесь; fuzzy title/OKPD2 не используются | SOFT/UNKNOWN, never hard |
| Material | `material_requirements` | `ProfileMaterialCapability` → `MaterialGroup/Material` | Exact material full; group partial; confirmed unsupported MANDATORY hard только без remediation | SOFT / conditional HARD / UNKNOWN/remediable |
| Technology | `technology_requirements` | `ProfileTechnologyCapability` → `TechnologyType` | Supported full; preferred subset partial; confirmed unsupported MANDATORY hard только при complete scope и запрете external execution | SOFT / conditional HARD / UNKNOWN/remediable |
| Equipment | `equipment_requirements` | type, CNC, axes, work zones, diameter | Exact facts positive; below mandatory numeric requirement hard только если все relevant confirmed options fail | SOFT / conditional HARD / UNKNOWN |
| Dimensions/mass | dimensional requirements | read-only Equipment projection | Within confirmed limits positive; exceeds confirmed maxima of all relevant options hard; absent max mass UNKNOWN | SOFT / conditional HARD / UNKNOWN |
| Quantity/capacity | quantity + unit | Сопоставимой capacity CURRENT нет | Сравнение только в одной unit/period; иначе UNKNOWN | UNKNOWN in first v1 |
| Execution deadline | execution deadline | Earliest feasible completion CURRENT нет | Hard only after confirmed comparable availability; otherwise UNKNOWN | UNKNOWN in first v1 |
| Region/logistics | region code | profile region + optional transport scope | Same region positive; another region not hard | SOFT/UNKNOWN |
| Certificates | required certificates + date | type + expiry + completeness | Valid positive; obtainable/renewable remediable; hard only if impossible by required date is proven | SOFT / conditional HARD / remediable / UNKNOWN |
| Quality | IT/Ra/measuring/CMM requirements | `QualityCapability` | `min_it_grade <= required`, `min_ra <= required`; mandatory confirmed numeric failure hard; technical false default not proof | SOFT / conditional HARD / UNKNOWN |
| Market status | status/application deadline | matching time | Closed/cancelled/awarded/expired → NOT_ELIGIBLE | ELIGIBILITY, not compatibility |
| Procurement type | source-side type | no profile fact | Display/filter only; do not use `OrderType` | NOT SCORED |
| Price | price/currency | no cost/finance profile | Display only | NOT SCORED |

OKVED не участвует в score и не доказывает capability. Industry не участвует
в score v1.

## 9. Technical boolean defaults

`Equipment.cnc`, `QualityCapability.measuring_tools`, `cim_machine` и ряд
infrastructure booleans имеют DB default `false`. До human confirmation
`false` нельзя использовать как доказанное отсутствие в hard rule.

## 10. Hard filters v1

Разрешены только следующие классы production/compliance hard conflicts после
успешной market eligibility:

1. **Physical impossibility:** MANDATORY dimension/diameter/mass или equipment
   parameter превышает подтверждённые capabilities всех relevant options.
2. **Quality impossibility:** MANDATORY IT/Ra requirement строже
   подтверждённого best profile capability.
3. **Mandatory compliance:** подтверждены complete certificate section,
   explicit required date и невозможность получить/продлить документ вовремя.
4. **Confirmed capability conflict:** mandatory material/technology/equipment
   capability явно unsupported в complete scope и remediation/source-side
   outsourcing недопустимы.
5. **Quantity/deadline — later conditional:** только после появления
   подтверждённых comparable capacity/earliest-completion facts.

Простое отсутствие row, Product или own transport hard conflict не создаёт.
Кандидатный `BR_COM_001` не активируется без отдельной нормативной проверки.

## 11. UNKNOWN rules

Criterion возвращает UNKNOWN, если:

- procurement field `null` или strength `UNKNOWN`;
- profile fact отсутствует;
- section `PARTIAL/UNKNOWN`, а absence row — единственное evidence;
- units/periods несопоставимы;
- mapping classifications не утверждён;
- raw prose не нормализована;
- technical default не подтверждён;
- rule требует cost/capacity/calendar data, которых нет.

Origin explanations:

- неизвестно в opportunity → `missing_data(origin=PROCUREMENT_SOURCE)`;
- неизвестно в profile → `missing_data(origin=ENTERPRISE_PROFILE)`;
- capability confirmed absent, но устранима → `missing_capabilities` +
  `remediable_limitations`;
- confirmed non-remediable mandatory conflict → `hard_conflicts`.

## 12. PROVISIONAL MATCHING V1 BASELINE

### 12.1 Weights

| Criterion | Weight |
|-----------|-------:|
| Product experience | 8 |
| Material capability | 23 |
| Technology capability | 23 |
| Equipment capability | 15 |
| Dimensions / mass | 12 |
| Quantity / capacity | 5 |
| Execution deadline | 5 |
| Region / logistics | 3 |
| Certificates | 3 |
| QualityCapability | 3 |
| **TOTAL** | **100** |

Weight — вклад positive compatibility, а не severity hard rule.

### 12.2 Criterion values

```text
1.0 = полное подтверждённое соответствие
0.5 = частичное соответствие или устранимое ограничение
0.0 = известное soft mismatch без hard conflict
UNKNOWN = недостаточно данных
NOT_APPLICABLE = requirement явно отсутствует
```

Прозрачное значение между 0 и 1 допустимо для воспроизводимой доли, например
подтверждённых preferred technologies.

### 12.3 Formulas

Пусть `w_i` — weight, `v_i` — известное criterion value.

```text
compatibility_score =
    100 × Σ(w_i × v_i)
    / Σ(w_i для известных применимых criteria)

coverage =
    Σ(w_i для известных применимых criteria)
    / Σ(w_i для всех ожидаемых применимых criteria)

ranking_score =
    0.85 × compatibility_score
    + 0.15 × (100 × coverage)
```

UNKNOWN requirement остаётся в expected coverage denominator, но исключается
из compatibility. `[]`/NOT_APPLICABLE исключается из обоих denominators.

Если неизвестен любой core criterion, это отражается coverage. Если не оценён
ни один known applicable criterion, `compatibility_score=null`,
`ranking_score=0`.

### 12.4 Status priority

Правила применяются сверху вниз:

1. market unavailable → `NOT_ELIGIBLE`;
2. production/compliance hard conflict → `INCOMPATIBLE`;
3. mandatory remediable limitation → `POTENTIAL` независимо от score/coverage;
4. coverage `< 0.35` или не оценён ни один core criterion из
   Material/Technology/Equipment/Dimensions/Quality → `INSUFFICIENT_DATA`;
5. compatibility `< 50` → `LOW_MATCH`;
6. compatibility `< 75` или coverage `< 0.60` → `POTENTIAL`;
7. иначе → `MATCH`.

Для `NOT_ELIGIBLE` capability score может не вычисляться:
`compatibility_score=null`, `ranking_score=0`.

Thresholds `0.35/0.60`, `50/75` и blend `85/15` provisional.

## 13. TOP-10

### BR_RNK_001 — Exclusion

`NOT_ELIGIBLE` и `INCOMPATIBLE` исключаются. Остальные statuses могут попасть
в ranking с явной маркировкой.

### BR_RNK_002 — Deterministic tie-break

```text
ranking_score DESC
→ coverage DESC
→ application_deadline ASC NULLS LAST
→ source ASC
→ external_id ASC
```

### BR_RNK_003 — Result size

Вернуть первые 10. Если eligible/non-incompatible opportunities меньше,
вернуть фактическое количество. Не создавать synthetic filler records.

## 14. Profile completeness rules

```text
UNKNOWN
= section не проверен; absence row ничего не доказывает

PARTIAL
= список явно неполный либо изменён после confirmation;
  known facts применимы, absence row ничего не доказывает

CONFIRMED_COMPLETE
= human подтвердил section/scope/snapshot;
  absence row может быть negative fact в пределах scope
```

Import/seed/default/row count/progress percentage не создают
`CONFIRMED_COMPLETE`. Изменение confirmed section → `PARTIAL`.

## 15. CURRENT validation/lifecycle rules preserved

Следующие реализованные rules остаются CURRENT и не объявляются Matching v1:

- Equipment numeric/ownership validations;
- Material identity `(group_code, grade_name)`, positive finite density и safe
  delete при отсутствии MaterialItem references;
- MaterialItem canonical units, form/dimension rules, nullable uniqueness,
  immutability when used by Product;
- Product profile ownership, trimmed non-blank SKU/name, exact per-profile SKU
  uniqueness, positive weight/Ra, IT1–IT18 and in-use guard;
- Transport positive payload/quantity, nullable positive volume, profile
  isolation и tri-state refrigeration.

CURRENT Product in-use guard срабатывает из-за `ProductionOrder`. Он честно
сохраняется как implementation fact, но не задаёт TARGET MVP market lifecycle.

`BR_COM_001` остаётся candidate rule, а не active production hard filter.

## 16. Blocking gaps

До first meaningful TOP-10 блокируют только:

1. profile technology capability;
2. profile material capability;
3. section completeness semantics/mechanism.

Capacity, availability, ProcessingEnvelope, Product ↔ OKPD2 и live ЕИС не
являются prerequisites.

## 17. LATER / recalibration

После end-to-end fixture допускается только явная manual review baseline на
конкретных ranking errors. ML/automatic optimization не используется.

LATER rules могут добавить capacity, availability, richer compliance,
classification mappings и AI-assisted normalization после отдельных решений.
