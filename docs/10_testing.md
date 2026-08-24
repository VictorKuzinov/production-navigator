# Автоматизированное тестирование backend

## Назначение и статус

Документ фиксирует фактически внедрённый стандарт автоматизированного тестирования backend Production Navigator. Основной test runner — `pytest`. Текущая suite находится в `backend/tests/` и проверяет завершённые вертикальные срезы `EnterpriseProfile`, `ProductionFacility`, `Equipment`, `Warehouse` и `LiftingEquipment`. `Transport` ещё не реализован и Transport-specific tests в suite отсутствуют.

Последний подтверждённый полный запуск завершён успешно:

```text
89 passed
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

Текущая suite содержит три зафиксированные группы регрессий:

1. **ProductionFacility PATCH.** Ранее PATCH endpoint существовал, но `ProductionFacilityService.update` был удалён. `test_patch_production_facility_persists_changes` выполняет create → GET → PATCH → GET и подтверждает сохранение нового значения через полный API flow.
2. **Warehouse PATCH nullability.** Runtime ранее принимал explicit `null` для ORM non-nullable полей. Schema и API tests подтверждают отказ с validation/HTTP 422 для `warehouse_type_code`, `total_capacity_cube` и `temperature_control`, а также разрешённую очистку nullable `max_load_sqm`.
3. **LiftingEquipment location и ownership.** Schema, service, repository и API
   tests защищают все четыре комбинации `facility_id`/`warehouse_id` (только
   площадка, только склад, обе ссылки и обе ссылки `NULL`), проверяют
   принадлежность заданных объектов тому же profile, фактическую замену ссылок
   A→B, различие omitted и explicit `null` в PATCH, а также изоляцию
   profile-scoped listing.

Regression expectation не подгоняется под дефект. Если тест выявляет новый production bug, production-код исправляется отдельным remediation cycle, а тест сохраняет требуемый контракт.

## Подтверждённый состав

| Уровень | Тестов |
|---|---:|
| Schemas | 26 |
| Services | 37 |
| Repositories | 10 |
| API/integration | 16 |
| **Всего** | **89** |

Подсчёт учитывает собранные pytest cases, включая параметризованные сценарии,
и соответствует подтверждённому результату последнего полного запуска:
`89 passed`.

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
