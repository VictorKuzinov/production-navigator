# Производственный профиль

## Статус документа

Документ описывает профиль с позиции Matching v1 и разделяет **CURRENT**,
**TARGET MVP** и **LATER**. Логические target concepts не объявляются
реализованными ORM-сущностями.

## 1. Назначение профиля

Производственный профиль — независимый от конкретной закупки набор
подтверждённых facts о предприятии. Он отвечает на вопрос:

> Какие требования внешней возможности предприятие подтверждённо выполняет,
> какие capability отсутствуют, а по каким данным вывод пока невозможен?

Профиль не является цифровым паспортом «на все случаи» и не должен быть
полностью заполнен до первого результата. Он должен быть достаточен для
объяснимого matching.

## 2. CURRENT profile foundation

В текущей ORM корнем является `EnterpriseProfile`. С ним связаны:

```text
EnterpriseProfile
├── Product → ProductType / MaterialItem → Material
├── Equipment → EquipmentType / ProductionFacility
├── QualityCapability
├── EnterpriseCertificate → CertificateType
├── Region
├── ProductionFacility
├── Warehouse
├── LiftingEquipment
├── Transport
├── EnterpriseOKVED → OKVED
├── EnterpriseIndustry → Industry
└── ProductionOrder
```

`TechnologyType` существует только как vocabulary и не связан с профилем.
Прямой capability-связи профиля с обрабатываемыми `MaterialGroup`/`Material`
нет. Цепочка `Product → MaterialItem → Material` описывает материал заведённых
изделий и не доказывает общий material capability set.

`ProductionOrder` существует в CURRENT ORM, но не является частью profile
input для TARGET MVP matching. Он остаётся frozen и отдельно рассматривается
как возможный LATER execution concept.

## 3. TARGET MVP profile core

| Profile concept | Роль в Matching v1 |
|-----------------|---------------------|
| `EnterpriseProfile` | Root и `region_code` |
| `Product` / `ProductType` | Небольшой soft experience/readiness signal |
| `Equipment` / `EquipmentType` | Тип, CNC, axes, work zones, max diameter |
| `ProfileTechnologyCapability` | Поддерживаемые/неподдерживаемые технологии |
| `ProfileMaterialCapability` | Поддерживаемые/неподдерживаемые группы и марки материалов |
| `QualityCapability` | IT grade, Ra, measuring tools, CMM |
| `EnterpriseCertificate` | Тип и срок действия документа |
| `Region` | Soft geographic context |
| `ProfileSectionCompleteness` | Различает отсутствие row и доказанное отсутствие capability |

Имена `ProfileTechnologyCapability`, `ProfileMaterialCapability` и
`ProfileSectionCompleteness` логические. Окончательные class/table names и
persistence design ещё не утверждены.

## 4. Capability state

Для target technology и material capability используется явное состояние:

```text
SUPPORTED
UNSUPPORTED
UNKNOWN
```

- `SUPPORTED` — capability подтверждена для указанного vocabulary item;
- `UNSUPPORTED` — пользователь/уполномоченный оператор явно подтвердил
  отсутствие capability;
- `UNKNOWN` — достоверного positive или negative fact нет.

Отсутствие capability row не эквивалентно `UNSUPPORTED`, пока соответствующий
section scope не имеет `CONFIRMED_COMPLETE`.

## 5. Section completeness

Для каждого релевантного раздела используется одно из состояний:

```text
CONFIRMED_COMPLETE
PARTIAL
UNKNOWN
```

| State | Происхождение | Семантика для matching |
|-------|---------------|-------------------------|
| `UNKNOWN` | Начальное состояние или происхождение полноты неизвестно | Отсутствие row ничего не доказывает |
| `PARTIAL` | Пользователь признал список неполным либо изменил ранее подтверждённый раздел | Known positive/numeric facts применимы; отсутствие row не является negative fact |
| `CONFIRMED_COMPLETE` | Явное human confirmation конкретного section/scope/snapshot | Отсутствие row в подтверждённом scope может означать отсутствие capability, но hard outcome всё равно требует MANDATORY requirement и утверждённого rule |

Обязательные правила:

- import, seed, DB default, наличие rows и процент заполнения никогда
  автоматически не создают `CONFIRMED_COMPLETE`;
- confirmation фиксирует section, scope, snapshot, confirmer и timestamp;
- добавление, изменение или удаление capability после confirmation переводит
  section в `PARTIAL`;
- пустой `CONFIRMED_COMPLETE` section означает подтверждённое отсутствие
  capabilities в scope;
- пустой `PARTIAL/UNKNOWN` section ничего не доказывает.

Для первой narrow fixture явное состояние обязательно как минимум для
technology и material sections. Большой CRUD workflow для этого не нужен.

## 6. Роль отдельных profile facts

### Product / ProductType

Совпадение `ProductType` подтверждает опыт и даёт небольшой soft signal.
Отсутствие Product не доказывает невозможность производства. Product name не
используется для fuzzy matching. Product ↔ OKPD2 mapping не требуется для
первой fixture.

### Equipment

Matching использует read-only projection существующих подтверждённых fields:

- `equipment_type_code`;
- `cnc`;
- `axes`;
- `working_zone_x/y/z`;
- `max_diameter`.

`Equipment.quantity` — inventory count, а не производительность за период.
Нельзя выводить capacity из числа станков.

`Equipment.cnc` имеет technical default `false`. Без подтверждения этот default
не является доказанным отсутствием CNC capability.

### QualityCapability

Числовые сравнения:

```text
profile.min_it_grade <= required_it_grade
profile.min_ra       <= required_ra
```

`measuring_tools` и `cim_machine` имеют technical default `false`; hard rule
требует подтверждённого human fact, а не только DB default.

### Certificates

Проверяются `certificate_type_code` и `expiry_date`. Отсутствие или истечение
документа не является автоматическим hard conflict:

- неполный certificate section → `UNKNOWN`;
- документ можно получить/продлить → `remediable_limitation`;
- hard допустим только при подтверждённой полноте, MANDATORY requirement,
  required date и доказанной невозможности устранения к этой дате.

### Region

Совпадение региона — небольшой soft signal. Различие регионов само по себе не
является hard conflict. При отсутствии сопоставимого mapping результат
`UNKNOWN`.

## 7. Blocking profile gaps

### BLOCKING BEFORE FIRST MEANINGFUL TOP-10

1. `ProfileTechnologyCapability`.
2. `ProfileMaterialCapability`.
3. `ProfileSectionCompleteness` semantics/mechanism.

Других blocking gaps для первого narrow meaningful TOP-10 нет.

### CAN REMAIN UNKNOWN

- Product ↔ OKPD2 mapping;
- processing limits, отсутствующие в `Equipment`;
- max workpiece mass;
- quantity/capacity;
- availability и earliest feasible completion;
- execution feasibility;
- region/logistics при отсутствии mapping;
- certificate absence при неподтверждённом section;
- technical boolean defaults;
- ненормализованные optional profile facts.

Эти gaps снижают coverage и порождают объяснения, но не блокируют matching.

## 8. OPTIONAL / LATER profile depth

Следующие CURRENT entities могут дополнять отдельные rules, но не являются
обязательными разделами первого matching profile:

- `ProductionFacility`;
- `Warehouse`;
- `LiftingEquipment`;
- `Transport`;
- `EnterpriseIndustry` / `Industry`;
- `EnterpriseOKVED` / `OKVED`;
- CompanySize и расширенные регистрационные данные.

Capacity, availability, production calendar, personnel, routes и shifts —
LATER. `ProcessingEnvelope` не вводится как обязательная entity; существующие
equipment limits используются как read-only projection.

## 9. Profile readiness for matching

Перед первой meaningful fixture блокируют только три gap из раздела 7:

1. `ProfileTechnologyCapability`;
2. `ProfileMaterialCapability`;
3. `ProfileSectionCompleteness` mechanism и явный state для technology/material.

`EnterpriseProfile` root уже является существующей основой, а не дополнительным
gap или prerequisite.

Known Equipment/Product/Quality/Certificate/Region facts используются
read-only matching projection только если известны. Их отсутствие сохраняется
как `UNKNOWN`; заполненность этих optional facts не является prerequisite
первого TOP-10.

Read-only projection и корректная `UNKNOWN` semantics — правила matching engine,
а не дополнительные data-readiness requirements. Других blocking gaps нет.
