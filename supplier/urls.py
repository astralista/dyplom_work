from django.urls import include, path
from django_rest_passwordreset.views import (reset_password_confirm,
                                             reset_password_request_token)
from drf_spectacular.views import (SpectacularAPIView, SpectacularRedocView,
                                   SpectacularSwaggerView)
from rest_framework import routers

from .views import (AccountDetails, BasketView, CategoryView, ConfirmAccount,
                    ContactView, LoginAccount, OrderView, PartnerOrders,
                    PartnerState, PartnerUpdate, ProductInfoView,
                    RegisterAccount, ShopView)

router = routers.DefaultRouter()
router.register(r"shops", ShopView)
router.register(r"categories", CategoryView)
router.register(r"products", ProductInfoView, basename="products")

urlpatterns = [
    path("schema", SpectacularAPIView.as_view(), name="schema"),
    path(
        "schema/swagger/",
        SpectacularSwaggerView.as_view(url_name="schema"),
        name="swagger-ui",
    ),
    path(
        "schema/redoc/", SpectacularRedocView.as_view(url_name="schema"), name="redoc"
    ),
    path("partner/update", PartnerUpdate.as_view(), name="partner-update"),
    path("partner/state", PartnerState.as_view(), name="partner-state"),
    path("partner/orders", PartnerOrders.as_view(), name="partner-orders"),
    path("user/register", RegisterAccount.as_view(), name="user-register"),
    path("user/register/confirm", ConfirmAccount.as_view(), name="confirm-email"),
    path("user/details", AccountDetails.as_view(), name="user-details"),
    path("user/contact", ContactView.as_view(), name="user-contact"),
    path("user/login", LoginAccount.as_view(), name="user-login"),
    path("user/password_reset", reset_password_request_token, name="password-reset"),
    path(
        "user/password_reset/confirm",
        reset_password_confirm,
        name="password-reset-confirm",
    ),
    path("basket", BasketView.as_view(), name="basket"),
    path("order", OrderView.as_view(), name="order"),
    path("", include(router.urls)),
]
