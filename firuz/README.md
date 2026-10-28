# Часть Фируза — участник 3

В этой папке находятся пользователи и роли. Стиль логики взят из
`D:\softclub\django\exam3`: функции для авторизации, Django Forms,
подтверждение email, выход через POST и CSRF.

Приложения коллег и общие настройки не изменены. В проекте уже подключён
`firuz.urls` под префиксом `/firuz/`, поэтому адрес регистрации:
`/firuz/accounts/register/`. Остальные адреса находятся в `urls.py`.

## Запуск из корня репозитория в PowerShell

```powershell
.\firuz\.myvenv\Scripts\Activate.ps1
python manage.py migrate --settings=firuz.dev_settings
python manage.py runserver --settings=firuz.dev_settings
```

Откройте http://127.0.0.1:8000/firuz/accounts/register/.
Письмо подтверждения выводится в терминал согласно общим настройкам проекта.
Откройте ссылку из письма и нажмите кнопку подтверждения, затем войдите.

Для создания окружения заново:

```powershell
py -3.14 -m venv firuz\.myvenv
.\firuz\.myvenv\Scripts\python.exe -m pip install -r requirements.txt
```

Если PowerShell запрещает активацию, используйте напрямую
`.\firuz\.myvenv\Scripts\python.exe` вместо `python`.

`dev_settings.py` и `dev_urls.py` нужны для проверки своей части, пока
`simple.urls` и `smuhammad.urls` отсутствуют. Они используют отдельную локальную
SQLite-базу `firuz/db.sqlite3`. После подключения URL коллег запускайте общий
проект обычными командами `python manage.py migrate` и `python manage.py runserver`.
Окружение и локальная база исключены из Git через `firuz/.gitignore`.

## Роли

При регистрации доступны `tenant` и `owner`. Роль хранится в `Profile`,
соответствующая группа Django обновляется при сохранении профиля.
Группа `moderator` имеет право `firuz.moderate_property`.
Модератора назначает администратор через редактирование `Profile` в Django Admin.
Из личного кабинета изменить роль или чужой профиль нельзя.

```powershell
python manage.py createsuperuser --settings=firuz.dev_settings
```

Публичная страница показывает имя и описание активного владельца.
Email и телефон доступны только в собственном кабинете.

## Что согласовать с командой

TODO в `views.py`: модель и приложение `Property`, поле владельца, статусы,
переходы модерации, условия создания отзывов и ссылка на детали объявления.
До согласования отзывы, жалобы и обработчики модерации не реализованы.
Модель недвижимости из чужого приложения не дублируется.

Общий `base.html` ещё не создан. Пока шаблоны наследуются от `firuz/base.html`;
после появления общего шаблона нужно согласовать его блоки с командой.
Деление на accounts/reviews/moderation показано в URL и шаблонах внутри `firuz`,
чтобы соблюдать ограничение на изменения только этой папки.

## Проверка

```powershell
python manage.py check --settings=firuz.dev_settings
python manage.py test firuz --settings=firuz.dev_settings
```

Рабочая ветка: `codex/firuz-accounts`. Git remote и автор коммитов сохранены.
