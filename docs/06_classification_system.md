# Справочники и классификаторы

## 1. Назначение и статусы

Документ фиксирует роль classifications в Matching v1 и различает
**CURRENT**, **TARGET MVP** и **LATER**. Наличие reference table не означает,
что её code автоматически участвует в score.

## 2. Общие правила

1. Классификатор нормализует термин, но сам по себе не доказывает capability.
2. External code участвует в matching только при утверждённом mapping к profile
   vocabulary.
3. Отсутствующий mapping даёт UNKNOWN/context, а не mismatch.
4. Registration, market context и production capability не смешиваются.
5. `OrderType` не переиспользуется как procurement procedure type.

## 3. CURRENT classification foundation

В рабочей модели существуют корпоративные PNC references, включая:

- `EquipmentType`;
- `TechnologyType`;
- `MaterialGroup` и `MaterialForm`;
- `ProductType`;
- `CertificateType`;
- `Industry`;
- `Region`;
- `OrderType`;
- company size, warehouse, crane and transport references.

`OKVED` хранится как внешний регистрационный классификатор с собственной
иерархией и не является PNC capability reference.

Наличие `TechnologyType` CURRENT не означает наличие technology capability у
конкретного профиля: profile link отсутствует.

## 4. TARGET MVP roles

| Classification | Роль в Matching v1 | Не означает |
|----------------|---------------------|-------------|
| `ProductType` | Малый soft experience/readiness signal | Доказанную capability или точное предметное совпадение |
| `TechnologyType` | Vocabulary technology requirement и profile capability | Capability без profile link/state |
| `MaterialGroup` / `Material` | Vocabulary material requirement и capability | Что master-data row принадлежит профилю |
| `EquipmentType` | Vocabulary equipment requirement и existing Equipment fact | Достаточность numeric limits/availability |
| `CertificateType` | Vocabulary compliance requirement и enterprise certificate | Автоматический hard conflict при отсутствии row |
| `Region` | Soft geographic context | Запрет межрегионального выполнения |
| `OKVED` | Registration context | Production capability или scoring signal |
| `Industry` | Market/application context | Scoring criterion v1 |
| `OrderType` | CURRENT internal order vocabulary, frozen with ProductionOrder | Тип закупочной процедуры |
| `OKPD2` | Optional opportunity context | Scoring signal без approved Product mapping |

## 5. ProductType

`ProductType` характеризует общий вид уже выпускаемой продукции. В первой
narrow fixture:

- совпадение даёт soft criterion value;
- отсутствие совпавшего Product даёт soft zero только в этом критерии;
- Product mismatch никогда не создаёт hard conflict;
- Product name не сравнивается fuzzy;
- вес Product experience — `8` из provisional baseline.

ProductType не заменяет material, technology, equipment, dimensions и quality
criteria.

## 6. TechnologyType

`TechnologyType` — vocabulary для:

- `ProcurementOpportunity.technology_requirements`;
- логического `ProfileTechnologyCapability`.

Target capability state: `SUPPORTED/UNSUPPORTED/UNKNOWN`. Отсутствие profile
capability row при `PARTIAL/UNKNOWN` section не означает unsupported.

Окончательная связь vocabulary с profile/equipment/facility не проектируется в
этом документе.

## 7. MaterialGroup / Material / MaterialForm

- `MaterialGroup` даёт coarse group match;
- `Material` даёт exact grade match;
- `MaterialForm` и `MaterialItem` могут уточнять форму/размер, если этого
  требует fixture;
- master-data entities не принадлежат профилю;
- capability выражается отдельным target profile link.

Product → MaterialItem → Material — evidence материала конкретного продукта,
но не полный material capability set.

## 8. EquipmentType

`EquipmentType` связывает structured requirement с существующим Equipment.
Дальнейшее сравнение использует подтверждённые CNC/axes/work-zone/diameter
facts. Сам code типа не подтверждает numeric feasibility.

Technical `Equipment.cnc=false` без confirmation не является доказанным
несоответствием.

## 9. CertificateType

`CertificateType` нормализует обязательный документ. Outcome зависит от:

- requirement strength;
- required date/validity period, если они известны;
- фактического EnterpriseCertificate и expiry;
- completeness certificate section;
- возможности получить или продлить документ.

Отсутствие code в неполном profile section → UNKNOWN. Получаемый/продлеваемый
документ → remediable limitation. Hard требует доказанной невозможности к
required date.

## 10. Region

Opportunity и profile должны использовать сопоставимый canonical region code.
Same region даёт небольшой positive signal. Разные regions не создают hard
conflict. Если mapping внешнего значения отсутствует, criterion UNKNOWN.

## 11. OKVED

OKVED:

- описывает зарегистрированные виды экономической деятельности;
- может импортироваться как registration context после проверки;
- не доказывает оборудование, материалы, технологии или качество;
- не участвует в score v1;
- не назначает Industry автоматически.

Основной `EnterpriseOKVED.is_primary` и основной `EnterpriseIndustry.is_primary`
имеют разную семантику.

## 12. Industry

Industry — PNC market/application context. В Matching v1:

- не участвует в score;
- не заменяет OKVED;
- не активирует compliance rule автоматически;
- может получить роль позже только через отдельное утверждённое rule.

Кандидатный `BR_COM_001` не активируется без юридической/нормативной
верификации.

## 13. OrderType

CURRENT `OrderType` обслуживает `ProductionOrder` и описывает характер
внутреннего производственного заказа. В TARGET MVP:

- не является `procurement_type`;
- не используется ingestion или matching;
- frozen вместе с ProductionOrder;
- не переносится в Market Opportunity Domain без redesign.

Procurement type, если дан источником, хранится как отдельное source-side
display/filter value.

## 14. OKPD2

`ProcurementOpportunity.okpd2_codes` можно сохранять для provenance,
отображения и будущей нормализации. В first narrow fixture:

- Product ↔ OKPD2 mapping не требуется;
- без mapping OKPD2 не участвует в score;
- отсутствие mapping не создаёт mismatch;
- решение о mapping принимается после end-to-end fixture.

## 15. CURRENT references вне core matching

CompanySize, MaterialForm, WarehouseType, CraneType, TransportType,
TransportScope и TransportOwnershipType сохраняют текущую profile/infrastructure
роль. Они могут участвовать в специальных future criteria, но не являются
blocking requirements первого TOP-10.

## 16. External values and import

Prepared import обязан:

- валидировать codes по target vocabulary;
- сохранять raw/display value отдельно от reliable canonical code, если это
  потребуется design stage;
- не создавать reference row автоматически из неизвестной строки;
- не применять silent case folding/conversion, кроме утверждённой
  canonicalization конкретного поля;
- возвращать validation error или UNKNOWN при отсутствии mapping.

## 17. LATER

- Product ↔ OKPD2 mapping, если доказана ценность;
- versioned external mappings;
- richer material/form taxonomy;
- Industry rules;
- live source classification adapters;
- AI-assisted normalization с обязательной validation boundary.

Эти решения не являются prerequisites first TOP-10.
