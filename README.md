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
[https://0.0.0.0:8000/](0.0.0.0:8000/)

Данные для входа в админ панель (суперпользователь) и для доступа к БД вы ранее указали в **.env** файле

Команды для работы с API прописаны на сервисе POSTMAN:
[POSTMAN - ссылка](https://www.postman.com/lively-capsule-851865/workspace/dyplom-api-service/overview)