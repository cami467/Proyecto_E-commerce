# Importamos toda la configuracion comun definida en base.py
from .base import *

# En produccion siempre debe estar en False.
DEBUG = False

# ALLOWED_HOSTS define que dominios o IPs pueden acceder a la aplicacion.
ALLOWED_HOSTS = csv_config("ALLOWED_HOSTS")

USAR_HTTPS = config("USAR_HTTPS", default=True, cast=bool)

if USAR_HTTPS:
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = 60 * 60 * 24 * 30  # 30 dias
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True

# CORS - dominios del frontend autorizados a consumir esta API.
CORS_ALLOWED_ORIGINS = csv_config("CORS_ALLOWED_ORIGINS")
CSRF_TRUSTED_ORIGINS = csv_config("CSRF_TRUSTED_ORIGINS")

# Solo debe activarse si la API se sirve detrás de un proxy HTTPS
# que envía X-Forwarded-Proto correctamente.
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")