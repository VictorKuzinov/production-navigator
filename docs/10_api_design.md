# API Design

## Содержание

1. [Назначение](#1-назначение)
2. [Общие принципы](#2-общие-принципы)
3. [Ресурсы первоначального API](#3-ресурсы-первоначального-api)
4. [Стандарт ответов с ошибкой](#4-стандарт-ответов-с-ошибкой)
5. [Enterprise API](#5-enterprise-api)
6. [Equipment API](#6-equipment-api)
7. [Product API](#7-product-api)
8. [Orders API](#8-orders-api)
9. [Matching API](#9-matching-api)
10. [Reference Data API](#10-reference-data-api)
11. [Следующие версии API](#11-следующие-версии-api)

## 1. Назначение

Документ описывает первоначальный API (MVP) «Производственного навигатора».

API обеспечивает минимальный сквозной сценарий:

1. создание производственного профиля;
2. добавление оборудования;
3. описание выпускаемой продукции;
4. создание заказа;
5. предварительную оценку соответствия предприятия требованиям заказа.

Расширенная аналитика, полный Rule Engine, формирование отчётов и интеграции с внешними площадками в первоначальный API не входят.

## 2. Общие принципы

- базовый путь API — `/api/v1`;
- формат запросов и ответов — JSON;
- имена полей используются в `snake_case`;
- даты передаются в формате ISO 8601 (`YYYY-MM-DD`);
- профиль заполняется поэтапно, без требования указать все сведения при первом запросе;
- значения классификаторов передаются только стабильными кодами PNC;
- API описывает публичный контракт и не раскрывает детали хранения данных;
- ошибки возвращаются в едином формате;
- бизнес-правила не включаются в текст ошибки: при необходимости их коды передаются отдельным полем.

## 3. Ресурсы первоначального API

| Ресурс                        | Назначение                          |
|-------------------------------|-------------------------------------|
| `/enterprises`                | Производственные профили            |
| `/enterprises/{id}/equipment` | Оборудование предприятия            |
| `/enterprises/{id}/products`  | Выпускаемая продукция               |
| `/orders`                     | Заказы для оценки                   |
| `/matching/evaluate`          | Предварительная оценка соответствия |
| `/reference-data/*`           | Получение системных справочников    |

Системные справочники входят в MVP и доступны через API только для чтения. Их создание, изменение и удаление относятся к административным функциям и в первоначальный API не входят.

Ресурсы для управления площадками, материалами предприятия, инфраструктурой и сертификатами, а также расширенный поиск и отчётность планируются для следующих версий API.

## 4. Стандарт ответов с ошибкой

### 4.1 Формат

Все ошибки возвращаются в единой структуре:

```json
{
  "error": {
    "code": "ENTERPRISE_NOT_FOUND",
    "message": "Производственный профиль не найден.",
    "details": {
      "enterprise_id": 999
    },
    "rule_codes": [],
    "request_id": "req_01JZ8M7K3T5A"
  }
}
```

| Поле         | Обязательное | Назначение                                                                |
|--------------|:------------:|---------------------------------------------------------------------------|
| `code`       |      Да      | Стабильный программный код ошибки                                         |
| `message`    |      Да      | Понятное пользователю описание на русском языке                           |
| `details`    |      Да      | Контекст ошибки; пустой объект, если деталей нет                          |
| `rule_codes` |      Да      | Коды нарушенных бизнес-правил; пустой массив, если правила не применялись |
| `request_id` |      Да      | Идентификатор запроса для поиска события в журнале                        |

Клиентская программа должна принимать решения по `code`, а не по тексту `message`.

### 4.2 Соответствие HTTP-статусов и кодов

| HTTP-статус                 | Когда используется                                               | Примеры кодов                                                                         |
|-----------------------------|------------------------------------------------------------------|---------------------------------------------------------------------------------------|
| `400 Bad Request`           | Невалидный JSON, отсутствует обязательное поле, неверный формат  | `INVALID_REQUEST`, `INVALID_FIELD_VALUE`                                              |
| `404 Not Found`             | Ресурс не найден                                                 | `ENTERPRISE_NOT_FOUND`, `EQUIPMENT_NOT_FOUND`, `PRODUCT_NOT_FOUND`, `ORDER_NOT_FOUND` |
| `409 Conflict`              | Запрос конфликтует с текущими данными                            | `ENTERPRISE_ALREADY_EXISTS`, `DUPLICATE_ORDER_NUMBER`                                 |
| `422 Unprocessable Entity`  | JSON корректен, но данные нарушают справочник или бизнес-правило | `REFERENCE_CODE_INVALID`, `BUSINESS_RULE_VIOLATION`                                   |
| `500 Internal Server Error` | Непредвиденная внутренняя ошибка                                 | `INTERNAL_ERROR`                                                                      |

### 4.3 Примеры

Неверное значение справочника:

```json
{
  "error": {
    "code": "REFERENCE_CODE_INVALID",
    "message": "Код типа оборудования отсутствует в классификаторе PNC.",
    "details": {
      "field": "equipment_type_code",
      "value": "TURNING"
    },
    "rule_codes": [],
    "request_id": "req_01JZ8M8D6Q1P"
  }
}
```

Нарушение бизнес-правила:

```json
{
  "error": {
    "code": "BUSINESS_RULE_VIOLATION",
    "message": "Для токарного оборудования необходимо указать максимальный диаметр обработки.",
    "details": {
      "field": "max_diameter"
    },
    "rule_codes": ["PNC-BR-EQ-001"],
    "request_id": "req_01JZ8M9B2K7R"
  }
}
```

## 5. Enterprise API

### 5.1 Создать производственный профиль

`POST /api/v1/enterprises`

Создаёт минимальный профиль. Наименование предприятия допускается не указывать при первом знакомстве с системой.

#### Request

```json
{
  "company_name": "ООО МеталлПром",
  "region_code": "PNC_REG_74",
  "company_size_code": "PNC_SIZE_SMALL"
}
```

#### Response — `201 Created`

```json
{
  "id": 1,
  "company_name": "ООО МеталлПром",
  "region_code": "PNC_REG_74",
  "company_size_code": "PNC_SIZE_SMALL",
  "profile_completion": 15,
  "next_step": "equipment"
}
```

Возможные ошибки: `400 INVALID_REQUEST`, `422 REFERENCE_CODE_INVALID`, `409 ENTERPRISE_ALREADY_EXISTS`.

### 5.2 Получить производственный профиль

`GET /api/v1/enterprises/{enterprise_id}`

#### Response — `200 OK`

```json
{
  "id": 1,
  "company_name": "ООО МеталлПром",
  "region_code": "PNC_REG_74",
  "company_size_code": "PNC_SIZE_SMALL",
  "profile_completion": 35,
  "next_step": "products"
}
```

#### Ошибка — `404 Not Found`

```json
{
  "error": {
    "code": "ENTERPRISE_NOT_FOUND",
    "message": "Производственный профиль не найден.",
    "details": {
      "enterprise_id": 999
    },
    "rule_codes": [],
    "request_id": "req_01JZ8MA5E4V2"
  }
}
```

### 5.3 Частично обновить профиль

`PATCH /api/v1/enterprises/{enterprise_id}`

В запрос включаются только изменяемые поля.

#### Request

```json
{
  "company_name": "АО МеталлПром-Холдинг",
  "company_size_code": "PNC_SIZE_MEDIUM"
}
```

#### Response — `200 OK`

```json
{
  "id": 1,
  "company_name": "АО МеталлПром-Холдинг",
  "region_code": "PNC_REG_74",
  "company_size_code": "PNC_SIZE_MEDIUM",
  "profile_completion": 35,
  "next_step": "products"
}
```

Возможные ошибки: `400 INVALID_REQUEST`, `404 ENTERPRISE_NOT_FOUND`, `409 ENTERPRISE_ALREADY_EXISTS`, `422 REFERENCE_CODE_INVALID`.

## 6. Equipment API

### 6.1 Добавить оборудование

`POST /api/v1/enterprises/{enterprise_id}/equipment`

Добавляет оборудование в производственный профиль. Привязка к площадке необязательна в MVP.

#### Request

```json
{
  "equipment_type_code": "PNC_EQUIP_TURNING",
  "cnc": true,
  "axes": 3,
  "quantity": 2,
  "max_diameter": 450.0
}
```

#### Response — `201 Created`

```json
{
  "id": 45,
  "enterprise_id": 1,
  "facility_id": null,
  "equipment_type_code": "PNC_EQUIP_TURNING",
  "cnc": true,
  "axes": 3,
  "quantity": 2,
  "max_diameter": 450.0,
  "working_zone_x": null,
  "working_zone_y": null,
  "working_zone_z": null
}
```

Возможные ошибки: `400 INVALID_REQUEST`, `404 ENTERPRISE_NOT_FOUND`, `422 REFERENCE_CODE_INVALID`, `422 BUSINESS_RULE_VIOLATION`.

### 6.2 Получить оборудование предприятия

`GET /api/v1/enterprises/{enterprise_id}/equipment`

Необязательные параметры запроса:

- `equipment_type_code` — фильтр по коду PNC;
- `cnc` — фильтр по наличию ЧПУ.

#### Response — `200 OK`

```json
{
  "items": [
    {
      "id": 45,
      "equipment_type_code": "PNC_EQUIP_TURNING",
      "cnc": true,
      "axes": 3,
      "quantity": 2,
      "max_diameter": 450.0
    }
  ],
  "total": 1
}
```

Пустой результат возвращается как `200 OK` с `items: []`. Ошибка `404 ENTERPRISE_NOT_FOUND` означает, что не найден сам профиль.

## 7. Product API

### 7.1 Добавить продукцию

`POST /api/v1/enterprises/{enterprise_id}/products`

Создаёт минимальное описание изделия, необходимое для заказа и сопоставления.

#### Request

```json
{
  "name": "Втулка фланцевая",
  "product_type_code": "PNC_PROD_PART",
  "description": "Изготовление по чертежу заказчика"
}
```

#### Response — `201 Created`

```json
{
  "id": 102,
  "enterprise_id": 1,
  "name": "Втулка фланцевая",
  "product_type_code": "PNC_PROD_PART",
  "description": "Изготовление по чертежу заказчика"
}
```

Возможные ошибки: `400 INVALID_REQUEST`, `404 ENTERPRISE_NOT_FOUND`, `422 REFERENCE_CODE_INVALID`.

## 8. Orders API

### 8.1 Создать заказ

`POST /api/v1/orders`

Создаёт заказ, требования которого будут сопоставлены с производственным профилем.

#### Request

```json
{
  "product_id": 102,
  "order_type_code": "PNC_ORD_CUSTOM",
  "industry_code": "PNC_IND_06",
  "order_number": "КОНТР-2026-004",
  "quantity": 10,
  "deadline": "2026-12-01"
}
```

#### Response — `201 Created`

```json
{
  "id": 87,
  "product_id": 102,
  "order_type_code": "PNC_ORD_CUSTOM",
  "industry_code": "PNC_IND_06",
  "order_number": "КОНТР-2026-004",
  "quantity": 10,
  "deadline": "2026-12-01"
}
```

Возможные ошибки: `400 INVALID_REQUEST`, `404 PRODUCT_NOT_FOUND`, `409 DUPLICATE_ORDER_NUMBER`, `422 REFERENCE_CODE_INVALID`.

Создание заказа не блокируется из-за несоответствия возможностям конкретного предприятия. Такие несоответствия выявляются методом Matching.

### 8.2 Получить заказ

`GET /api/v1/orders/{order_id}`

#### Response — `200 OK`

Ответ имеет ту же структуру, что и результат создания заказа.

Возможная ошибка: `404 ORDER_NOT_FOUND`.

## 9. Matching API

### 9.1 Выполнить предварительную оценку

`POST /api/v1/matching/evaluate`

Сопоставляет существующий производственный профиль с существующим заказом. Клиент передаёт только их идентификаторы — требования заказа повторно не дублируются.

#### Request

```json
{
  "enterprise_id": 1,
  "order_id": 87
}
```

#### Response — `200 OK`

```json
{
  "enterprise_id": 1,
  "order_id": 87,
  "is_executable": false,
  "score": 43,
  "summary": "Для уверенного выполнения заказа недостаточно данных о точности обработки."
}
```

`score` принимает значение от `0` до `100` и является предварительной оценкой, а не гарантией исполнения заказа.

Отрицательный результат сопоставления является обычным результатом (`200 OK`), а не ошибкой API.

Возможные ошибки: `404 ENTERPRISE_NOT_FOUND`, `404 ORDER_NOT_FOUND`, `422 PROFILE_INSUFFICIENT_DATA`.

Пример недостаточности данных:

```json
{
  "error": {
    "code": "PROFILE_INSUFFICIENT_DATA",
    "message": "Недостаточно данных для выполнения предварительной оценки.",
    "details": {
      "missing_sections": ["equipment", "materials"]
    },
    "rule_codes": [],
    "request_id": "req_01JZ8MB8S6N3"
  }
}
```

## 10. Reference Data API

### 10.1 Назначение

Reference Data API предоставляет клиентским приложениям доступ к системным справочникам и классификаторам PNC, необходимым для заполнения форм и проверки передаваемых кодов.

В MVP справочники доступны только для чтения:

- `GET` используется для получения списков значений;
- `POST`, `PATCH` и `DELETE` не поддерживаются;
- управление справочниками будет реализовано позднее в отдельном административном API;
- поле `code` является стабильным идентификатором и передаётся в операционные методы API.

### 10.2 Общий формат ответа

Все методы получения списков справочных значений возвращают объект с массивом `items` и общим количеством записей:

```json
{
  "items": [
    {
      "code": "PNC_EQUIP_TURNING",
      "name_ru": "Токарное оборудование",
      "description": "Токарные станки и токарные обрабатывающие центры."
    },
    {
      "code": "PNC_EQUIP_MILLING",
      "name_ru": "Фрезерное оборудование",
      "description": "Фрезерные станки и обрабатывающие центры."
    }
  ],
  "total": 2
}
```

Поля `description` и сведения о внешних классификаторах могут отсутствовать в кратком представлении справочника.

### 10.3 Доступные справочники

| Метод и ресурс                                     | Назначение                          |
|----------------------------------------------------|-------------------------------------|
| `GET /api/v1/reference-data/company-sizes`         | Размеры предприятий                 |
| `GET /api/v1/reference-data/production-types`      | Типы производства                   |
| `GET /api/v1/reference-data/equipment-types`       | Типы производственного оборудования |
| `GET /api/v1/reference-data/product-types`         | Типы продукции                      |
| `GET /api/v1/reference-data/technology-categories` | Категории технологий                |
| `GET /api/v1/reference-data/material-groups`       | Группы материалов                   |
| `GET /api/v1/reference-data/materials`             | Материалы и марки материалов        |
| `GET /api/v1/reference-data/industries`            | Отрасли                             |
| `GET /api/v1/reference-data/regions`               | Регионы                             |
| `GET /api/v1/reference-data/certificate-types`     | Типы сертификатов                   |
| `GET /api/v1/reference-data/transport-types`       | Типы транспорта                     |
| `GET /api/v1/reference-data/warehouse-categories`  | Категории складов                   |

### 10.4 Параметры запроса

Для справочников с большим количеством значений допускаются необязательные параметры:

- `q` — поиск по коду и наименованию;
- `parent_code` — фильтрация дочерних значений иерархического справочника;
- `limit` — максимальное количество возвращаемых записей;
- `offset` — смещение от начала списка.

Пример:

```http
GET /api/v1/reference-data/materials?q=сталь&limit=20&offset=0
```

### 10.5 Возможные ошибки

- `400 INVALID_REQUEST` — неверный формат параметров запроса;
- `500 INTERNAL_ERROR` — непредвиденная внутренняя ошибка.

Пустой результат возвращается как `200 OK` с `items: []` и `total: 0`.

## 11. Следующие версии API

После проверки MVP планируется добавить:

- управление площадками, материалами, инфраструктурой и сертификатами;
- пагинацию, сортировку и расширенную фильтрацию списков;
- детализированный отчёт Matching с объяснимыми выводами;
- историю оценок и рекомендации;
- экспорт профиля и отчётов в PDF;
- аутентификацию, авторизацию и аудит действий;
- интеграции с внешними источниками заказов.
