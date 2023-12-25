import yaml
import json
from django.conf.global_settings import EMAIL_HOST_USER
from django.core.mail.message import EmailMultiAlternatives
from django.core.exceptions import ValidationError
from django.core.files.storage import default_storage
from django.db import transaction
from django.db.utils import IntegrityError
from typing import Union

from retail_purchase_service.celery import app

from .models import Category, Parameter, Product, ProductParameter, Shop, ProductInfo
import logging

logger = logging.getLogger(__name__)


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


def open_file(file) -> Union[str, dict]:
    try:
        # Чтение данных из InMemoryUploadedFile
        file_data = file.read()
        # Преобразование данных в строку
        file_str = file_data.decode('utf-8')
        # Загрузка JSON
        data = json.loads(file_str)
        return data
    except Exception as e:
        print(f"Error opening file: {e}")
        raise


@app.task
def import_shop_data(file, user_id):
    try:
        file_content = open_file(file)
        if isinstance(file_content, str):
            data = json.loads(file_content)
        else:
            data = file_content

        goods_data = data.get("goods", [])

        if not isinstance(goods_data, list):
            raise ValueError("Invalid 'goods' data format")

        shop_name = data.get("shop", "")

        shop_data = data.get("shop_data", {})
        categories_data = shop_data.get("categories", [])

        with transaction.atomic():
            shop, _ = Shop.objects.get_or_create(
                user_id=user_id, defaults={"name": shop_name}
            )

            # Добавим категории
            categories_to_create = [
                Category(name=category_data.get("name", ""))
                for category_data in categories_data
            ]

            try:
                with transaction.atomic():
                    Category.objects.bulk_create(categories_to_create)
                    print(f"Categories created successfully.")
            except Exception as e:
                print(f"Error creating categories: {e}")
                for category in categories_to_create:
                    try:
                        existing_category = Category.objects.get(name=category.name)
                        print(f"Category {category.name} already exists with ID {existing_category.id}")
                    except Category.DoesNotExist:
                        print(f"Category {category.name} does not exist.")

            # Очистим продукты для данного магазина
            Product.objects.filter(shop_id=shop.id).delete()

            load_prod = []
            for item in goods_data:
                if isinstance(item, dict):
                    category_data = item.get("category", "")
                    if isinstance(category_data, dict):
                        category_id = category_data.get("id", "")
                    else:
                        try:
                            category = Category.objects.get(name=category_data)
                            category_id = category.id
                        except Category.DoesNotExist:
                            print(f"Category {category_data} does not exist for shop {shop_name}.")
                            continue

                    try:
                        product, created = Product.objects.get_or_create(
                            external_id=item.get("id", ""),
                            defaults={
                                "name": item.get("name", ""),
                                "category_id": category_id,
                                "shop_id": shop.id,
                            },
                        )
                        if not created:
                            print(f"Product {item.get('name', '')} already exists")

                        # Добавим информацию о продукте
                        product_info, _ = ProductInfo.objects.get_or_create(
                            model=item.get("model", ""),
                            quantity=item.get("quantity", 0),
                            price=item.get("price", 0),
                            price_rrc=item.get("price_rrc", 0),
                            product=product,
                            shop=shop,
                        )

                        # Добавим параметры продукта
                        parameters = item.get("parameters", [])
                        for param in parameters:
                            parameter_name = param.get("name", "")
                            parameter_value = param.get("value", "")
                            parameter, _ = Parameter.objects.get_or_create(
                                name=parameter_name
                            )

                            ProductParameter.objects.get_or_create(
                                product_info=product_info,
                                parameter=parameter,
                                value=parameter_value,
                            )

                    except IntegrityError as e:
                        print(f"Error inserting product {item.get('name', '')}: {e}")

        return {"Status": True, "Message": "Данные успешно обновлены"}
    except Exception as e:
        logger.error(f"Error during data import: {e}")
        raise
