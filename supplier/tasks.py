import yaml
from django.conf.global_settings import EMAIL_HOST_USER
from django.core.mail.message import EmailMultiAlternatives
from django.core.exceptions import ValidationError
from django.core.files.storage import default_storage

from retail_purchase_service.celery import app

from .models import Category, Parameter, Product, ProductParameter, Shop


@app.task()
def send_email(message: str, email: str, *args, **kwargs) -> str:
    title = "Title"
    email_list = list()
    email_list.append(email)
    try:
        msg = EmailMultiAlternatives(
            subject=title, body=message, from_email=EMAIL_HOST_USER, to=email_list
        )
        msg.send()
        return f"Title: {msg.subject}, Message:{msg.body}"
    except Exception as e:
        raise e


def open_file(shop):
    file_path = shop.get_file()

    # Проверяем, существует ли файл
    if not default_storage.exists(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")

    try:
        # Пытаемся прочитать и загрузить данные из файла
        with default_storage.open(file_path, "r") as f:
            data = yaml.safe_load(f)
            if data is None:
                raise ValueError("File is empty or contains invalid YAML")
    except (FileNotFoundError, ValueError, ValidationError) as e:
        raise e  # Пробрасываем исключение дальше

    return data


@app.task()
def import_shop_data(data, user_id):
    try:
        file = open_file(data)
        shop_data = file.get("shop", {})
        categories_data = file.get("categories", [])
        goods_data = file.get("goods", [])

        shop, _ = Shop.objects.get_or_create(
            user_id=user_id, defaults={"name": shop_data.get("name", "")}
        )

        load_cat = [
            Category(id=category.get("id", ""), name=category.get("name", ""))
            for category in categories_data
        ]
        Category.objects.bulk_create(load_cat)

        Product.objects.filter(shop_id=shop.id).delete()

        load_prod = []
        product_id = {}
        load_pp = []
        for item in goods_data:
            load_prod.append(
                Product(
                    name=item.get("name", ""),
                    category_id=item.get("category", ""),
                    model=item.get("model", ""),
                    external_id=item.get("id", ""),
                    shop_id=shop.id,
                    quantity=item.get("quantity", 0),
                    price=item.get("price", 0),
                    price_rrc=item.get("price_rrc", 0),
                )
            )
            product_id[item.get("id", "")] = {}

            for name, value in item.get("parameters", {}).items():
                parameter, _ = Parameter.objects.get_or_create(name=name)
                product_id[item.get("id", "")].update({parameter.id: value})
                load_pp.append(
                    ProductParameter(
                        product_id=product_id[item.get("id", "")][parameter.id],
                        parameter_id=parameter.id,
                        value=value,
                    )
                )

        Product.objects.bulk_create(load_prod)
        ProductParameter.objects.bulk_create(load_pp)

        return {"Status": True, "Message": "Данные успешно обновлены"}
    except Exception as e:
        return {"Status": False, "Error": f"Произошла ошибка: {str(e)}"}

