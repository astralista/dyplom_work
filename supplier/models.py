from django.db import models


class Supplier(models.Model):
    name = models.CharField(max_length=100)
    is_accepting_orders = models.BooleanField(default=True)
    # Другие поля поставщика


class Product(models.Model):
    supplier = models.ForeignKey(Supplier, on_delete=models.CASCADE)
    name = models.CharField(max_length=100)
    # Другие поля товара
