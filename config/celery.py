import os
from celery import Celery

# Establece el módulo de settings de Django para Celery.
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

app = Celery("ecommerce")

# Carga la configuración desde settings.py usando el prefijo CELERY_.
app.config_from_object("django.conf:settings", namespace="CELERY")

# Descubre automáticamente archivos tasks.py en todas las apps instaladas.
app.autodiscover_tasks()


@app.task(bind=True)
def debug_task(self):
    """Tarea de prueba para verificar que Celery funciona correctamente."""
    print(f"Request: {self.request!r}")