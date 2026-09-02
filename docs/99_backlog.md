# Backlog после MVP realignment

## 1. Статус и правило приоритета

Этот backlog содержит только **POST-FIRST-TOP-10 / LATER** work. Утверждённые
TARGET MVP concepts не возвращаются в список как нерешённый product scope.

Порядок:

```text
first deterministic explainable TOP-10
→ review provisional baseline
→ only then later integrations and depth
```

## 2. Не является backlog: уже утверждено для TARGET MVP

Следующие решения обязательны для критического пути и больше не являются
вопросами «нужно ли это делать»:

- independent `ProcurementOpportunity`;
- prepared/manual/file ingestion;
- stable identity `(canonical_source, exact_external_id)`;
- profile technology capability;
- profile material capability;
- section completeness semantics;
- deterministic Matching v1;
- separate compatibility and coverage;
- explanations and deterministic TOP-10;
- UNKNOWN semantics;
- `NOT_ELIGIBLE ≠ INCOMPATIBLE`;
- `ProductionOrder` frozen outside current MVP.

Их implementation design выполняется отдельным следующим этапом, а не
откладывается в LATER backlog.

## 3. Live market integrations — POST-FIRST-TOP-10

- live ЕИС adapter;
- commercial platform adapters;
- provider-specific auth, rate limits and retries;
- polling/cursors and source update scheduling;
- raw payload archive/revision history, если требуется;
- reconciliation conflicts across sources;
- monitoring source freshness and failures.

Live integration не является prerequisite первой fixture.

## 4. AI and semantic normalization — LATER

- AI/LLM extraction structured requirements from prose;
- fuzzy/semantic subject matching;
- embeddings and semantic retrieval;
- human review workflow for extracted requirements;
- quality/evaluation set for normalization.

AI не заменяет deterministic rule engine и не участвует в provisional score.

## 5. Classification depth — POST-FIRST-TOP-10

- Product ↔ OKPD2 mapping, только если fixture показывает пользу;
- versioning external classification mappings;
- richer product/material taxonomy;
- multiple external mappings per PNC reference;
- official OKVED edition/update lifecycle;
- explicit OKVED ↔ Industry mapping, если будет доказана потребность;
- separate approved Industry rules.

OKVED и Industry не входят в scoring v1.

## 6. Capacity and availability — POST-FIRST-TOP-10

- coarse confirmed capacity snapshots with comparable unit/period;
- current availability / earliest feasible completion;
- workload and calendar semantics;
- refresh/confirmation lifecycle;
- personnel/shifts where required;
- production route and time norms;
- evidence and confidence of estimates.

Нельзя заменять capacity значением `Equipment.quantity` или available area.
До появления approved model quantity/deadline remain UNKNOWN.

## 7. Processing depth — LATER

- max workpiece mass and missing equipment limits;
- richer geometry and multi-axis processing envelopes;
- material form/range restrictions;
- cross-equipment route feasibility;
- lifting/storage/infrastructure criteria for relevant opportunities.

`ProcessingEnvelope` не объявляется обязательной entity. Возможность отдельной
model оценивается только после первой fixture.

## 8. Execution / ERP — LATER

- redesign current `ProductionOrder` in a separate bounded context;
- transition from awarded opportunity/contract to internal execution;
- BOM, routes, operations and norms;
- scheduling, shifts and resource calendars;
- execution states/history;
- production documents and audit;
- cancellation/deletion lifecycle semantics.

CURRENT ProductionOrder foundation не продолжать как Stage 2/3 до этого
design. `OrderType` не считать procurement type.

## 9. CRM and commercial workflow — LATER

- leads/favorites and responsible users;
- application preparation;
- customer communications;
- contracts;
- invoices/payments;
- document flow;
- external CRM integrations.

Эти capabilities не входят в Matching v1.

## 10. Economics and analytics — LATER

- cost model;
- material and labor costs;
- logistics and financing;
- profitability;
- market trend analytics;
- conversion and win-rate history;
- impact simulation for new equipment/certificates;
- advanced recommendation analytics.

Нельзя объявлять opportunity прибыльной только по compatibility score.

## 11. MatchAssessment persistence — optional LATER decision

После first TOP-10 решить, нужен ли stored assessment history для:

- reproducibility across rule versions;
- audit and user comparison;
- analytics;
- debugging source/profile changes.

Compute-on-demand остаётся допустимым. Persistence не должна создавать
execution-order lifecycle.

## 12. Многопользовательский режим, доступ и конкурентное редактирование — LATER

- `User` и Auth;
- роли, permissions и RBAC;
- подтверждённая identity пользователя;
- журнал действий пользователей и audit trail;
- optimistic locking;
- revision/version tokens для конкурентного редактирования;
- обнаружение устаревшего изменения;
- обнаружение устаревшего подтверждения полноты;
- обработка конфликтов конкурентного редактирования;
- session management;
- PostgreSQL-тесты конкурентных пользовательских сценариев;
- multi-tenancy, если возникнет соответствующая продуктовая необходимость;
- retention и data isolation, необходимые выбранной access model.

Этот блок не является необходимым условием первого meaningful TOP-10. К нему
следует возвращаться после проверки основной однопользовательской продуктовой
цепочки на реальных данных либо при появлении фактической потребности в
одновременной работе нескольких пользователей с одним профилем.

Первая версия не объявляется навсегда однопользовательской: её архитектура не
должна намеренно препятствовать такому развитию. Однако multi-user mechanisms
не реализуются заранее и не увеличивают текущий MVP scope.

## 13. Registration onboarding — LATER depth

- provider-independent normalized ЕГРЮЛ schema;
- confirmed import and conflict resolution;
- fallback/manual correction;
- provider replacement and safe logging;
- Region mapping from address;
- OKVED version mismatch handling.

Registration lookup может улучшать onboarding, но не доказывает capability и
не блокирует first TOP-10.

## 14. Infrastructure and logistics — LATER depth

- railway infrastructure and rolling stock domain;
- special storage/handling rules;
- logistics cost/distance model;
- third-party logistics capability;
- infrastructure completeness confirmations when a rule needs absence facts.

CURRENT Warehouse/LiftingEquipment/Transport remain valid foundation, but are
not mandatory sections first matching profile.

## 15. API and operational architecture — after core design

- public route naming conventions;
- import job lifecycle;
- async processing only if fixture demonstrates need;
- idempotency implementation там, где её требует import/API contract;
- observability/metrics;
- deployment and scaling;
- API versioning.

Обычная idempotency и транзакционная целостность не являются
многопользовательской concurrency architecture. Механизмы совместного
редактирования из раздела 12 не добавлять до measured product need.
