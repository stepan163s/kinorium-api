# Kinorium API

Python-клиент для работы с API Кинориума (Kinorium). Поддерживает синхронный и асинхронный режимы работы, автоматическую подпись запросов, нормализацию ключей ответа в `snake_case` и объектно-ориентированную работу через Python Dataclass-модели.

## Ключевые особенности

* **Два режима работы**: Синхронный (`KinoriumClient`) и асинхронный (`KinoriumClientAsync`) клиенты с идентичным интерфейсом.
* **Автоматическая подпись запросов (Request Signing)**: Библиотека сама считает MD5-хеш параметров и подставляет секретный `key` для прохождения валидации на сервере.
* **Умная нормализация ключей (JSON Key Normalization)**: Все ключи API (в форматах `camelCase` или `kebab-case`) на лету переводятся в `snake_case` при парсинге, а также разрешаются конфликты с ключевыми словами Python (например, `id` -> `id_`, `type` -> `type_`, `from` -> `from_`).
* **Легковесные доменные модели**: Использование встроенных Python `dataclasses` вместо тяжелого Pydantic. Модели поддерживают рекурсивную десериализацию вложенных объектов и фильтрацию новых неизвестных полей API.
* **«Активные» модели (Active Models)**: Объекты домена хранят ссылку на клиент, позволяя совершать действия прямо из экземпляров моделей (например, `user.get_lists()` или `user_list.get_objects()`).
* **Кастомная иерархия исключений**: Все ошибки HTTP (400, 401, 403, 404), сетевые сбои и ошибки подписи ключей маппятся на понятные Python-исключения.

---

## Установка

Установка библиотеки напрямую из репозитория GitHub:

```bash
python3 -m pip install git+https://github.com/stepan163s/kinorium-api.git
```

Оба клиента устанавливаются вместе с зависимостями `requests` и `aiohttp`.

Проверить установку:

```bash
python3 -c "from kinorium import KinoriumClient, KinoriumClientAsync; assert callable(KinoriumClient) and callable(KinoriumClientAsync); print('Kinorium установлен')"
```

Для установки из локальной копии репозитория запустите `python3 -m pip install .`
из его корня — папки с `pyproject.toml`, `setup.cfg` и `setup.py`.

---

## Аутентификация

Для авторизованных запросов используется токен `auth` в cookie. Запустите
`python3 get_session.py`: скрипт запросит почту и пароль, получит токен и
выведет его вместе с примером инициализации клиента. Пароль вводится скрыто.

Для повторных запусков можно задать переменные окружения `KINORIUM_EMAIL` и
`KINORIUM_PASSWORD` либо создать рядом со скриптом `get_session.local.json`:

```json
{"email": "your_email@example.com", "password": "your_password"}
```

Этот локальный файл исключён из Git и исходного дистрибутива. Переменные
окружения имеют приоритет. Данные для входа не нужно записывать в исходный код.

---

## Быстрый старт

### Синхронный клиент (`KinoriumClient`)

```python
from kinorium import KinoriumClient
from kinorium.models import User

# Инициализация клиента с полученным токеном auth
client = KinoriumClient(auth="ВАШ_ПОСТОЯННЫЙ_ТОКЕН_AUTH")

# 1. Получение информации о пользователе (модель User)
user_data = client.get_user_info()
user = User.de_json(user_data, client=client)
print(f"Пользователь: {user.name} (ID: {user.id_})")

# 2. Вызов активного метода модели для получения списков пользователя
# (возвращает сырые данные списков)
lists_data = user.get_lists()
print(lists_data)
```

### Асинхронный клиент (`KinoriumClientAsync`)

Асинхронный клиент генерируется автоматически из синхронного кода, предоставляя абсолютно идентичные сигнатуры методов.

```python
import asyncio
from kinorium import KinoriumClientAsync
from kinorium.models import User

async def main():
    # Инициализация асинхронного клиента
    client = KinoriumClientAsync(auth="ВАШ_ПОСТОЯННЫЙ_ТОКЕН_AUTH")
    
    try:
        # 1. Получение информации о пользователе
        user_data = await client.get_user_info()
        user = User.de_json(user_data, client=client)
        print(f"Асинхронный пользователь: {user.name} (ID: {user.id_})")
        
        # 2. Получение списков пользователя через активный метод
        lists_data = await user.get_lists()
        print(lists_data)
        
    finally:
        # Важно закрывать асинхронную сессию клиента
        await client.close()

asyncio.run(main())
```

---

## Произвольные запросы к API (`request`)

Библиотека предоставляет публичный шлюз запросов `request(http_method, api_method, params=None, data=None)`. Так как все параметры подписываются динамически перед отправкой, вы можете вызывать любые конечные точки Кинориума:

```python
# Получить данные фильма по его ID (API метод getMovie)
movie_data = client.request("GET", "getMovie", params={"movie_id": 447299})
print(movie_data)

# Установить статус «буду смотреть»
client.request("POST", "setMovieStatus", data={"movie_id": 447299, "status": "future"})

# Удалить текущую отметку
client.request("POST", "removeMovieStatus", data={"movie_id": 447299, "type": "status"})
```

У POST-запросов параметры из `data` добавляются в подписанную строку запроса
и отправляются как поля формы. Почта и пароль метода `userAuth` передаются
только в теле формы. При разных значениях одного параметра в `params` и `data`
библиотека выдаёт `InvalidOptionError` до отправки запроса.

Доступны сокращённые методы с теми же операциями:

```python
movie_data = client.get_movie(447299)
client.set_movie_status(447299, "future")
client.remove_movie_status(447299)
```

Для асинхронного клиента используйте `await`. Значения статуса:
`done`, `future`, `never`. `set_movie_status()` отклоняет другие значения
с `InvalidOptionError` до отправки запроса. Сервер отвергает `now` с кодом 403.

Значения в подписанной строке и форме имеют одинаковое строковое представление:
`None` становится пустой строкой, остальные значения — результатом `str()`.
Если серверный параметр требует JSON или CSV, передайте явно подготовленную строку.
Для GET и обычного DELETE используйте `params`; непустой `data` у них вызывает
`InvalidOptionError`, чтобы параметры не терялись при отправке.

Сервер отклоняет HTTP DELETE для `removeMovieStatus`. Вызов
`request("DELETE", "removeMovieStatus", params={"movie_id": 447299})`
библиотека преобразует в POST и добавляет `type="status"`, если тип не указан.
Для остальных серверных методов DELETE отправляется без преобразования.

---

## Доменные модели данных

`de_json()` принимает как объект из `response["data"]`, так и полный ответ
с полями `result_code` и `data`. `User` понимает поля API `user_id` и `image`,
`Movie` — `name` и `genre_list`. ID и год преобразуются в числа, жанры —
в список названий. Вложенные модели и списки моделей также преобразуются.

### `User`
Представляет пользователя Кинориума.
* **Поля**:
  * `id_`: ID пользователя.
  * `name`: Имя/Никнейм.
  * `avatar`: URL аватара.
* **Активные методы**:
  * `user.get_lists()`: Возвращает метаданные списков пользователя (по умолчанию Watchlist, Избранное, кастомные списки).

### `Movie`
Представляет информацию о фильме/сериале.
* **Поля**:
  * `id_`: ID фильма в Кинориуме.
  * `title`: Название.
  * `genres`: Список жанров.
  * `year`: Год выпуска.

### `UserList`
Представляет пользовательский список фильмов.
* **Поля**:
  * `ulist_id`: ID списка.
  * `obj_type`: Тип содержимого.
  * `title`: Название списка.
  * `special`: Служебный флаг (например, `watchlist`).
* **Активные методы**:
  * `user_list.get_objects(page=1, perpage=50)`: Возвращает список объектов (фильмов), входящих в данный список.

---

## Иерархия исключений

Все сетевые ошибки и ответы API распределены по следующим классам исключений (`kinorium.exceptions`):

* `ApiError` — Базовое исключение библиотеки.
* `KinoriumError` — Совместимое имя `ApiError`, перехватывает все ошибки библиотеки.
* `NetworkError` — Ошибка соединения или необработанный отдельно HTTP-статус (включая 405 и 429).
  * `TimedOutError` — Запрос превысил время ожидания.
* `UnauthorizedError` — Неверный токен авторизации (HTTP 401/403).
* `BadRequestError` — Неверные параметры запроса (HTTP 400).
* `NotFoundError` — Ресурс не найден (HTTP 404).
* `InvalidKeyError` — Ошибка подписи запроса (`{"key": false}`).
* `KinoriumAPIError` — Ошибка API Кинориума с возвратом кода ошибки (например, неверный ID).
* `AuthenticationError` — Ошибка при входе по почте/паролю.

Пустое успешное тело ответа (в том числе HTTP 204) преобразуется в `{}`.
Некорректный JSON вызывает `KinoriumAPIError` у обоих клиентов.

## Проверки

```bash
python3 -m unittest discover -s tests -v
```

Автоматические тесты используют локальный HTTP-сервер и имитацию ответов;
они не обращаются к настоящему аккаунту и не меняют его данные.

Углублённая проверка настоящего API запускается отдельно:

```bash
python3 tests/live_api_audit.py --credentials-file get_session.local.json \
  --allow-write --movie-id 447299 --report /tmp/kinorium-live-audit.json
```

Вместо файла можно задать `KINORIUM_EMAIL` и `KINORIUM_PASSWORD` в окружении.
Без `--allow-write` проверяется только чтение. Для записи выберите фильм без
исходной отметки и заметки: проверка меняет статусы и оценки, удаляет их,
сверяет результат и восстанавливает проверенное состояние. JSON-отчёт сохраняет
исходные поля и результаты операций, без пароля и cookies.
