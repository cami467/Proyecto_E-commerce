from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from .models import Notificacion
from .tasks import (
    crear_notificacion,
    notificar_orden_confirmada,
    notificar_orden_cancelada,
    notificar_pago_aprobado,
    notificar_pago_rechazado,
)

Usuario = get_user_model()


@override_settings(CELERY_TASK_ALWAYS_EAGER=True, CELERY_TASK_EAGER_PROPAGATES=True)
class NotificacionTasksTestCase(TestCase):
    """
    Suite de pruebas QA para las tareas asincronas de notificaciones.

    Usa CELERY_TASK_ALWAYS_EAGER=True para que las tareas se ejecuten
    de forma sincrona durante el test, sin necesitar Redis ni un
    worker de Celery corriendo.

    Cubre:
        - crear_notificacion() crea el registro correctamente.
        - crear_notificacion() con usuario inexistente no falla.
        - notificar_orden_confirmada() crea notificacion con mensaje correcto.
        - notificar_orden_cancelada() crea notificacion con mensaje correcto.
        - notificar_pago_aprobado() crea notificacion con mensaje correcto.
        - notificar_pago_rechazado() crea notificacion con mensaje correcto.
        - marcar_leida() actualiza el estado correctamente.
    """

    def setUp(self):
        self.usuario = Usuario.objects.create_user(
            username="notif_test",
            email="notif_test@tienda.com",
            password="Password123"
        )

    def test_crear_notificacion_crea_el_registro(self):
        """crear_notificacion() persiste una Notificacion en la base de datos."""
        crear_notificacion.delay(
            usuario_id=self.usuario.pk,
            tipo="sistema",
            titulo="Notificacion de prueba",
            mensaje="Este es un mensaje de prueba.",
        )

        self.assertEqual(Notificacion.objects.count(), 1)
        notificacion = Notificacion.objects.first()
        self.assertEqual(notificacion.usuario, self.usuario)
        self.assertEqual(notificacion.titulo, "Notificacion de prueba")
        self.assertFalse(notificacion.leida)

    def test_crear_notificacion_con_usuario_inexistente_no_falla(self):
        """Si el usuario no existe, la tarea retorna sin crear nada ni lanzar excepcion."""
        resultado = crear_notificacion.delay(
            usuario_id=999999,
            tipo="sistema",
            titulo="No deberia crearse",
            mensaje="Usuario inexistente.",
        )
        self.assertEqual(Notificacion.objects.count(), 0)
        self.assertIn("no existe", resultado.result)

    def test_notificar_orden_confirmada_crea_mensaje_correcto(self):
        """La notificacion de orden confirmada incluye numero y total formateado."""
        notificar_orden_confirmada.delay(
            usuario_id=self.usuario.pk,
            orden_id="abc-123",
            numero_orden="#ABC12345",
            total=150000,
        )

        notificacion = Notificacion.objects.first()
        self.assertEqual(notificacion.tipo, Notificacion.Tipo.ORDEN_CONFIRMADA)
        self.assertIn("#ABC12345", notificacion.mensaje)
        self.assertIn("150.000", notificacion.mensaje)
        self.assertEqual(notificacion.referencia_id, "abc-123")

    def test_notificar_orden_cancelada_crea_mensaje_correcto(self):
        """La notificacion de orden cancelada incluye el numero de orden."""
        notificar_orden_cancelada.delay(
            usuario_id=self.usuario.pk,
            orden_id="def-456",
            numero_orden="#DEF67890",
        )

        notificacion = Notificacion.objects.first()
        self.assertEqual(notificacion.tipo, Notificacion.Tipo.ORDEN_CANCELADA)
        self.assertIn("#DEF67890", notificacion.mensaje)

    def test_notificar_pago_aprobado_crea_mensaje_correcto(self):
        """La notificacion de pago aprobado incluye el monto formateado."""
        notificar_pago_aprobado.delay(
            usuario_id=self.usuario.pk,
            pago_id="pago-789",
            monto=75000,
        )

        notificacion = Notificacion.objects.first()
        self.assertEqual(notificacion.tipo, Notificacion.Tipo.PAGO_APROBADO)
        self.assertIn("75.000", notificacion.mensaje)

    def test_notificar_pago_rechazado_crea_notificacion(self):
        """La notificacion de pago rechazado se crea correctamente."""
        notificar_pago_rechazado.delay(
            usuario_id=self.usuario.pk,
            pago_id="pago-000",
        )

        notificacion = Notificacion.objects.first()
        self.assertEqual(notificacion.tipo, Notificacion.Tipo.PAGO_RECHAZADO)

    def test_marcar_leida_actualiza_estado(self):
        """marcar_leida() cambia leida a True y registra fecha_leida."""
        notificacion = Notificacion.objects.create(
            usuario=self.usuario,
            tipo=Notificacion.Tipo.SISTEMA,
            titulo="Test de lectura",
            mensaje="Mensaje de prueba.",
        )
        self.assertFalse(notificacion.leida)
        self.assertIsNone(notificacion.fecha_leida)

        notificacion.marcar_leida()

        self.assertTrue(notificacion.leida)
        self.assertIsNotNone(notificacion.fecha_leida)