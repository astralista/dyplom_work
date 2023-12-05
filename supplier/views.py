from distutils.util import strtobool

from django.conf import settings
from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.core.mail import send_mail
from django.db import IntegrityError
from django.db.models import F, Q, Sum
from django.db.models.query import Prefetch
from django.http import JsonResponse
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from django_rest_passwordreset.tokens import get_token_generator
from rest_framework import status, viewsets
from rest_framework.authtoken.models import Token
from rest_framework.generics import ListAPIView
from rest_framework.response import Response
from rest_framework.views import APIView
from ujson import loads as load_json
from yaml import Loader
from yaml import load as load_yaml

from customer.models import ConfirmEmailToken, Contact, User
from requests import get
from supplier.tasks import import_shop_data

from .models import (Category, Order, OrderItem, Parameter, Product,
                     ProductInfo, ProductParameter, Shop)
from .serializers import (CategorySerializer, ContactSerializer,
                          OrderItemSerializer, OrderSerializer,
                          ProductInfoSerializer, ShopSerializer,
                          UserSerializer)
from .signals import new_user_registered


class RegisterAccount(APIView):
    """
    Для регистрации покупателей
    """

    throttle_scope = "anon"

    def post(self, request, *args, **kwargs):
        required_fields = {
            "first_name",
            "last_name",
            "email",
            "password",
            "company",
            "position",
            "username",
        }
        # проверка пароля
        if required_fields.issubset(request.data):
            try:
                validate_password(request.data["password"])
            except Exception as password_error:
                error_array = [item for item in password_error]
                return JsonResponse(
                    {"Status": False, "Errors": {"password": error_array}}
                )
            # проверка имени
            user_serializer = UserSerializer(data=request.data)
            if user_serializer.is_valid():
                user = self.create_inactive_user(
                    user_serializer.data, request.data["password"]
                )
                self.send_confirmation_email(user)
                return JsonResponse(
                    {
                        "Status": True,
                        "Message": "Регистрация успешно завершена. Письмо с подтверждением отправлено",
                    }
                )
            else:
                return JsonResponse({"Status": False, "Errors": user_serializer.errors})

    def create_inactive_user(self, data, password):
        user = User.objects.create(**data)
        user.set_password(password)
        user.is_active = False
        user.save()
        return user

    def send_confirmation_email(self, user):
        # Создаем токен для подтверждения email
        token_generator = get_token_generator()
        token = ConfirmEmailToken.objects.create(user=user)

        # Отправляем письмо с токеном по электронной почте
        subject = "Подтверждение регистрации"
        message = (
            f"Для подтверждения регистрации перейдите по ссылке: {settings.BASE_URL}/user/register"
            f"/confirm?token={token.key}&email={user.email}"
        )
        from_email = settings.DEFAULT_FROM_EMAIL
        to_email = user.email

        send_mail(subject, message, from_email, [to_email])


class ConfirmAccount(APIView):
    """
    Класс для подтверждения почтового адреса
    """

    throttle_scope = "anon"

    def get(self, request, *args, **kwargs):
        email = self.request.query_params.get("email")
        token = self.request.query_params.get("token")

        if email and token:
            user = User.objects.filter(email=email).first()
            if user:
                token_obj = ConfirmEmailToken.objects.filter(
                    user=user, key=token
                ).first()

                if token_obj:
                    user.is_active = True
                    user.save()
                    token_obj.delete()
                    return Response(
                        {"Status": True, "Message": "Пользователь успешно активирован"}
                    )
                else:
                    return Response(
                        {
                            "Status": False,
                            "Errors": "Неправильно указан токен подтверждения.",
                        },
                        status=status.HTTP_400_BAD_REQUEST,
                    )
            else:
                return Response(
                    {
                        "Status": False,
                        "Errors": "Пользователь с указанным email не найден",
                    },
                    status=status.HTTP_404_NOT_FOUND,
                )
        else:
            return Response(
                {"Status": False, "Errors": "Не указан email или токен"},
                status=status.HTTP_400_BAD_REQUEST,
            )


class LoginAccount(APIView):
    """
    Класс для авторизации пользователей
    """

    throttle_scope = "anon"

    def post(self, request, *args, **kwargs):
        if {"email", "password"}.issubset(request.data):
            user = authenticate(
                request,
                username=request.data["email"],
                password=request.data["password"],
            )

            if user is not None:
                if user.is_active:
                    token, _ = Token.objects.get_or_create(user=user)

                    return Response({"Status": True, "Token": token.key})

            return Response(
                {"Status": False, "Errors": "Не удалось авторизовать"},
                status=status.HTTP_403_FORBIDDEN,
            )

        return Response(
            {"Status": False, "Errors": "Не указаны все необходимые аргументы"},
            status=status.HTTP_400_BAD_REQUEST,
        )


class AccountDetails(APIView):
    """
    Класс для работы данными пользователя
    """

    throttle_scope = "user"

    # Возвращает все данные пользователя включая все контакты.
    def get(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return Response(
                {"Status": False, "Error": "Login required"},
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = UserSerializer(request.user)
        return Response(serializer.data)

    # Изменяем данные пользователя.
    def post(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return Response(
                {"Status": False, "Error": "Login required"},
                status=status.HTTP_403_FORBIDDEN,
            )

        # Если есть пароль, проверяем его и сохраняем.
        if "password" in request.data:
            try:
                validate_password(request.data["password"])
            except Exception as password_error:
                return Response(
                    {"Status": False, "Errors": {"password": password_error}}
                )
            else:
                request.user.set_password(request.data["password"])

        # Проверяем остальные данные
        user_serializer = UserSerializer(request.user, data=request.data, partial=True)
        if user_serializer.is_valid():
            user_serializer.save()
            return Response({"Status": True}, status=status.HTTP_201_CREATED)
        else:
            return Response(
                {"Status": False, "Errors": user_serializer.errors},
                status=status.HTTP_400_BAD_REQUEST,
            )


class CategoryView(viewsets.ModelViewSet):
    """
    Класс для просмотра категорий
    """

    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    ordering = ("name",)


class ShopView(viewsets.ModelViewSet):
    """
    Класс для просмотра списка магазинов
    """

    queryset = Shop.objects.all()
    serializer_class = ShopSerializer
    ordering = ("name",)


class ProductInfoView(viewsets.ReadOnlyModelViewSet):
    """
    Класс для поиска товаров
    """

    throttle_scope = "anon"
    serializer_class = ProductInfoSerializer
    ordering = ("product",)

    def get_queryset(self):
        query = Q(shop__state=True)
        shop_id = self.request.query_params.get("shop_id")
        category_id = self.request.query_params.get("category_id")

        if shop_id:
            query = query & Q(shop_id=shop_id)

        if category_id:
            query = query & Q(product__category_id=category_id)

        # фильтруем и отбрасываем дуликаты
        queryset = (
            ProductInfo.objects.filter(query)
            .select_related("shop", "product__category")
            .prefetch_related("product_parameters__parameter")
            .distinct()
        )

        return queryset


class BasketView(APIView):
    """
    Класс для работы с корзиной пользователя
    """

    throttle_scope = "user"

    # получить корзину
    def get(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return JsonResponse(
                {"Status": False, "Error": "Log in required"},
                status=status.HTTP_403_FORBIDDEN,
            )
        basket = (
            Order.objects.filter(user_id=request.user.id, status="basket")
            .prefetch_related(
                "ordered_items__product_info__product__category",
                "ordered_items__product_info__product_parameters__parameter",
            )
            .annotate(
                total_sum=Sum(
                    F("ordered_items__quantity")
                    * F("ordered_items__product_info__price")
                )
            )
            .distinct()
        )

        serializer = OrderSerializer(basket, many=True)
        return Response(serializer.data)

    # редактировать корзину
    def post(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return JsonResponse(
                {"Status": False, "Error": "Log in required"},
                status=status.HTTP_403_FORBIDDEN,
            )

        items_sting = request.data.get("items")
        if items_sting:
            try:
                items_dict = load_json(items_sting)
            except ValueError:
                JsonResponse({"Status": False, "Errors": "Неверный формат запроса"})
            else:
                basket, _ = Order.objects.get_or_create(
                    user_id=request.user.id, state="basket"
                )
                objects_created = 0
                for order_item in items_dict:
                    order_item.update({"order": basket.id})
                    serializer = OrderItemSerializer(data=order_item)
                    if serializer.is_valid():
                        try:
                            serializer.save()
                        except IntegrityError as error:
                            return JsonResponse({"Status": False, "Errors": str(error)})
                        else:
                            objects_created += 1
                    else:
                        JsonResponse({"Status": False, "Errors": serializer.errors})

                return JsonResponse(
                    {"Status": True, "Создано объектов": objects_created}
                )
        return JsonResponse(
            {"Status": False, "Errors": "Не указаны все необходимые аргументы"}
        )

    # удалить товары из корзины
    def delete(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return JsonResponse(
                {"Status": False, "Error": "Log in required"},
                status=status.HTTP_403_FORBIDDEN,
            )

        items_sting = request.data.get("items")
        if items_sting:
            items_list = items_sting.split(",")
            basket, _ = Order.objects.get_or_create(
                user_id=request.user.id, state="basket"
            )
            query = Q()
            objects_deleted = False
            for order_item_id in items_list:
                if order_item_id.isdigit():
                    query = query | Q(order_id=basket.id, id=order_item_id)
                    objects_deleted = True

            if objects_deleted:
                deleted_count = OrderItem.objects.filter(query).delete()[0]
                return JsonResponse({"Status": True, "Удалено объектов": deleted_count})
        return JsonResponse(
            {"Status": False, "Errors": "Не указаны все необходимые аргументы"}
        )

    # добавить позиции в корзину
    def put(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return JsonResponse(
                {"Status": False, "Error": "Log in required"},
                status=status.HTTP_403_FORBIDDEN,
            )

        items_sting = request.data.get("items")
        if items_sting:
            try:
                items_dict = load_json(items_sting)
            except ValueError:
                JsonResponse({"Status": False, "Errors": "Неверный формат запроса"})
            else:
                basket, _ = Order.objects.get_or_create(
                    user_id=request.user.id, state="basket"
                )
                objects_updated = 0
                for order_item in items_dict:
                    if (
                        type(order_item["id"]) == int
                        and type(order_item["quantity"]) == int
                    ):
                        objects_updated += OrderItem.objects.filter(
                            order_id=basket.id, id=order_item["id"]
                        ).update(quantity=order_item["quantity"])

                return JsonResponse(
                    {"Status": True, "Обновлено объектов": objects_updated}
                )
        return JsonResponse(
            {"Status": False, "Errors": "Не указаны все необходимые аргументы"}
        )


class OrderView(APIView):
    """
    Класс для получения и размешения заказов пользователями
    """

    throttle_scope = "user"

    def get(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return Response(
                {"Status": False, "Error": "Log in required"},
                status=status.HTTP_403_FORBIDDEN,
            )

        order = (
            Order.objects.filter(user_id=request.user.id)
            .exclude(status="basket")
            .select_related("contact")
            .prefetch_related("ordered_items")
            .annotate(
                total_quantity=Sum("ordered_items__quantity"),
                total_sum=Sum("ordered_items__total_amount"),
            )
            .distinct()
        )

        serializer = OrderSerializer(order, many=True)
        return Response(serializer.data)

    # Размещаем заказ из корзины и посылаем письмо об изменении статуса заказа.
    def post(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return Response(
                {"Status": False, "Error": "Log in required"},
                status=status.HTTP_403_FORBIDDEN,
            )

        if request.data["id"].isdigit():
            try:
                is_updated = Order.objects.filter(
                    id=request.data["id"], user_id=request.user.id
                ).update(contact_id=request.data["contact"], status="new")
            except IntegrityError as error:
                return Response(
                    {"Status": False, "Errors": "Неправильно указаны аргументы"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            else:
                if is_updated:
                    request.user.email_user(
                        f"Обновление статуса заказа",
                        "Заказ сформирован",
                        from_email=settings.EMAIL_HOST_USER,
                    )
                    return Response({"Status": True})

        return Response(
            {"Status": False, "Errors": "Не указаны все необходимые аргументы"},
            status=status.HTTP_400_BAD_REQUEST,
        )


class ContactView(APIView):
    """
    Класс для работы с контактами покупателей
    """

    throttle_scope = "user"

    # получить мои контакты
    def get(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return JsonResponse(
                {"Status": False, "Error": "Log in required"},
                status=status.HTTP_403_FORBIDDEN,
            )
        contact = Contact.objects.filter(user_id=request.user.id)
        serializer = ContactSerializer(contact, many=True)
        return Response(serializer.data)

    # добавить новый контакт
    def post(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return JsonResponse(
                {"Status": False, "Error": "Log in required"},
                status=status.HTTP_403_FORBIDDEN,
            )

        if {"city", "phone"}.issubset(request.data):
            request.data._mutable = True
            request.data.update({"user": request.user.id})
            serializer = ContactSerializer(data=request.data)

            if serializer.is_valid():
                serializer.save()
                return JsonResponse({"Status": True})
            else:
                JsonResponse({"Status": False, "Errors": serializer.errors})

        return JsonResponse(
            {"Status": False, "Errors": "Не указаны все необходимые аргументы"}
        )

    # удалить контакт
    def delete(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return JsonResponse(
                {"Status": False, "Error": "Log in required"},
                status=status.HTTP_403_FORBIDDEN,
            )

        items_sting = request.data.get("items")
        if items_sting:
            items_list = items_sting.split(",")
            query = Q()
            objects_deleted = False
            for contact_id in items_list:
                if contact_id.isdigit():
                    query = query | Q(user_id=request.user.id, id=contact_id)
                    objects_deleted = True

            if objects_deleted:
                deleted_count = Contact.objects.filter(query).delete()[0]
                return JsonResponse({"Status": True, "Удалено объектов": deleted_count})
        return JsonResponse(
            {"Status": False, "Errors": "Не указаны все необходимые аргументы"}
        )

    # редактировать контакт
    def put(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return JsonResponse(
                {"Status": False, "Error": "Log in required"},
                status=status.HTTP_403_FORBIDDEN,
            )

        if "id" in request.data:
            if request.data["id"].isdigit():
                contact = Contact.objects.filter(
                    id=request.data["id"], user_id=request.user.id
                ).first()
                print(contact)
                if contact:
                    serializer = ContactSerializer(
                        contact, data=request.data, partial=True
                    )
                    if serializer.is_valid():
                        serializer.save()
                        return JsonResponse({"Status": True})
                    else:
                        JsonResponse({"Status": False, "Errors": serializer.errors})

        return JsonResponse(
            {"Status": False, "Errors": "Не указаны все необходимые аргументы"}
        )


class PartnerOrders(APIView):
    """
    Класс для получения заказов поставщиками
    """

    throttle_scope = "user"

    def get(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return Response(
                {"Status": False, "Error": "Login required"},
                status=status.HTTP_403_FORBIDDEN,
            )

        if request.user.type != "shop":
            return Response(
                {"Status": False, "Error": "Только для магазинов"},
                status=status.HTTP_403_FORBIDDEN,
            )

        pr = Prefetch(
            "ordered_items",
            queryset=OrderItem.objects.filter(shop__user_id=request.user.id),
        )
        order = (
            Order.objects.filter(ordered_items__shop__user_id=request.user.id)
            .exclude(status="basket")
            .prefetch_related(pr)
            .select_related("contact")
            .annotate(
                total_sum=Sum("ordered_items__total_amount"),
                total_quantity=Sum("ordered_items__quantity"),
            )
        )

        serializer = OrderSerializer(order, many=True)
        return Response(serializer.data)


class PartnerState(APIView):
    """
    Класс для работы со статусом поставщика
    """

    throttle_scope = "user"

    # Получить текущий статус получения заказов у магазина
    def get(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return Response(
                {"Status": False, "Error": "Login required"},
                status=status.HTTP_403_FORBIDDEN,
            )

        if request.user.type != "shop":
            return Response(
                {"Status": False, "Error": "Только для магазинов"},
                status=status.HTTP_403_FORBIDDEN,
            )

        shop = request.user.shop
        serializer = ShopSerializer(shop)
        return Response(serializer.data)

    # Изменить текущий статус получения заказов у магазина
    def post(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return Response(
                {"Status": False, "Error": "Log in required"},
                status=status.HTTP_403_FORBIDDEN,
            )

        if request.user.type != "shop":
            return Response(
                {"Status": False, "Error": "Только для магазинов"},
                status=status.HTTP_403_FORBIDDEN,
            )

        state = request.data.get("state")
        if state:
            try:
                Shop.objects.filter(user_id=request.user.id).update(
                    state=strtobool(state)
                )
                return Response({"Status": True})
            except ValueError as error:
                return Response(
                    {"Status": False, "Errors": str(error)},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        return Response(
            {"Status": False, "Errors": "Не указан аргумент state."},
            status=status.HTTP_400_BAD_REQUEST,
        )


class PartnerUpdate(APIView):
    """
    Класс для обновления прайса от поставщика
    """

    throttle_scope = "partner"

    def post(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return Response(
                {"Status": False, "Error": "Log in required"},
                status=status.HTTP_403_FORBIDDEN,
            )

        if request.user.type != "shop":
            return Response(
                {"Status": False, "Error": "Только для магазинов"},
                status=status.HTTP_403_FORBIDDEN,
            )

        file = request.FILES.get("file")
        if file:
            user_id = request.user.id
            try:
                import_shop_data(file, user_id)
                return Response({"Status": True, "Message": "Данные успешно загружены"})
            except Exception as e:
                return Response(
                    {"Status": False, "Error": f"Произошла ошибка: {str(e)}"},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )

        return Response(
            {"Status": False, "Errors": "Не указаны все необходимые аргументы"},
            status=status.HTTP_400_BAD_REQUEST,
        )

