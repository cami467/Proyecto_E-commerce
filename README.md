# Proyecto E-commerce — Backend

API REST para un sistema de e-commerce, construida con Django y Django REST Framework. Incluye catálogo de productos con variantes e inventario, carrito de compras, órdenes con historial de estados, pagos, cupones de descuento, reseñas, notificaciones en tiempo real vía WebSockets, y generación de facturas en PDF con formato paraguayo (IVA incluido, timbrado, QR).

## Stack técnico

- **Django 6** + **Django REST Framework** — API REST
- **PostgreSQL** — base de datos principal
- **Simple JWT** — autenticación por token (login con email)
- **Celery + Redis** — tareas asíncronas (notificaciones, procesos en segundo plano)
- **Django Channels + Daphne** — WebSockets para notificaciones en tiempo real
- **drf-spectacular** — documentación OpenAPI / Swagger / Redoc autogenerada
- **ReportLab + qrcode** — generación de facturas en PDF
- **django-cors-headers** — CORS para consumo desde un frontend separado

## Estructura del proyecto

```
config/
  settings/
    base.py      # configuración común
    dev.py       # desarrollo (DEBUG=True)
    prod.py      # producción (HTTPS, hosts, CORS restringido)
    test.py      # settings para tests (SQLite, hashers rápidos)
  asgi.py        # entrypoint ASGI (HTTP + WebSocket)
  wsgi.py        # entrypoint WSGI (solo HTTP)
  celery.py      # configuración de Celery
  urls.py        # rutas raíz de la API

core/
  models.py              # ModeloBase: UUID, timestamps, borrado lógico (esta_activo)
  permissions.py
  pagination.py
  exceptions.py           # excepciones de negocio (StockInsuficiente, CarritoVacio, CuponInvalido)
  numeros_en_letras.py    # convierte montos a texto para las facturas
  management/commands/cargar_datos_demo.py   # datos de prueba (usuarios, productos, cupón)

apps/
  usuarios/       # usuario personalizado (login por email), registro, perfil
  productos/      # categorías (jerárquicas), productos, variantes (stock real), imágenes
  carrito/        # carrito y sus items
  ordenes/        # órdenes, historial de estados, facturación PDF (SIFEN-like)
  pagos/          # pagos por pasarela, con máquina de estados
  cupones/        # cupones por porcentaje o monto fijo
  resenas/        # reseñas de productos
  notificaciones/ # notificaciones + WebSocket en tiempo real (Channels)
```

## Modelo de dominio (resumen)

- **`ModeloBase`** (`core/models.py`): clase abstracta de la que heredan casi todos los modelos. Da UUID como PK, `fecha_creacion`/`fecha_actualizacion` automáticas, y borrado lógico vía `esta_activo` (con manager `activos` para filtrar automáticamente).
- **Usuario personalizado** (`apps.usuarios.Usuario`): extiende `AbstractUser`, con `email` único (es el campo de login), `telefono` y `avatar`.
- **Catálogo** (`apps.productos`): `Categoria` soporta jerarquía (categoría padre/subcategorías, con validación anti-ciclos). `Producto` guarda precio base, descuento y tasa de IVA. El **stock real vive en `Variante`** (no en `Producto`), con operaciones `incrementar_stock` / `reducir_stock` transaccionales (`select_for_update`) para evitar condiciones de carrera.
- **Carrito** (`apps.carrito`): un carrito por usuario (`OneToOne`). `agregar_o_actualizar_item` bloquea la variante para evitar carreras cuando dos requests tocan el mismo carrito a la vez.
- **Órdenes** (`apps.ordenes`): `Orden.crear_desde_carrito()` congela precios, valida stock, descuenta inventario en lote (`bulk_create`/`bulk_update`) y registra todo en una transacción atómica. Cada cambio de estado queda en `HistorialEstadoOrden`. Incluye generación de factura en PDF (`factura.py`) con numeración estilo Paraguay (`001-001-NNNNNNN`), QR de verificación y montos en letras.
- **Pagos** (`apps.pagos`): un `Pago` por intento de cobro; solo puede haber un pago `approved` por orden (constraint a nivel de base). Las transiciones de estado (`marcar_aprobado`, `marcar_rechazado`, `marcar_reembolsado`) son atómicas e idempotentes.
- **Cupones** (`apps.cupones`): por porcentaje o monto fijo, con vigencia, límite de usos y restricción opcional a usuarios específicos.
- **Notificaciones** (`apps.notificaciones`): se crean de forma asíncrona vía Celery cada vez que ocurre un evento relevante (orden confirmada/cancelada, pago aprobado/rechazado). Además de guardarse en la base, se empujan en tiempo real por WebSocket al usuario conectado.

## Notificaciones en tiempo real (WebSockets)

Este proyecto usa **Django Channels** para notificar al usuario en vivo, sin polling:

- `config/asgi.py` enruta HTTP normal por Django y WebSocket (`/ws/notificaciones/`) por Channels, protegido con `AllowedHostsOriginValidator`.
- `apps/notificaciones/middleware.py` autentica la conexión WebSocket usando el mismo JWT de la API REST, pasado como query param (`?token=...`), ya que el navegador no permite mandar headers custom en el handshake de WebSocket.
- `apps/notificaciones/consumers.py` agrupa a cada usuario en su propio canal (`notificaciones_usuario_<id>`).
- `apps/notificaciones/tasks.py` (Celery) crea la notificación en la base y, en el mismo paso, hace `group_send` para empujarla en vivo a quien esté conectado. Si nadie está conectado, la notificación igual queda guardada para consultarla después.

**Requisito importante para desarrollo:** además de `python manage.py runserver` (que ya sirve WebSockets gracias a `daphne` en `INSTALLED_APPS`), hace falta tener **Redis** corriendo y un **worker de Celery** activo:

```bash
celery -A config worker -l info --pool=solo   # --pool=solo es necesario en Windows
```

## Configuración de entorno

Este proyecto usa `python-decouple` para leer variables desde un archivo `.env` en la raíz (no versionado). Variables usadas:

```dotenv
# Django
SECRET_KEY=cambia-esto-por-una-clave-secreta-real
DJANGO_SETTINGS_MODULE=config.settings.dev   # o config.settings.prod en producción

# Base de datos (PostgreSQL)
DB_NAME=ecommerce_db
DB_USER=postgres
DB_PASSWORD=
DB_HOST=localhost
DB_PORT=5432

# Celery / Redis (también usado como Channel Layer de Channels)
CELERY_BROKER_URL=redis://localhost:6379/0

# CORS / hosts (solo necesarios en producción; dev.py ya trae defaults locales)
ALLOWED_HOSTS=localhost,127.0.0.1
CORS_ALLOWED_ORIGINS=http://localhost:5173,http://127.0.0.1:5173
CSRF_TRUSTED_ORIGINS=https://tu-dominio.com
USAR_HTTPS=True
```

## Instalación y puesta en marcha (desarrollo local)

### 1. Cloná el repo y creá el entorno virtual

```bash
git clone <url-del-repo>
cd Proyecto_E-commerce
python -m venv venv
venv\Scripts\activate          # Windows
# source venv/bin/activate     # Linux/Mac
```

### 2. Instalá las dependencias

```bash
pip install -r requirements.txt
```

### 3. Levantá PostgreSQL y Redis

Hay un `docker-compose.yml` en `docker/` que levanta ambos servicios:

```bash
docker compose -f docker/docker-compose.yml up -d
```

### 4. Creá tu archivo `.env`

Copiá el bloque de la sección anterior en un archivo `.env` en la raíz del proyecto, y completá al menos `SECRET_KEY`.

### 5. Aplicá las migraciones

```bash
python manage.py migrate
```

### 6. (Opcional) Cargá datos de prueba

```bash
python manage.py cargar_datos_demo
```

### 7. Creá un superusuario para el admin

```bash
python manage.py createsuperuser
```

### 8. Levantá los tres procesos necesarios

```bash
# Terminal 1 — backend (HTTP + WebSocket)
python manage.py runserver

# Terminal 2 — worker de Celery (notificaciones, tareas async)
celery -A config worker -l info --pool=solo

# Terminal 3 — Redis y PostgreSQL, si no los levantaste con Docker
```

La API queda disponible en `http://127.0.0.1:8000/`.

## Endpoints principales

Login con `POST /api/token/` (devuelve `access` y `refresh`), refresh en `POST /api/token/refresh/`. El resto de los recursos cuelgan de `/api/usuarios/`, `/api/productos/`, `/api/carrito/`, `/api/ordenes/`, `/api/pagos/`, `/api/cupones/`, `/api/resenas/` y `/api/notificaciones/` (con su WebSocket en `ws://.../ws/notificaciones/?token=<access>`). Documentación interactiva en `/api/swagger/` y `/api/redoc/`. Todos requieren `Authorization: Bearer <access_token>`, salvo login, registro y refresh.

## Tests

```bash
python manage.py test
```

Corre con `config.settings.test` (SQLite + hasher rápido, solo para tests).