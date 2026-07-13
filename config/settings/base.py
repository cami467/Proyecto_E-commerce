from datetime import timedelta
from pathlib import Path

import dj_database_url
from decouple import config


# ==============================================================================
# FUNCIONES AUXILIARES
# ==============================================================================

def csv_config(nombre_variable: str, default: str = "") -> list[str]:
    """
    Convierte una variable de entorno separada por comas
    en una lista limpia.

    Ejemplo:
    ALLOWED_HOSTS=localhost,127.0.0.1,mi-api.onrender.com
    """

    return [
        valor.strip()
        for valor in config(
            nombre_variable,
            default=default,
        ).split(",")
        if valor.strip()
    ]


# ==============================================================================
# RUTAS PRINCIPALES
# ==============================================================================

# Si base.py está en config/settings/base.py, esta ruta apunta
# a la raíz del proyecto, donde se encuentra manage.py.
BASE_DIR = Path(__file__).resolve().parent.parent.parent


# ==============================================================================
# SEGURIDAD GENERAL
# ==============================================================================

# Nunca debe escribirse directamente una clave real en este archivo.
SECRET_KEY = config("SECRET_KEY")

# En desarrollo debe configurarse DEBUG=True en el archivo .env.
# En producción, Render debe tener DEBUG=False.
DEBUG = config(
    "DEBUG",
    default=False,
    cast=bool,
)

# Dominios desde los cuales Django puede recibir solicitudes.
ALLOWED_HOSTS = csv_config(
    "ALLOWED_HOSTS",
    default="127.0.0.1,localhost",
)


# ==============================================================================
# APLICACIONES INSTALADAS
# ==============================================================================

DJANGO_APPS = [
    # Servidor ASGI. Debe aparecer antes de staticfiles.
    "daphne",

    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
]


THIRD_PARTY_APPS = [
    # Django REST Framework.
    "rest_framework",

    # Autenticación JWT.
    "rest_framework_simplejwt",

    # Lista negra de refresh tokens.
    "rest_framework_simplejwt.token_blacklist",

    # Filtros de endpoints.
    "django_filters",

    # Documentación automática OpenAPI.
    "drf_spectacular",

    # Comunicación entre React y Django.
    "corsheaders",

    # Resultados de tareas Celery.
    "django_celery_results",

    # WebSockets.
    "channels",
]


LOCAL_APPS = [
    "core",
    "apps.usuarios",
    "apps.productos",
    "apps.carrito",
    "apps.ordenes",
    "apps.pagos",
    "apps.cupones",
    "apps.resenas",
    "apps.notificaciones",
]


INSTALLED_APPS = (
    DJANGO_APPS
    + THIRD_PARTY_APPS
    + LOCAL_APPS
)


# ==============================================================================
# MIDDLEWARE
# ==============================================================================

MIDDLEWARE = [
    # CORS debe ejecutarse antes de CommonMiddleware.
    "corsheaders.middleware.CorsMiddleware",

    "django.middleware.security.SecurityMiddleware",

    # WhiteNoise sirve los archivos estáticos en producción.
    "whitenoise.middleware.WhiteNoiseMiddleware",

    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",

    # Protección CSRF.
    "django.middleware.csrf.CsrfViewMiddleware",

    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",

    # Protección contra clickjacking.
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]


# ==============================================================================
# RUTAS, PLANTILLAS, WSGI Y ASGI
# ==============================================================================

ROOT_URLCONF = "config.urls"


TEMPLATES = [
    {
        "BACKEND": (
            "django.template.backends.django."
            "DjangoTemplates"
        ),
        "DIRS": [
            BASE_DIR / "templates",
        ],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                (
                    "django.template.context_processors."
                    "debug"
                ),
                (
                    "django.template.context_processors."
                    "request"
                ),
                (
                    "django.contrib.auth.context_processors."
                    "auth"
                ),
                (
                    "django.contrib.messages."
                    "context_processors.messages"
                ),
            ],
        },
    },
]


# Entrada tradicional WSGI.
WSGI_APPLICATION = "config.wsgi.application"

# Entrada ASGI para Django Channels y WebSockets.
ASGI_APPLICATION = "config.asgi.application"


# ==============================================================================
# BASE DE DATOS
# ==============================================================================

# En Render se utilizará DATABASE_URL.
# En desarrollo se siguen admitiendo DB_NAME, DB_USER, etc.
DATABASES = {
    "default": dj_database_url.config(
        default=config(
            "DATABASE_URL",
            default=(
                "postgresql://"
                f"{config('DB_USER', default='postgres')}:"
                f"{config('DB_PASSWORD', default='')}@"
                f"{config('DB_HOST', default='localhost')}:"
                f"{config('DB_PORT', default='5432')}/"
                f"{config('DB_NAME', default='ecommerce_db')}"
            ),
        ),
        conn_max_age=600,
        conn_health_checks=True,
    )
}


# ==============================================================================
# VALIDACIÓN DE CONTRASEÑAS
# ==============================================================================

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": (
            "django.contrib.auth.password_validation."
            "UserAttributeSimilarityValidator"
        ),
    },
    {
        "NAME": (
            "django.contrib.auth.password_validation."
            "MinimumLengthValidator"
        ),
    },
    {
        "NAME": (
            "django.contrib.auth.password_validation."
            "CommonPasswordValidator"
        ),
    },
    {
        "NAME": (
            "django.contrib.auth.password_validation."
            "NumericPasswordValidator"
        ),
    },
]


# Modelo personalizado de usuario.
AUTH_USER_MODEL = "usuarios.Usuario"


# ==============================================================================
# INTERNACIONALIZACIÓN
# ==============================================================================

LANGUAGE_CODE = "es-py"
TIME_ZONE = "America/Asuncion"

USE_I18N = True
USE_TZ = True


# ==============================================================================
# FORMATO NUMÉRICO DE PARAGUAY
# ==============================================================================

DECIMAL_SEPARATOR = ","
THOUSAND_SEPARATOR = "."
USE_THOUSAND_SEPARATOR = True
NUMBER_GROUPING = 3


# ==============================================================================
# ARCHIVOS ESTÁTICOS
# ==============================================================================

# Debe comenzar con una barra.
STATIC_URL = "/static/"

# Directorio generado por collectstatic.
STATIC_ROOT = BASE_DIR / "staticfiles"

# Solo se agrega la carpeta si existe.
STATICFILES_DIRS = []

STATIC_DIRECTORY = BASE_DIR / "static"

if STATIC_DIRECTORY.exists():
    STATICFILES_DIRS.append(STATIC_DIRECTORY)


# WhiteNoise comprimirá y versionará los archivos estáticos.
STORAGES = {
    "default": {
        "BACKEND": (
            "django.core.files.storage."
            "FileSystemStorage"
        ),
    },
    "staticfiles": {
        "BACKEND": (
            "whitenoise.storage."
            "CompressedManifestStaticFilesStorage"
        ),
    },
}


# ==============================================================================
# ARCHIVOS MULTIMEDIA
# ==============================================================================

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"


# ==============================================================================
# CONFIGURACIÓN GENERAL DE MODELOS
# ==============================================================================

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"


# ==============================================================================
# DJANGO REST FRAMEWORK
# ==============================================================================

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        (
            "rest_framework_simplejwt.authentication."
            "JWTAuthentication"
        ),
    ],

    "DEFAULT_PERMISSION_CLASSES": [
        (
            "rest_framework.permissions."
            "IsAuthenticated"
        ),
    ],

    "DEFAULT_THROTTLE_CLASSES": [
        (
            "rest_framework.throttling."
            "ScopedRateThrottle"
        ),
    ],

    "DEFAULT_THROTTLE_RATES": {
        "login": "5/minute",
    },

    "DEFAULT_PAGINATION_CLASS": (
        "core.pagination.PaginacionEstandar"
    ),

    "PAGE_SIZE": 20,

    "DEFAULT_SCHEMA_CLASS": (
        "drf_spectacular.openapi.AutoSchema"
    ),
}


# ==============================================================================
# DOCUMENTACIÓN DE LA API
# ==============================================================================

SPECTACULAR_SETTINGS = {
    "TITLE": "E-Commerce API",

    "DESCRIPTION": (
        "API REST para sistema de e-commerce"
    ),

    "VERSION": "1.0.0",

    "SERVE_INCLUDE_SCHEMA": False,

    "ENUM_NAME_OVERRIDES": {
        "EstadoOrdenEnum": (
            "apps.ordenes.models.Orden.Estado"
        ),

        "EstadoPagoEnum": (
            "apps.pagos.models.Pago.Estado"
        ),

        "PasarelaEnum": (
            "apps.pagos.models.Pago.Pasarela"
        ),

        "TipoCuponEnum": (
            "apps.cupones.models."
            "Cupon.TipoDescuento"
        ),

        "TipoNotificacionEnum": (
            "apps.notificaciones.models."
            "Notificacion.Tipo"
        ),

        "TasaIVAEnum": (
            "apps.productos.models."
            "Producto.TasaIVA"
        ),
    },

    "ENUM_GENERATE_CHOICE_DESCRIPTION": False,
}


# ==============================================================================
# JSON WEB TOKENS
# ==============================================================================

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(hours=1),

    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),

    "ROTATE_REFRESH_TOKENS": True,

    "BLACKLIST_AFTER_ROTATION": True,

    "AUTH_HEADER_TYPES": (
        "Bearer",
    ),
}


# ==============================================================================
# CORS
# ==============================================================================

CORS_ALLOWED_ORIGINS = csv_config(
    "CORS_ALLOWED_ORIGINS",
    default=(
        "http://localhost:5173,"
        "http://127.0.0.1:5173"
    ),
)

CORS_ALLOW_ALL_ORIGINS = False


# No es obligatorio para JWT por encabezado Authorization,
# pero puede ser útil si posteriormente se utilizan cookies.
CORS_ALLOW_CREDENTIALS = True


# ==============================================================================
# CSRF
# ==============================================================================

CSRF_TRUSTED_ORIGINS = csv_config(
    "CSRF_TRUSTED_ORIGINS",
    default=(
        "http://localhost:5173,"
        "http://127.0.0.1:5173"
    ),
)


# ==============================================================================
# REDIS
# ==============================================================================

# Redis se comparte entre Celery y Django Channels.
REDIS_URL = config(
    "REDIS_URL",
    default=config(
        "CELERY_BROKER_URL",
        default="redis://localhost:6379/0",
    ),
)


# ==============================================================================
# CELERY
# ==============================================================================

CELERY_BROKER_URL = REDIS_URL

CELERY_RESULT_BACKEND = "django-db"

CELERY_ACCEPT_CONTENT = [
    "json",
]

CELERY_TASK_SERIALIZER = "json"

CELERY_RESULT_SERIALIZER = "json"

CELERY_TIMEZONE = TIME_ZONE

CELERY_TASK_TRACK_STARTED = True

CELERY_TASK_TIME_LIMIT = 30 * 60


# ==============================================================================
# DJANGO CHANNELS
# ==============================================================================

# En desarrollo permite trabajar sin un Redis activo.
# En producción se debe configurar REDIS_URL.
if DEBUG:
    CHANNEL_LAYERS = {
        "default": {
            "BACKEND": (
                "channels.layers."
                "InMemoryChannelLayer"
            ),
        },
    }
else:
    CHANNEL_LAYERS = {
        "default": {
            "BACKEND": (
                "channels_redis.core."
                "RedisChannelLayer"
            ),
            "CONFIG": {
                "hosts": [
                    REDIS_URL,
                ],
            },
        },
    }


# ==============================================================================
# STRIPE
# ==============================================================================

STRIPE_SECRET_KEY = config(
    "STRIPE_SECRET_KEY",
    default="",
)

STRIPE_WEBHOOK_SECRET = config(
    "STRIPE_WEBHOOK_SECRET",
    default="",
)


# ==============================================================================
# DATOS DE LA EMPRESA PARA FACTURACIÓN
# ==============================================================================

URL_BASE_SISTEMA = config(
    "URL_BASE_SISTEMA",
    default="http://127.0.0.1:8000",
)

EMPRESA_RAZON_SOCIAL = config(
    "EMPRESA_RAZON_SOCIAL",
    default="Mi Empresa",
)

EMPRESA_RUC = config(
    "EMPRESA_RUC",
    default="0000000-0",
)

EMPRESA_TIMBRADO = config(
    "EMPRESA_TIMBRADO",
    default="00000000",
)

EMPRESA_TIMBRADO_VIGENCIA_INICIO = config(
    "EMPRESA_TIMBRADO_VIGENCIA_INICIO",
    default="01/01/2025",
)

EMPRESA_TIMBRADO_VIGENCIA_FIN = config(
    "EMPRESA_TIMBRADO_VIGENCIA_FIN",
    default="31/12/2026",
)

EMPRESA_DIRECCION = config(
    "EMPRESA_DIRECCION",
    default="Dirección no configurada",
)

EMPRESA_TELEFONO = config(
    "EMPRESA_TELEFONO",
    default="(000) 000 000",
)

EMPRESA_ACTIVIDAD = config(
    "EMPRESA_ACTIVIDAD",
    default="Comercio electrónico",
)


# ==============================================================================
# SEGURIDAD PARA PRODUCCIÓN
# ==============================================================================

if not DEBUG:
    # Render trabaja detrás de un proxy HTTPS.
    SECURE_PROXY_SSL_HEADER = (
        "HTTP_X_FORWARDED_PROTO",
        "https",
    )

    # Redirige automáticamente HTTP a HTTPS.
    SECURE_SSL_REDIRECT = True

    # Cookies disponibles únicamente mediante HTTPS.
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True

    # Política HSTS inicial de 30 días.
    SECURE_HSTS_SECONDS = 60 * 60 * 24 * 30

    SECURE_HSTS_INCLUDE_SUBDOMAINS = True

    # Se mantiene desactivado mientras el despliegue
    # todavía está en etapa de prueba.
    SECURE_HSTS_PRELOAD = False

    SECURE_CONTENT_TYPE_NOSNIFF = True

    X_FRAME_OPTIONS = "DENY"