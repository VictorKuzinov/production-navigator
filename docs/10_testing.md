# Автоматизированное тестирование backend

## Назначение и статус

Документ фиксирует фактически внедрённый стандарт автоматизированного тестирования backend Production Navigator. Основной test runner — `pytest`. Текущая suite находится в `backend/tests/` и проверяет завершённые вертикальные срезы `EnterpriseProfile`, `ProductionFacility`, `Equipment`, `Warehouse`, `LiftingEquipment`, `Transport`, `Material`, `MaterialItem` и `Product`.

Последний подтверждённый полный запуск завершён успешно:

```text
375 passed in 13.32s
```

Этот результат является текущим regression baseline. Документ не задаёт будущую CI-архитектуру, требования к coverage или альтернативную test database.

## Инструменты и конфигурация
Проект устанавливается в development environment в editable-режиме:

```bash
python -m pip install -e ".[test]"
```


Для автоматизированного тестирования используются следующие инструменты. `pytest`, `pytest-asyncio` и `aiosqlite` объявлены в optional group `project.optional-dependencies.test`; `httpx` входит в основные зависимости проекта.

| Инструмент | Назначение |
|---|---|
| `pytest` | Сбор, запуск и отчёт по тестам |
| `pytest-asyncio` | Выполнение async tests и async fixtures |
| `aiosqlite` | Асинхронный SQLAlchemy-драйвер изолированной SQLite test database |
| `httpx` | In-process HTTP-запросы к FastAPI через `AsyncClient` и `ASGITransport` |

Фактические pytest settings:

- `testpaths = ["tests"]`;
- `asyncio_mode = "auto"`;
- `asyncio_default_fixture_loop_scope = "function"`;
- `--import-mode=importlib` для независимого импорта одноимённых test-модулей в разных слоях;
- `--strict-markers` и краткий summary через `-ra`.

Async tests объявляются обычными `async def`. В suite не смешиваются `asyncio.run`, синхронный `TestClient` и async HTTP client.

## Структура test suite

```text
tests/
├── conftest.py
├── schemas/
├── services/
├── repositories/
└── api/
```

Каждый уровень проверяет только собственную ответственность:

| Уровень | Что проверяется | Инфраструктура |
|---|---|---|
| `schemas` | Pydantic validation, defaults, nullable-поля и PATCH presence через `model_fields_set`/`exclude_unset` | Без БД |
| `services` | Domain orchestration: существование родительских сущностей, ownership, reference validation, duplicate и NotFound behavior | `AsyncMock`/простые fake repositories, без БД |
| `repositories` | Фактические create/get/list/update/delete и наблюдаемое persistence behavior | Реальный `AsyncSession` с in-memory SQLite |
| `api` | HTTP status/body, маршрутизация, dependency injection, handlers и полный API → service → repository flow | Actual FastAPI app с test DB dependency override |

Один и тот же простой факт не дублируется во всех слоях. Повторная проверка допустима для регрессии, когда отдельно защищаются внутренняя ответственность слоя и внешний HTTP-контракт.

## Test database и изоляция

Repository и API tests используют только in-memory SQLite:

```text
sqlite+aiosqlite://
```

В `tests/conftest.py` для каждого теста создаётся отдельный async engine с `StaticPool`. Для SQLite включается `PRAGMA foreign_keys=ON`. Fixture `db_session` имеет function scope, поэтому каждый тест получает новое изолированное состояние; после теста in-memory engine освобождается через `dispose()`.

Test database инициализируется полным набором текущих ORM-таблиц:

```python
await connection.run_sync(Base.metadata.create_all)
```

Если полный `Base.metadata` совместим с test DB, нельзя вручную сокращать набор создаваемых таблиц до объектов, которые тест использует явно. ORM relationships, cascade behavior и lazy loading могут обращаться к таблицам косвенно; искусственно сокращённый набор таблиц способен вызывать ложные падения тестов и ошибки test infrastructure, не связанные с дефектом production-кода.

Fixtures создают только минимальные reference rows и domain rows, необходимые сценарию. Они не запускают production seeds, не используют фиксированные рабочие ID и не зависят от состояния development database.

## FastAPI dependency override

API tests используют фактический объект `app.main.app`, реальные routers, dependency factories, services, repositories, exception handlers и response schemas. Подменяется только источник `AsyncSession`.

Fixture `api_client` устанавливает стандартный FastAPI override:

```python
app.dependency_overrides[get_session] = override_get_session
```

`override_get_session` возвращает function-scoped test session. После теста исходный словарь overrides восстанавливается.

Дополнительно действует fail-closed защита: `app.db.dependencies.AsyncSessionLocal` подменяется функцией, которая немедленно поднимает `AssertionError`. Если override перестанет работать и production dependency будет вызвана, тест завершится ошибкой до попытки открыть development/production database session.

HTTP-вызовы выполняются через:

```python
ASGITransport(app=app, raise_app_exceptions=False)
AsyncClient(transport=transport, base_url="http://testserver")
```

Так проверяется реальный FastAPI wiring, а необработанные application exceptions наблюдаются как HTTP 500.

## Regression tests

Regression test добавляется для каждого подтверждённого дефекта приложения или нарушенного backend-контракта и проверяет поведение, а не наличие метода или строки кода.

Текущая suite содержит семь зафиксированных групп регрессий:

1. **ProductionFacility PATCH.** Ранее PATCH endpoint существовал, но `ProductionFacilityService.update` был удалён. `test_patch_production_facility_persists_changes` выполняет create → GET → PATCH → GET и подтверждает сохранение нового значения через полный API flow.
2. **Warehouse PATCH nullability.** Runtime ранее принимал explicit `null` для ORM non-nullable полей. Schema и API tests подтверждают отказ с validation/HTTP 422 для `warehouse_type_code`, `total_capacity_cube` и `temperature_control`, а также разрешённую очистку nullable `max_load_sqm`.
3. **LiftingEquipment location и ownership.** Schema, service, repository и API
   tests защищают все четыре комбинации `facility_id`/`warehouse_id` (только
   площадка, только склад, обе ссылки и обе ссылки `NULL`), проверяют
   принадлежность заданных объектов тому же profile, фактическую замену ссылок
   A→B, различие omitted и explicit `null` в PATCH, а также изоляцию
   profile-scoped listing.
4. **Transport validation, PATCH и profile isolation.** Schema tests проверяют
   `payload_tons > 0`, `quantity >= 1`, nullable `body_volume_cube` и условие
   `body_volume_cube > 0` при заданном значении, а также отклонение explicit
   `null` для обязательных полей. Service, repository и API tests защищают
   замену `TransportType`, `TransportScope` и `TransportOwnershipType`, отказ
   для отсутствующих reference codes, CRUD persistence и profile-scoped list
   isolation. Для `has_refrigeration` проверяются состояния `True`, `False` и
   `None`: `False` не теряется из-за truthiness, explicit `None` очищает
   nullable-поле, omitted-поле сохраняет старое значение, а пустой PATCH `{}`
   допустим как no-op.
5. **Material global CRUD, validation и safe delete.** Schema, service,
   repository и API tests проверяют глобальный CRUD без enterprise/profile
   scope, существование `MaterialGroup`, отклонение дубликата
   `(group_code, grade_name)` при create и в итоговом состоянии PATCH,
   empty/whitespace-only `grade_name`, explicit `null` для обязательных create
   и PATCH-полей, а также `density > 0` при заданном значении. Nullable
   `density` различает omitted PATCH, сохраняющий текущее значение, и explicit
   `null`, очищающий поле; пустой PATCH `{}` допустим как no-op. Удаление
   неиспользуемого Material разрешено, а Material со связанным MaterialItem не
   удаляется, при этом MaterialItem сохраняется.
6. **MaterialItem identity, PATCH и lifecycle.** Schema, service, repository и
   API tests защищают глобальный CRUD, closed vocabulary
   `unit_of_measure`, проверку `Material` и `MaterialForm`, finite positive
   `dimension_1`, правило `LIQUID_CHEMICAL` с `dimension_1 = null` и
   uniqueness identity, включая равенство nullable dimension. PATCH
   различает omitted и explicit `null`, проверяет resulting identity и
   допускает пустой no-op. MaterialItem, используемый `Product`,
   immutable и не удаляется; неиспользуемый item
   удаляется.
7. **Product profile scope, identity, validation и lifecycle.** Schema,
   service, repository и API tests защищают profile-scoped create/list и
   глобальные item routes, обязательные `ProductType`/`MaterialItem` references,
   trim leading/trailing whitespace с сохранением case и exact case-sensitive
   uniqueness `(profile_id, sku_code)` при create и resulting-state PATCH.
   Проверяются finite positive `weight_net`/`required_ra`, диапазон
   `required_it_grade=1..18`, explicit `null` только для nullable quality
   fields, omitted/explicit-null PATCH semantics и пустой no-op. Product с
   ProductionOrder immutable и не удаляется; unused Product допускает PATCH и
   DELETE.

Regression expectation не подгоняется под дефект. Если тест выявляет новый production bug, production-код исправляется отдельным remediation cycle, а тест сохраняет требуемый контракт.

## Подтверждённый состав

| Уровень | Тестов |
|---|---:|
| Schemas | 139 |
| Services | 111 |
| Repositories | 21 |
| API/integration | 104 |
| **Всего** | **375** |

Подсчёт учитывает собранные pytest cases, включая параметризованные сценарии,
и соответствует подтверждённому результату последнего полного запуска:
`375 passed in 13.32s`.

Срез `Transport` добавил 56 tests: schemas — 19, services — 19,
repositories — 2, API/integration — 16. Вместе с предыдущим baseline из 89
tests это дало исторический post-Transport итог 145.

Срез `Material` добавил 52 tests: schemas — 18, services — 15,
repositories — 3, API/integration — 16. Вместе с post-Transport baseline из
145 tests это дало исторический post-Material итог 197.

Срез `MaterialItem` добавил 77 tests: schemas — 33, services — 17,
repositories — 3, API/integration — 24. Вместе с post-Material baseline из
197 tests это дало исторический post-MaterialItem итог 274.

Срез `Product` добавил 101 test: schemas — 43, services — 23,
repositories — 3, API/integration — 32. Вместе с post-MaterialItem baseline из
274 tests это даёт текущий подтверждённый итог 375. Итоговые layer counts:
139 schemas + 111 services + 21 repositories + 104 API/integration = 375.

## Финальная проверка Transport

После интеграции Transport выполнены автоматизированные проверки:

- `ruff check app tests` → `All checks passed!`;
- полный `python -m pytest -q` → `145 passed in 4.82s`.

Manual Swagger smoke на development backend подтвердил следующий фактический
happy path:

1. `POST /api/v1/enterprises/2/transports` создал Transport `id=1` с типом
   `HEAVY_TRUCK`, scope `REGIONAL`, ownership `PNC_OWN_OWNED`,
   `payload_tons=20`, `body_volume_cube=82`, `has_refrigeration=null` и
   `quantity=1`.
2. `GET /api/v1/enterprises/2/transports` вернул созданную запись в списке
   профиля.
3. `PATCH /api/v1/transports/1` с `has_refrigeration=false` и
   `body_volume_cube=null` сохранил `False`, очистил объём кузова и не изменил
   остальные поля.
4. `DELETE /api/v1/transports/1` вернул HTTP 200 и удалил объект.

## Финальная проверка Material

После интеграции Material выполнены автоматизированные проверки:

- `ruff check app tests` → `All checks passed!`;
- полный `pytest` → `197 passed in 6.34s`.

Manual Swagger smoke на development backend подтвердил только следующий
фактически выполненный happy path глобального каталога Material:

1. `POST /api/v1/materials` с body
   `{"group_code":"STEEL_STAINLESS","grade_name":"12Х18Н10Т","density":7900}`
   вернул HTTP 200 и создал Material `id=1` с переданными значениями.
2. `GET /api/v1/materials` вернул HTTP 200; глобальный список содержал
   созданный Material.
3. `PATCH /api/v1/materials/1` с body `{"density":null}` вернул HTTP 200,
   очистил `density` и сохранил `group_code` и `grade_name`.
4. `DELETE /api/v1/materials/1` вернул HTTP 200 и удалённый объект.

Остальные Material scenarios, включая
`GET /api/v1/materials/{material_id}`, duplicate, 404, 409, 422 и delete guard
с MaterialItem, подтверждены automated tests, но не заявляются как выполненная
часть этого manual Swagger smoke.

## Финальная проверка MaterialItem

После интеграции MaterialItem на реальном working backend выполнены
автоматизированные проверки:

- `ruff check app tests` → `All checks passed!`;
- полный `pytest` → `274 passed in 11.11s`.

### POSITIVE PATH

1. `POST /api/v1/materials` вернул HTTP 200 и создал synthetic Material
   `id=2`, `group_code=STEEL_CARBON`, `grade_name=MI_SMOKE_20260827`,
   `density=7850`.
2. `POST /api/v1/material-items` вернул HTTP 200 и создал
   MaterialItem `id=1` с `material_id=2`, `material_form_code=SHEET_PLATE`,
   `dimension_1=10`, `unit_of_measure=kg`.
3. `GET /api/v1/material-items/1` вернул HTTP 200; identity совпала
   с созданной записью.
4. `PATCH /api/v1/material-items/1` с body `{"dimension_1":null}` вернул
   HTTP 200, применил explicit null и не изменил остальные identity fields.
5. `PATCH /api/v1/material-items/1` с body `{"dimension_1":10}` вернул
   HTTP 200 и восстановил состояние для negative smoke.

### NEGATIVE / EXCEPTION PATH

1. `POST /api/v1/material-items` с `material_id=999999` возбудил
   `MaterialNotFoundError`: HTTP 404,
   `{"detail":"Material 999999 not found."}` — PASS.
2. `POST /api/v1/material-items` с `material_form_code=NO_SUCH_FORM` возбудил
   `MaterialFormNotFoundError`: HTTP 404,
   `{"detail":"Material form NO_SUCH_FORM not found."}` — PASS.
3. `GET /api/v1/material-items/9999` возбудил
   `MaterialItemNotFoundError`: HTTP 404,
   `{"detail":"Material item 9999 not found."}` — PASS.
4. `PATCH /api/v1/material-items/1` с
   `{"material_form_code":"LIQUID_CHEMICAL"}` при `dimension_1=10` возбудил
   `InvalidMaterialItemError`: HTTP 422,
   `{"detail":"dimension_1 must be null for LIQUID_CHEMICAL."}` — PASS.
   Recovery PATCH с
   `{"material_form_code":"LIQUID_CHEMICAL","dimension_1":null}` вернул
   HTTP 200.
5. Повторный `POST /api/v1/material-items` с identity
   `(material_id=2, material_form_code=LIQUID_CHEMICAL, dimension_1=null, unit_of_measure=kg)`
   возбудил `DuplicateMaterialItemError`: HTTP 409,
   `{"detail":"Material item with the same identity already exists."}` — PASS.
6. `POST /api/v1/material-items` с `unit_of_measure="KG"` вернул HTTP 422;
   top-level `detail` был непустым list, error содержал `type`, `loc`, `msg`,
   `input`, а `loc` начинался с `body` — PASS.
7. Для `MaterialItemInUseError` был создан временный Product
   `id=1`, `sku_code=STAGE13-SMOKE-651599F4E7574957997F498BD7FF9B6C`,
   связанный с MaterialItem `id=1`. `DELETE /api/v1/material-items/1`
   вернул HTTP 409,
   `{"detail":"Material item 1 is used by products."}` — PASS.

### Cleanup

- Временный Product fixture `id=1` удалён.
- MaterialItem `id=1` после удаления Product удалён через API с HTTP 200.
- Synthetic Material `id=2` намеренно сохранён для будущих
  development smoke tests; cleanup является намеренно частичным.

## Финальная проверка Product

После интеграции Product на реальном working backend выполнены
автоматизированные проверки:

- `ruff check app tests` → `All checks passed!`;
- полный `pytest` → `375 passed in 13.32s`.

### POSITIVE PATH

1. `POST /api/v1/material-items` вернул HTTP 200 и создал временный
   MaterialItem `id=2`.
2. `GET /api/v1/enterprises/2/products` до create вернул HTTP 200 и `[]`.
3. `POST /api/v1/enterprises/2/products` вернул HTTP 200 и создал Product
   `id=2`, `profile_id=2`; outer whitespace был удалён из
   `sku_code=Product-Smoke-20260831A` и `name=Product Smoke 20260831A`, case
   сохранился.
4. `GET /api/v1/products/2` и `GET /api/v1/enterprises/2/products` вернули
   HTTP 200; get/list identity совпала с созданной записью.
5. `PATCH /api/v1/products/2` с body `{"required_ra":null}` вернул HTTP 200,
   применил explicit null и сохранил остальные fields.
6. После отдельного cleanup временного ProductionOrder
   `DELETE /api/v1/products/2` и `DELETE /api/v1/material-items/2` вернули
   HTTP 200 и удалили оба временных объекта.

### NEGATIVE / EXCEPTION PATH

1. Отсутствующий EnterpriseProfile вызвал `EnterpriseProfileNotFoundError`:
   HTTP 404, ожидаемый `detail` — PASS.
2. Неизвестный ProductType вызвал `ProductTypeNotFoundError`: HTTP 404,
   ожидаемый `detail` — PASS.
3. Отсутствующий MaterialItem вызвал `MaterialItemNotFoundError`: HTTP 404,
   ожидаемый `detail` — PASS.
4. Отсутствующий Product вызвал `ProductNotFoundError`: HTTP 404, ожидаемый
   `detail` — PASS.
5. Повторный create с тем же resulting trimmed SKU вызвал
   `DuplicateProductError`: HTTP 409, ожидаемый `detail` — PASS.
6. Whitespace-only `sku_code` вернул HTTP 422; validation `detail` содержал
   `type`, `loc=["body","sku_code"]`, `msg` и `input=""` — PASS.
7. При временном `ProductionOrder id=1` пустой PATCH `{}` вернул HTTP 200 и
   не изменил Product; non-empty PATCH вызвал `ProductInUseError` с HTTP 409 и
   ожидаемым `detail`; DELETE вызвал `ProductInUseError` с HTTP 409 и ожидаемым
   `detail` — PASS.

Swagger отображал фактически проверенные custom `404/409` responses как
`Undocumented`, при этом реальные statuses и bodies соответствовали контракту.
Временный ProductionOrder был удалён отдельной approved DB cleanup operation;
Product и MaterialItem удалены через API.

## Стандартные команды

Команды выполняются из каталога `backend`.

Полный запуск тестов:

```powershell
pytest
```
Эквивалентный вариант: 
```powershell
python -m pytest
```


Ruff только для тестов:

```powershell
ruff check tests
```

Совместная проверка production-кода и тестов:

```powershell
ruff check app tests
```

## Правила добавления тестов

- Тест называется по проверяемому контракту, например `test_update_warehouse_rejects_null_total_capacity`.
- Schema test проверяет Pydantic contract, service test — orchestration, repository test — persistence, API test — HTTP contract и wiring.
- Service, который проверяется, не мокается; мокируются его внешние repository dependencies.
- Repository/API tests остаются async и используют только `db_session` из `conftest.py`.
- Test data создаётся fixtures; нельзя использовать ID или строки из development database.
- Reference fixtures содержат минимальный набор валидных полей `PNCBaseReference`.
- Тесты не зависят от порядка запуска и состояния другого теста.
- Полные OpenAPI/JSON snapshots не используются, если контракт можно проверить устойчивыми meaningful fields.

## Definition of Done для новой backend-сущности

Новая backend-сущность считается завершённой после последовательного выполнения:

1. Добавлены автоматизированные tests на релевантных уровнях: schemas, services, repositories и API.
2. Ruff завершён без ошибок для затронутого кода и тестов.
3. Полный `pytest` завершён успешно.
4. Выполнен короткий Swagger smoke для основных happy-path операций и визуальной проверки опубликованного HTTP-контракта.
5. `docs/10_testing.md` синхронизирован с фактически завершённым slice и
   воспроизводимым полным test run.

Swagger smoke выполняется после автоматизированных проверок. Он не заменяет pytest и не является regression suite: ручная проверка не обеспечивает воспроизводимость, изоляцию данных и защиту ранее обнаруженных дефектов.

После создания или изменения automated tests для завершённого vertical slice
этот документ обновляется до того, как slice считается завершённым. Минимально
синхронизируются:

- перечень покрытых slices;
- фактически воспроизводимый full-pytest baseline;
- новые существенные regression scenarios;
- изменения test infrastructure, если они были.

Исторический test baseline нельзя оставлять в `docs/10_testing.md` после
завершения нового slice.
