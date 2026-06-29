from celery import shared_task
from django.contrib.auth import get_user_model

from .models import Notificacion

Usuario = get_user_model()


@shared_task(bind=True, max_retries=3, default_retry_delay=10)
def crear_notificacion(self, usuario_id, tipo, titulo, mensaje, referencia_id=""):
    """
    Tarea asíncrona que crea una notificación para un usuario en la base de datos.
        Se ejecuta en segundo plano a través de Celery para no bloquear el ciclo
        de respuesta (Request/Response) HTTP de la API principal.
        
        Args:
            usuario_id (str): UUID del usuario destinatario.
            tipo (str): Tipo de notificación según los canales del modelo (ej: 'pago', 'orden').
            titulo (str): Título corto de la notificación.
            mensaje (str): Cuerpo o descripción del evento.
            referencia_id (str, opcional): UUID de la entidad relacionada (Orden, Pago, etc.).

    """
    try:
        usuario = Usuario.objects.get(pk=usuario_id)
    except Usuario.DoesNotExist:
        # Error permanente: el usuario no existe, reintentar no ayuda.
        return f"Usuario {usuario_id} no existe. Notificación descartada."
    except Exception as exc:
        # Error transitorio (ej: conexion a la BD): reintentar.
        raise self.retry(exc=exc)

    notificacion = Notificacion.objects.create(
        usuario=usuario,
        tipo=tipo,
        titulo=titulo,
        mensaje=mensaje,
        referencia_id=str(referencia_id) if referencia_id else "",
    )
    return f"Notificación {notificacion.id} creada para {usuario.username}."


@shared_task
def notificar_orden_confirmada(usuario_id, orden_id, numero_orden, total):
    """
    Notifica al usuario que su orden fue confirmada exitosamente.
    Se dispara desde Orden.crear_desde_carrito().
    """
    crear_notificacion.delay(
        usuario_id=usuario_id,
        tipo="orden_confirmada",
        titulo="¡Tu orden fue confirmada!",
        mensaje=(
            f"Tu orden {numero_orden} fue confirmada por un total de "
            f"Gs. {int(total):,}".replace(",", ".") + ". "
            f"Te avisaremos cuando esté en camino."
        ),
        referencia_id=orden_id,
    )


@shared_task
def notificar_orden_cancelada(usuario_id, orden_id, numero_orden):
    """
    Notifica al usuario que su orden fue cancelada.
    Se dispara desde Orden.cancelar().
    """
    crear_notificacion.delay(
        usuario_id=usuario_id,
        tipo="orden_cancelada",
        titulo="Tu orden fue cancelada",
        mensaje=(
            f"Tu orden {numero_orden} fue cancelada. "
            f"El stock de los productos fue restituido."
        ),
        referencia_id=orden_id,
    )


@shared_task
def notificar_pago_aprobado(usuario_id, pago_id, monto):
    """
    Notifica al usuario que su pago fue aprobado.
    Se dispara desde Pago.marcar_aprobado().
    """
    crear_notificacion.delay(
        usuario_id=usuario_id,
        tipo="pago_aprobado",
        titulo="¡Pago aprobado!",
        mensaje=(
            f"Tu pago de Gs. {int(monto):,}".replace(",", ".") +
            " fue aprobado exitosamente."
        ),
        referencia_id=pago_id,
    )


@shared_task
def notificar_pago_rechazado(usuario_id, pago_id):
    """
    Notifica al usuario que su pago fue rechazado.
    Se dispara desde Pago.marcar_rechazado().
    """
    crear_notificacion.delay(
        usuario_id=usuario_id,
        tipo="pago_rechazado",
        titulo="Tu pago fue rechazado",
        mensaje=(
            "Tu pago no pudo ser procesado. "
            "Por favor intentá nuevamente o usá otro método de pago."
        ),
        referencia_id=pago_id,
    )