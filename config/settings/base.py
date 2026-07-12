from pathlib import Path
from decouple import config
from datetime import timedelta


def csv_config(nombre_variable, default=""):
    """Convierte variables de entorno separadas por coma en listas limpias."""
    return [
        valor.strip()
        for valor in config(nombre_variable, default=default).split(",")
        if valor.strip()
    ]
# Ruta base del proyecto (nivel raíz)
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# Clave secreta para firmar cookies, sesiones y tokens
SECRET_KEY = config("SECRET_KEY")

# Modo debug (solo debe estar en True en desarrollo)
DEBUG = False

# Lista de dominios permitidos para servir la aplicación
ALLOWED_HOSTS = []

# Aplicaciones nativas de Django
DJANGO_APPS = [
    "daphne",                     #  servidor ASGI (debe ir antes que staticfiles)
    "django.contrib.admin",       # Panel de administración
    "django.contrib.auth",        # Sistema de autenticación
    "django.contrib.contenttypes",# Tipos de contenido
    "django.contrib.sessions",    # Manejo de sesiones
    "django.contrib.messages",    # Mensajes flash
    "django.contrib.staticfiles", # Archivos estáticos (CSS, JS, imágenes)
]

# Librerías externas instaladas
THIRD_PARTY_APPS = [
    "rest_framework",             # Django REST Framework
    "rest_framework_simplejwt",   # Autenticación con JWT
    "rest_framework_simplejwt.token_blacklist",   # Lista negra de tokens JWT
    "django_filters",             # Filtros en consultas
    "drf_spectacular",            # Documentación automática de la API
    "corsheaders",                # Manejo de cabeceras CORS
    "django_celery_results",    # Almacena resultados de tareas de Celery en la base de datos
    "channels",                   # soporte de WebSockets (Django Channels)
]

# Aplicaciones propias del proyecto
LOCAL_APPS = [
    "core",                       # Configuración central
    "apps.usuarios",              # Gestión de usuarios
    "apps.productos",             # Productos
    "apps.carrito",               # Carrito de compras
    "apps.ordenes",               # Órdenes
    "apps.pagos",                 # Pagos
    "apps.cupones",               # Cupones de descuento
    "apps.resenas",               # Reseñas de productos
    "apps.notificaciones",        # Notificaciones
    
]

# Registro de todas las apps
INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

# Middleware: capas intermedias que procesan las peticiones/respuestas
MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",   # Protección CSRF
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware", # Prevención clickjacking
]

# Archivo principal de rutas
ROOT_URLCONF = "config.urls"

# Configuración de plantillas HTML
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],  # Directorios adicionales de plantillas
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

# Punto de entrada WSGI para servidores
WSGI_APPLICATION = "config.wsgi.application"

# Punto de entrada ASGI para servidores (NUEVO: necesario para WebSockets con Channels)
ASGI_APPLICATION = "config.asgi.application"

# Configuración de la base de datos (PostgreSQL)
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": config("DB_NAME", default="ecommerce_db"),
        "USER": config("DB_USER", default="postgres"),
        "PASSWORD": config("DB_PASSWORD", default=""),
        "HOST": config("DB_HOST", default="localhost"),
        "PORT": config("DB_PORT", default="5432"),
    }
}

# Validadores de contraseñas
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# Modelo de usuario personalizado
AUTH_USER_MODEL = "usuarios.Usuario"

# Configuración regional
LANGUAGE_CODE = "es-py"           # Español de Paraguay
TIME_ZONE = "America/Asuncion"    # Zona horaria local
USE_I18N = True    
USE_L10N = True                  # Internacionalización
USE_TZ = True                     # Uso de zonas horarias

# Formato monetario de Paraguay - Guaranies
DECIMAL_SEPARATOR = "," # Define que los decimales se separan con coma (ejemplo: 123,45).
THOUSAND_SEPARATOR = "." # Define que los miles se separan con punto (ejemplo: 1.234.567).
USE_THOUSAND_SEPARATOR = True # Activa el uso del separador de miles en la representación de números.
NUMBER_GROUPING = 3 # Indica que los números se agrupan cada 3 dígitos (ejemplo: 1.234.567).

# Archivos estáticos
STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"

MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"

# Tipo de campo por defecto para IDs
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Configuración de Django REST Framework
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework_simplejwt.authentication.JWTAuthentication", # Autenticación JWT
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated", # Requiere login por defecto
    ],
    "DEFAULT_THROTTLE_CLASSES": [
        "rest_framework.throttling.ScopedRateThrottle",
    ],
    "DEFAULT_THROTTLE_RATES": {
        "login": "5/minute",
    },
    "DEFAULT_PAGINATION_CLASS": "core.pagination.PaginacionEstandar", # Paginación personalizada
    "PAGE_SIZE": 20,
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema", # Documentación automática
}

# Configuración de documentación de la API
SPECTACULAR_SETTINGS = {
    "TITLE": "E-Commerce API",
    "DESCRIPTION": "API REST para sistema de e-commerce",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "ENUM_NAME_OVERRIDES": {
        "EstadoOrdenEnum": "apps.ordenes.models.Orden.Estado",
        "EstadoPagoEnum": "apps.pagos.models.Pago.Estado",
        "PasarelaEnum": "apps.pagos.models.Pago.Pasarela",
        "TipoCuponEnum": "apps.cupones.models.Cupon.TipoDescuento",
        "TipoNotificacionEnum": "apps.notificaciones.models.Notificacion.Tipo",
        "TasaIVAEnum": "apps.productos.models.Producto.TasaIVA",
    },
    "ENUM_GENERATE_CHOICE_DESCRIPTION": False,
}

# Configuración de JWT (tokens)
SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(hours=1),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "AUTH_HEADER_TYPES": ("Bearer",),
}

# CORS
CORS_ALLOWED_ORIGINS = []
CORS_ALLOW_ALL_ORIGINS = False

# ==============================================================================
# CONFIGURACIÓN DE CELERY
# ==============================================================================

CELERY_BROKER_URL = config("CELERY_BROKER_URL", default="redis://localhost:6379/0")
CELERY_RESULT_BACKEND = "django-db"
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_TIMEZONE = TIME_ZONE
CELERY_TASK_TRACK_STARTED = True
CELERY_TASK_TIME_LIMIT = 30 * 60


# ==============================================================================
# CONFIGURACIÓN DE STRIPE
# ==============================================================================
STRIPE_SECRET_KEY = config("STRIPE_SECRET_KEY", default="")
STRIPE_WEBHOOK_SECRET = config("STRIPE_WEBHOOK_SECRET", default="")



# ==============================================================================
# CONFIGURACIÓN DE DJANGO CHANNELS (WebSockets)  <-- BLOQUE NUEVO
# ==============================================================================

CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {
            # Reutiliza el mismo Redis que ya usa Celery (mismo host/puerto,
            # distinta responsabilidad: Channels usa sus propias claves internas).
            "hosts": [config("CELERY_BROKER_URL", default="redis://localhost:6379/0")],
        },
    },
}

# ==============================================================================
# DATOS DE LA EMPRESA PARA FACTURACIÓN
# ==============================================================================
URL_BASE_SISTEMA = config("URL_BASE_SISTEMA", default="http://127.0.0.1:8000")
EMPRESA_RAZON_SOCIAL = config("EMPRESA_RAZON_SOCIAL", default="Mi Empresa")
EMPRESA_RUC = config("EMPRESA_RUC", default="0000000-0")
EMPRESA_TIMBRADO = config("EMPRESA_TIMBRADO", default="00000000")
EMPRESA_TIMBRADO_VIGENCIA_INICIO = config("EMPRESA_TIMBRADO_VIGENCIA_INICIO", default="01/01/2025")
EMPRESA_TIMBRADO_VIGENCIA_FIN = config("EMPRESA_TIMBRADO_VIGENCIA_FIN", default="31/12/2026")
EMPRESA_DIRECCION = config("EMPRESA_DIRECCION", default="Dirección no configurada")
EMPRESA_TELEFONO = config("EMPRESA_TELEFONO", default="(000) 000 000")
EMPRESA_ACTIVIDAD = config("EMPRESA_ACTIVIDAD", default="Comercio electrónico")