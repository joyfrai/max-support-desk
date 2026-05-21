import os

from django.core.wsgi import get_wsgi_application


os.environ.setdefault("DJANGO_SETTINGS_MODULE", "max_support_desk.settings")

application = get_wsgi_application()

