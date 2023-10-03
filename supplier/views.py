from rest_framework import viewsets
from .models import Supplier, Product
from .serializers import SupplierSerializer, ProductSerializer


class CustomerViewSet(viewsets.ModelViewSet):
    queryset = Supplier.objects.all()
    serializer_class = SupplierSerializer


class OrderViewSet(viewsets.ModelViewSet):
    queryset = Product.objects.all()
    serializer_class = ProductSerializer
