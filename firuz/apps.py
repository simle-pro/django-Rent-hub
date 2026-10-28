from django.apps import AppConfig


class FiruzConfig(AppConfig):
    name = 'firuz'

    def ready(self):
        from . import signals
