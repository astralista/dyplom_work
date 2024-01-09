import json
import logging
from typing import Union

from django.conf.global_settings import EMAIL_HOST_USER
from django.core.mail.message import EmailMultiAlternatives
from django.db import transaction
from django.db.utils import IntegrityError

from retail_purchase_service.celery import app
from supplier.models import (Category, Parameter, Product, ProductInfo,
                             ProductParameter, Shop)

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
        file_data = file.read()
        file_str = file_data.decode("utf-8")
        data = json.loads(file_str)
        return data
    except Exception as e:
        print(f"Error opening file: {e}")
        raise


@app.task
def import_shop_data(file, user_id, file_name):
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
        categories_data = data.get("categories", [])

        with transaction.atomic():
            shop, _ = Shop.objects.get_or_create(
                user_id=user_id, defaults={"name": shop_name, "file_name": file_name}
            )
            # Выведем информацию о магазине после его получения или создания
            print(f"Shop: {shop.name}, File Name: {shop.file_name}")

            # Выведем категории, связанные с магазином
            print(f"Categories linked to shop {shop.name}: {shop.categories.all()}")

            # Добавим вывод существующих категорий
            existing_categories = Category.objects.all()
            print("Existing categories:", existing_categories)
            for existing_category in existing_categories:
                print(f"Existing category: {existing_category.name}")

            # Добавим категории
            for category_data in categories_data:
                category_name = category_data.get("name", "")
                try:
                    category, created = Category.objects.get_or_create(
                        name=category_name
                    )
                    if created:
                        print(f"Category {category_name} created.")
                    else:
                        print(f"Category {category_name} already exists.")

                    shop.categories.add(category)

                    category.save()
                except Exception as e:
                    print(f"Error creating category {category_name}: {e}")
                    continue

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
                            print(
                                f"Category {category_data} does not exist for shop {shop_name}."
                            )
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
