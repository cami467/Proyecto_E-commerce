from pathlib import Path
from decouple import config
from datetime import timedelta

# Ruta base del proyecto (nivel raíz)
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# Clave secreta para firmar cookies, sesiones y tokens
SECRET_KEY = config("SECRET_KEY", default="clave temporal cambiar mas adelante")

# Modo debug (solo debe estar en True en desarrollo)
DEBUG = False

# Lista de dominios permitidos para servir la aplicación
ALLOWED_HOSTS = []

# Aplicaciones nativas de Django
DJANGO_APPS = [
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
    "django_filters",             # Filtros en consultas
    "drf_spectacular",            # Documentación automática de la API
    "corsheaders",                # Manejo de cabeceras CORS
    "django_celery_results",    # Almacena resultados de tareas de Celery en la base de datos
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
}

# Configuración de JWT (tokens)
SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(hours=1),   # Duración del token de acceso
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),   # Duración del token de refresco
    "ROTATE_REFRESH_TOKENS": True,                 # Rotar tokens de refresco
    "BLACKLIST_AFTER_ROTATION": False,             # No invalidar tokens antiguos
    "AUTH_HEADER_TYPES": ("Bearer",),              # Tipo de encabezado
}

# CORS
CORS_ALLOWED_ORIGINS = [] # Lista de dominios permitidos para consumir la API
CORS_ALLOW_ALL_ORIGINS = False # Si es True, permite cualquier origen (inseguro en producción)
                               # Si está en False, solo se aceptan los orígenes definidos en CORS_ALLOWED_ORIGINS.
                               

# ==============================================================================
# CONFIGURACIÓN DE CELERY
# ==============================================================================

CELERY_BROKER_URL = config("CELERY_BROKER_URL", default="redis://localhost:6379/0")
"""
URL del broker (Redis) que Celery usa como cola de mensajes.
En Docker, el host suele ser el nombre del servicio (ej: redis://redis:6379/0).
"""

CELERY_RESULT_BACKEND = "django-db"
"""
Guarda los resultados de las tareas en la base de datos usando
django-celery-results. Permite consultar el estado de cada tarea
desde el admin de Django.
"""

CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_TIMEZONE = TIME_ZONE
"""
Usa la misma zona horaria configurada en Django (America/Asuncion)
para que los timestamps de las tareas sean consistentes.
"""

CELERY_TASK_TRACK_STARTED = True
"""Permite ver en el admin cuándo una tarea pasó de PENDING a STARTED."""

CELERY_TASK_TIME_LIMIT = 30 * 60
"""Límite máximo de 30 minutos por tarea, para evitar tareas colgadas."""

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