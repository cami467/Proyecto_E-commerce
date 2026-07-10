from .base import *

DEBUG = True

ALLOWED_HOSTS = ["localhost", "127.0.0.1", "0.0.0.0"]

# En desarrollo permitimos el frontend local.
# Si necesitás otro puerto, agregalo en CORS_ALLOWED_ORIGINS del .env.
CORS_ALLOWED_ORIGINS = csv_config(
    "CORS_ALLOWED_ORIGINS",
    default="http://localhost:5173,http://127.0.0.1:5173, http://localhost:4173,http://127.0.0.1:4173",
)
CORS_ALLOW_ALL_ORIGINS = False