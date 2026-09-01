# Автоматизированное тестирование backend

## 1. Назначение и статус

Документ отделяет **CURRENT verified implementation** от **TARGET tests после
realignment**. Наличие target test plan не означает, что ProcurementOpportunity,
Matching или TOP-10 уже реализованы.

Во время documentation realignment tests не запускались; фактические counts не
пересчитывались.

## 2. CURRENT verified baseline

Последний наиболее поздний полный запуск, зафиксированный в рабочем
`docs/10_testing.md`:

```text
378 passed in 14.42s
```

Документированный layer count:

| Layer | Tests |
|-------|------:|
| Schemas | 139 |
| Services | 111 |
| Repositories | 21 |
| API/integration | 107 |
| **TOTAL** | **378** |

Это historical CURRENT baseline, а не новый результат candidate stage.

Ранее зафиксированный `375 passed in 13.32s` относится к post-Product run до
добавления трёх OpenAPI custom error response regression tests. Candidate
сохраняет более поздний baseline 378 и не заявляет новый test execution.

## 3. CURRENT test stack

- `pytest`;
- `pytest-asyncio`;
- `aiosqlite` in-memory test DB;
- `httpx.AsyncClient` + `ASGITransport`;
- FastAPI dependency override for `AsyncSession`;
- fail-closed protection against accidental development database access.

Suite разделена на schemas, services, repositories и API/integration. Текущие
tests проверяют implemented vertical slices, включая EnterpriseProfile,
ProductionFacility, Equipment, Warehouse, LiftingEquipment, Transport,
Material, MaterialItem и Product, а также OpenAPI custom errors.

## 4. CURRENT facts about ProductionOrder tests

Product regression tests используют temporary `ProductionOrder`, чтобы
подтвердить CURRENT Product in-use guard. Это не является утверждением
ProductionOrder Stage 2 или external opportunity workflow.

ProductionOrder vertical slice не является текущей целью. Stage 2/3 и Builder
не утверждены и не должны продолжаться до отдельного LATER decision.

## 5. TARGET MVP test scope — not yet implemented

Будущий test plan начинается только после отдельного design/implementation
stage и должен покрыть критический flow:

```text
profile + prepared opportunities
→ deterministic assessments
→ explanations
→ ranking
→ TOP-10
```

### 5.1 ProcurementOpportunity contract

Проверить:

- required source/external id/title/status;
- explicit `UNKNOWN` status;
- at least one structured signal;
- conditional currency/unit/canonical-unit validation;
- stable identity `(canonical_source, exact_external_id)`;
- idempotent duplicate import;
- update same identity when payload changes;
- conflicting duplicate rows in one batch;
- manual id stability;
- independence from EnterpriseProfile ownership;
- distinction `null` vs `[]` vs `[x]` requirements;
- no silent defaults for blank fields.

### 5.2 Capability and completeness

Проверить technology/material states:

```text
SUPPORTED / UNSUPPORTED / UNKNOWN
```

Проверить section states:

```text
CONFIRMED_COMPLETE / PARTIAL / UNKNOWN
```

Обязательные cases:

- import/seed/default/row count do not create CONFIRMED_COMPLETE;
- explicit human confirmation records scope/snapshot/time;
- change after confirmation → PARTIAL;
- empty confirmed section may prove absence;
- empty partial/unknown section proves nothing.

### 5.3 Market eligibility

Проверить отдельно от compatibility:

- CLOSED/CANCELLED/AWARDED → NOT_ELIGIBLE;
- definitely expired application deadline → NOT_ELIGIBLE;
- date-only deadline equal today remains eligible;
- unknown timezone/deadline does not cause premature exclusion;
- eligibility reason is not stored as hard conflict;
- `NOT_ELIGIBLE ≠ INCOMPATIBLE`.

### 5.4 Criterion evaluators

Для каждого Product/material/technology/equipment/dimensions/quantity/deadline/
region/certificate/quality criterion проверить:

- positive confirmed fact;
- known soft mismatch;
- UNKNOWN procurement fact;
- UNKNOWN profile fact;
- MANDATORY confirmed non-remediable conflict;
- remediable limitation;
- NOT_APPLICABLE;
- explanation contains criterion code, requirement fact, profile fact and rule.

Special cases:

- Product mismatch never hard;
- OKVED/Industry never score v1;
- technical boolean false default is not confirmed absence;
- equipment count is not capacity;
- missing max workpiece mass is UNKNOWN;
- certificate absence in unconfirmed section is UNKNOWN;
- obtainable/renewable certificate is remediable;
- certificate hard conflict requires proven impossibility by required date.

### 5.5 Score formulas

Future table-driven tests фиксируют `PROVISIONAL MATCHING V1 BASELINE`:

| Criterion | Exact weight |
|-----------|-------------:|
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

Проверить exact set критериев, exact weight каждого criterion и total `100`.
Это provisional baseline для первого end-to-end fixture, а не окончательно
доказанные business coefficients.

Проверить:

- weighted compatibility across known applicable criteria;
- UNKNOWN excluded from compatibility denominator;
- UNKNOWN retained in expected coverage denominator;
- NOT_APPLICABLE excluded from both denominators;
- ranking `0.85 × compatibility + 0.15 × coverage×100`;
- no known applicable criterion → compatibility null/ranking zero;
- numeric rounding policy once approved by implementation design.

### 5.6 Status priority

Table-driven tests применяют rules exactly in order:

1. NOT_ELIGIBLE;
2. INCOMPATIBLE;
3. mandatory remediable → POTENTIAL;
4. coverage `< 0.35` or no core capability → INSUFFICIENT_DATA;
5. compatibility `< 50` → LOW_MATCH;
6. compatibility `< 75` or coverage `< 0.60` → POTENTIAL;
7. otherwise MATCH.

Проверить boundary values `0.35`, `0.60`, `50`, `75` и priority collisions.

### 5.7 Ranking and TOP-10

Проверить:

- NOT_ELIGIBLE/INCOMPATIBLE exclusion only;
- deterministic sort by score, coverage, deadline, source, external id;
- NULL deadlines last;
- stable ordering on exact ties;
- exactly first ten from larger pool;
- fewer than ten returned without filler;
- INSUFFICIENT_DATA can rank only with explicit missing data.

## 6. Required end-to-end fixture

Future Definition of Done должна включать:

```text
one EnterpriseProfile
+ prepared opportunities containing:
  - MATCH
  - POTENTIAL
  - LOW_MATCH
  - INSUFFICIENT_DATA
  - INCOMPATIBLE
  - NOT_ELIGIBLE
→ deterministic explainable TOP-10
```

Каждый outcome строится и проверяется отдельно так, чтобы ожидаемый status
детерминированно следовал из утверждённых rules.

Fixture обязана подтвердить, что:

- hard conflicts исключаются;
- UNKNOWN не отклоняется;
- compatibility и coverage не смешиваются;
- reasons reproducible;
- rerun with identical inputs gives identical ordering.

## 7. Layer responsibilities for future slice

| Layer | Target responsibility |
|-------|-----------------------|
| Schemas/import contract | Required fields, tri-state, units, strength |
| Services/application | Dedup, orchestration, status priority, TOP-10 |
| Repositories | Idempotent persistence only if approved by design |
| Rule engine unit tests | Criterion outcomes, formulas and explanations |
| API/integration | Minimal exposed import/result path after core works |
| End-to-end fixture | One profile through full deterministic flow |

MatchAssessment repository tests добавляются только если persistence будет
утверждена.

## 8. Commands for CURRENT suite

Из каталога `backend`:

```powershell
python -m pytest
ruff check app tests
```

Candidate не заявляет результат этих команд без фактического запуска.

## 9. Future Definition of Done

Matching slice завершён только когда:

1. approved design реализован без участия ProductionOrder runtime;
2. relevant tests добавлены на нужных слоях;
3. full existing suite проходит;
4. lint проходит;
5. end-to-end fixture даёт deterministic explainable TOP-10;
6. counts и фактический run синхронизированы с рабочей документацией;
7. CURRENT/TARGET boundary обновлена по факту.

Live ЕИС, ML/LLM, capacity, availability, ProcessingEnvelope и execution ERP
не входят в Definition of Done первого Matching v1.
