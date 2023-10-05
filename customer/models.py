from django.contrib.auth.models import User
from django.db import models


class Customer(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    # Дополнительные поля клиента


class Order(models.Model):
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE)
    # Другие поля заказа
