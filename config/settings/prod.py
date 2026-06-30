# Importamos toda la configuracion comun definida en base.py
from .base import *

# En produccion siempre debe estar en False.
DEBUG = False

# ALLOWED_HOSTS define que dominios o IPs pueden acceder a la aplicacion.
ALLOWED_HOSTS = config("ALLOWED_HOSTS", default="").split(",")

USAR_HTTPS = config("USAR_HTTPS", default=True, cast=bool)

if USAR_HTTPS:
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = 60 * 60 * 24 * 30  # 30 dias
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    
# CORS - dominios del frontend autorizados a consumir esta API.
CORS_ALLOWED_ORIGINS = config(
    "CORS_ALLOWED_ORIGINS",
    default=""
).split(",")