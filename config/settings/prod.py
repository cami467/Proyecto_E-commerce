# Importamos toda la configuración común definida en base.py
from .base import *

# En producción siempre debe estar en False.
DEBUG = False

# ALLOWED_HOSTS define qué dominios o IPs pueden acceder a la aplicación.
ALLOWED_HOSTS = config("ALLOWED_HOSTS", default="").split(",")
