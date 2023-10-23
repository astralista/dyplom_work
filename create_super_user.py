from django.contrib.auth import get_user_model


def run():
    User = get_user_model()
    if not User.objects.filter(username='${DJANGO_SUPERUSER_USERNAME}').exists():
        User.objects.create_superuser('${DJANGO_SUPERUSER_EMAIL}',
                                      '${DJANGO_SUPERUSER_PASSWORD}')
