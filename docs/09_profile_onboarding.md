# Онбординг производственного профиля

## 1. Назначение и статус

TARGET MVP onboarding формирует не полный цифровой паспорт, а минимально
достаточный и честно подтверждённый matching profile. Документ различает
**CURRENT**, **TARGET MVP** и **LATER**.

## 2. CURRENT

Backend уже предоставляет API vertical slices для ряда profile entities.
Отдельный завершённый guided onboarding flow, который собирает capability
states, section completeness и запускает TOP-10, CURRENT не реализован.

`backend/app/integrations/fns/client.py` выполняет низкоуровневый lookup raw
registration data. Нормализованный import/confirmation flow по ИНН не считается
реализованным onboarding.

CURRENT `ProductionOrder` и Product in-use guard существуют, но не участвуют в
TARGET onboarding и не показываются как этап подготовки внешних закупок.

## 3. TARGET onboarding outcome

Пользователь должен получить:

1. профиль, содержащий known production facts;
2. явные UNKNOWN вместо выдуманных negative defaults;
3. явный completeness state (`CONFIRMED_COMPLETE`, `PARTIAL` или `UNKNOWN`) для
   technology/material sections;
4. возможность загрузить prepared opportunity set;
5. объяснимый TOP-10 или честный `INSUFFICIENT_DATA` с планом дозаполнения.

Процент заполнения не заменяет semantic readiness.

## 4. Приоритет сбора данных

TARGET последовательность:

1. базовые сведения предприятия;
2. продукция / направления;
3. материалы;
4. технологии;
5. оборудование;
6. качество;
7. сертификаты;
8. регион.

Дополнительная инфраструктура может заполняться позже.

## 5. Step 1 — Базовые сведения

Минимально нужен `EnterpriseProfile` с рабочим company name. ИНН/ОГРН,
website, employee count и company size можно добавить позже, если они не нужны
конкретному approved rule.

Registration lookup по ИНН — optional accelerator:

- raw provider data сначала нормализуются;
- пользователь подтверждает предложенные сведения;
- provider failure не блокирует profile creation;
- OKVED остаётся registration context и не создаёт capabilities;
- Industry не назначается автоматически из OKVED.

## 6. Step 2 — Продукция / направления

Пользователь указывает основные Product/ProductType, если они известны.

Объяснение интерфейса:

> Каталог продукции повышает confidence в уже освоенных направлениях, но его
> отсутствие не означает, что предприятие не способно изготовить новый предмет.

Product — малый experience signal. Product ↔ OKPD2 mapping не требуется.

## 7. Step 3 — Material capability

Пользователь выбирает поддерживаемые MaterialGroup и при необходимости
конкретные Material. Для каждого known item нужен state:

```text
SUPPORTED / UNSUPPORTED / UNKNOWN
```

Цепочка Product → MaterialItem не заменяет этот section.

### Mandatory completeness-state step

После заполнения система задаёт отдельный вопрос:

> Раздел просмотрен, и список обрабатываемых материалов полный для указанного
> scope?

Варианты приводят к `CONFIRMED_COMPLETE`, `PARTIAL` или `UNKNOWN`.
До первого meaningful TOP-10 для material и technology sections обязателен
явный state из этого набора; первый TOP-10 разрешён при любом из трёх states.
`CONFIRMED_COMPLETE` не является prerequisite и возникает только когда
пользователь или уполномоченный оператор явно подтвердил, что section scope
просмотрен и список полон. `PARTIAL` и `UNKNOWN` — допустимые честные состояния:
они ограничивают hard conclusions и уменьшают coverage, но не блокируют
matching или TOP-10.

Import, seed, DB default, row count и progress percentage никогда автоматически
не создают `CONFIRMED_COMPLETE`.

## 8. Step 4 — Technology capability

Пользователь выбирает `TechnologyType` и states:

```text
SUPPORTED / UNSUPPORTED / UNKNOWN
```

### Mandatory completeness-state step

> Раздел просмотрен, и список доступных технологий полный для указанного scope?

Как и у materials, изменение после confirmation переводит section в `PARTIAL`
до повторного подтверждения.

## 9. Step 5 — Equipment

Приоритетные fields:

- EquipmentType;
- CNC, если факт подтверждён;
- axes;
- work zones X/Y/Z;
- max diameter.

Пользователь может оставить неизвестные limits пустыми. Technical
`cnc=false` не должен показываться как подтверждённое «ЧПУ отсутствует», пока
пользователь это не подтвердил.

Max workpiece mass и полный ProcessingEnvelope не обязательны. Equipment count
не представляется как capacity.

## 10. Step 6 — Quality

Собираются известные:

- best IT grade;
- minimum achievable Ra;
- measuring tools;
- CMM;
- optional notes/evidence.

Technical boolean defaults не считаются ответом пользователя. UNKNOWN
разрешён и будет объяснён в matching.

## 11. Step 7 — Certificates

Собираются типы документов, issue/expiry dates и known scope. Интерфейс должен
различать:

- документ есть и действителен;
- документ можно получить/продлить;
- документ подтверждённо невозможно обеспечить к required date;
- section неполный/UNKNOWN.

Отсутствие row в неподтверждённом section не является hard conflict.

## 12. Step 8 — Region

Region указывается, если доступен reliable local code. Он используется как
небольшой soft context. Отсутствие mapping не блокирует matching.

## 13. Readiness gate

### BLOCKING BEFORE FIRST MEANINGFUL TOP-10

1. Technology capability section.
2. Material capability section.
3. Section completeness mechanism и явные states для этих sections.

Для каждой technology/material section должен быть явно выбран
`CONFIRMED_COMPLETE`, `PARTIAL` или `UNKNOWN`. Первый TOP-10 разрешён при любом
из этих states; `CONFIRMED_COMPLETE` не является обязательным prerequisite.

### CAN REMAIN UNKNOWN

- Product ↔ OKPD2;
- absent equipment processing limits/max mass;
- quantity/capacity;
- availability/execution feasibility;
- region/logistics mapping;
- certificate absence in unconfirmed section;
- technical boolean defaults;
- optional unnormalized facts.

Readiness означает наличие трёх blocking elements, а не 100% progress bar или
обязательную полную подтверждённость sections.

## 14. После profile readiness

Пользователь импортирует prepared CSV/JSON/fixture с opportunities. Система:

1. валидирует identity and structured signals;
2. не превращает blanks в negative values;
3. оценивает каждый object;
4. возвращает TOP-10 и explanations;
5. предлагает заполнить конкретные missing profile data, влияющие на coverage.

Live ЕИС не нужен для этого flow.

## 15. OPTIONAL / LATER onboarding

После первого TOP-10 можно предложить расширенные sections:

- ProductionFacility and utilities;
- Warehouse;
- LiftingEquipment;
- Transport/logistics;
- capacity and availability snapshots;
- expanded registration/Industry context;
- live source connections;
- execution/ERP setup.

CRM, scheduling и ProductionOrder lifecycle не являются onboarding steps
TARGET MVP.

## 16. UX rules

- Всегда объяснять, зачем спрашивается fact и какой criterion его использует.
- Разрешать сохранить UNKNOWN и вернуться позже.
- Не выдавать progress percentage за confirmation.
- Показывать, кто и когда подтвердил complete section.
- После изменения confirmed section явно показывать `PARTIAL`.
- Не обещать MATCH до расчёта; не скрывать low coverage.
- Следующий recommended question выбирается по missing_data TOP-10, а не по
  полноте optional цифрового паспорта.
