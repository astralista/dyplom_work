# Дипломная работа "API Сервис заказа товаров для розничных сетей"

## для работы необходимо:
склонировать репозиторий:
```
git clone https://github.com/astralista/dyplom_work.git
```

в корневом каталоге создать файл **.env** по образцу:
```
# данные для создания БД PostgreSQL:
PG_USER=user1
PG_PASSWORD=12345678
PG_DB=dyplom_db1
PG_HOST=db

# данные вашей почты(с нее будут отправляться письма на авторизацию новых пользователей):
EMAIL_HOST=smtp.mail.ru
EMAIL_HOST_USER = test4dyplom@mail.ru
#это пароль "приложения" почты, настраиваемый пароль почтовика, его надо создать отдельно:
EMAIL_HOST_PASSWORD=7h4XpnHincD05WyWKP

# данные суперпользователя:
DJANGO_SUPERUSER_USERNAME=admin
DJANGO_SUPERUSER_EMAIL=admin@example.com
DJANGO_SUPERUSER_PASSWORD=P4tgdb21~1%^&
```
Запустить Docker  
Собрать и запустить Docker контейнер:
```
docker-compose up --build
```
После сборки и запуска сервис будет доступен по адресу:  
[https://0.0.0.0:8000/](https://0.0.0.0:8000/)

Данные для входа в админ панель (суперпользователь) и для доступа к БД вы ранее указали в **.env** файле

Команды для работы с API прописаны на сервисе POSTMAN:\
[POSTMAN - ссылка](https://www.postman.com/lively-capsule-851865/workspace/dyplom-api-service/overview)


Порядок работы с API через POSTMAN:

1. Регистрация пользователя (тип: Магазин):
- POST Partner / user (type: shop) register

    / В поле Body надо вписать данные по образцу (почта должна быть настоящая)
    / после отправки запроса, пройти в почту, и перейти по ссылке в письме для подтверждения (и активации) учетной записи

2. Загрузка прайс-листа в БД
- POST Partner / Shop Upload Price

    / в поле Authorization ввести почту и пароль из данных прошлого пункта
    / в поле Body выбрать key:file, value: выбрать файл прайс листа (лежит тут:/supplier/data/ формат json)

3. Регистрация пользователя (тип: Покупатель):
- POST user/ /user/register (type: buyer)

    / В поле Body надо вписать данные по образцу (почта должна быть настоящая)
    / после отправки запроса, пройти в почту, и перейти по ссылке в письме для подтверждения (и активации) учетной записи

4. Смотрим список товаров:
- GET Product info / Product info

    / в поле Params проставляем ключ магазина категории
    / записанные в БД магазины и категории можно посмотреть через GET Category Info и GET Shop list

5. "Складываем" нужные товары в корзину:
- PUT basket / PUT basket

    / в поле Authorization указываем почту и пароль пользователя (покупателя)
    / в поле Body указываем json запрос по образцу
    / в поле Headers нужно указать key: Content-type, value:application/json

6. Получаем данные корзины (id)
- GET basket / GET basket

    / в поле Authorization указываем почту и пароль пользователя (покупателя)

7. Отправляем заказ на исполнение (покупаем):
- POST Order / POST order

    / в поле Authorization указываем почту и пароль пользователя (покупателя)
    / в поле Body указываем json запрос по образцу
    / в поле Headers нужно указать key: Content-type, value:application/json

8. Админ получает на почту письмо о новом заказе / Покупатель получает на почту письмо о заказе