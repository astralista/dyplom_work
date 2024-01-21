from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from customer.models import ConfirmEmailToken

User = get_user_model()


class RegisterAccountTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.register_url = reverse("supplier:user-register")

    def test_register_account_valid_data(self):
        data = {
            "first_name": "John",
            "last_name": "Doe",
            "email": "john.doe@example.com",
            "password": "StrongPassword123",
            "company": "Example Company",
            "position": "Manager",
            "username": "john_doe",
        }

        response = self.client.post(self.register_url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response.json(),
            {
                "Status": True,
                "Message": "Регистрация успешно завершена. Письмо с подтверждением отправлено",
            },
        )

    def test_register_account_invalid_password(self):
        data = {
            "first_name": "John",
            "last_name": "Doe",
            "email": "john.doe@example.com",
            "password": "weakpassword",  # invalid password
            "company": "Example Company",
            "position": "Manager",
            "username": "john_doe",
        }

        response = self.client.post(self.register_url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response.json(),
            {
                "Status": True,
                "Message": "Регистрация успешно завершена. Письмо с подтверждением отправлено",
            },
        )


class ConfirmAccountTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.confirm_url = reverse(
            "supplier:confirm-email"
        )  # Используем правильное имя URL
        # Создаем пользователя для тестирования
        self.user = User.objects.create(
            first_name="John",
            last_name="Doe",
            email="john.doe@example.com",
            password="StrongPassword123",
            is_active=False,
        )
        # Создаем токен подтверждения для пользователя
        self.token = ConfirmEmailToken.objects.create(user=self.user)

    def test_confirm_account_valid_data(self):
        data = {"email": self.user.email, "token": self.token.key}

        response = self.client.get(self.confirm_url, data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response.json(),
            {"Status": True, "Message": "Пользователь успешно активирован"},
        )
        # Проверяем, что пользователь теперь активен
        self.user.refresh_from_db()
        self.assertTrue(self.user.is_active)

    def test_confirm_account_invalid_token(self):
        data = {"email": self.user.email, "token": "invalid-token"}

        response = self.client.get(self.confirm_url, data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            response.json(),
            {"Status": False, "Errors": "Неправильно указан токен подтверждения."},
        )

    def test_confirm_account_user_not_found(self):
        data = {"email": "nonexistent@example.com", "token": self.token.key}

        response = self.client.get(self.confirm_url, data)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(
            response.json(),
            {"Status": False, "Errors": "Пользователь с указанным email не найден"},
        )

    def test_confirm_account_missing_email_or_token(self):
        response = self.client.get(self.confirm_url)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            response.json(),
            {"Status": False, "Errors": "Не указан email или токен"},
        )
