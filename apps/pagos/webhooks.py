import stripe
from django.conf import settings
from django.http import HttpResponse
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt

from .models import Pago


def _campo(obj, clave, default=None):
    """
    Lee un campo de un objeto de Stripe (StripeObject) de forma segura.

    Los objetos de Stripe soportan indexado tipo diccionario
    (obj["clave"]), pero dependiendo de la version del SDK instalada
    NO siempre exponen un metodo .get() real: a veces obj.get(...)
    termina cayendo en el __getattr__ generico de StripeObject, que
    busca una clave literal "get" dentro del objeto y no la
    encuentra, tirando AttributeError en lugar de simplemente
    devolver el default.

    Por eso todo este archivo usa esta funcion en lugar de .get()
    directo sobre objetos de Stripe, para no depender de un detalle
    de implementacion que cambia entre versiones del SDK.
    """
    try:
        valor = obj[clave]
    except (KeyError, TypeError):
        return default
    return default if valor is None else valor


@method_decorator(csrf_exempt, name="dispatch")
class StripeWebhookView(View):
    """
    Recibe eventos de Stripe para confirmar el estado real de un pago.

    Stripe es la única fuente de verdad sobre si un pago con tarjeta
    se completó: el frontend puede reportar éxito antes de tiempo
    (por ejemplo, si el usuario cierra la pestaña en medio de una
    autenticación 3D Secure), así que el estado definitivo del Pago
    SIEMPRE se actualiza acá, nunca a partir de lo que devuelve
    stripe.confirmPayment() en el navegador.

    Es una vista Django plana (no un @action del ViewSet) y con
    csrf_exempt porque Stripe no puede autenticarse con nuestro JWT
    ni mandar un token CSRF. La seguridad no depende de quién hace
    el request, sino de que la firma del payload sea válida — por
    eso construct_event() es el único paso que realmente protege
    este endpoint.

    Idempotencia: Stripe puede reenviar el mismo evento más de una
    vez. pago.esta_pendiente ya filtra ese caso (si el pago ya fue
    procesado, no se vuelve a tocar), y marcar_aprobado()/
    marcar_rechazado() son idempotentes por diseño.
    """

    def post(self, request, *args, **kwargs):
        payload = request.body
        firma = request.META.get("HTTP_STRIPE_SIGNATURE", "")

        try:
            evento = stripe.Webhook.construct_event(
                payload, firma, settings.STRIPE_WEBHOOK_SECRET
            )
        except ValueError:
            # Payload malformado
            return HttpResponse(status=400)
        except stripe.error.SignatureVerificationError:
            # Firma inválida: alguien intentó mandar un evento falso
            return HttpResponse(status=400)

        tipo_evento = evento["type"]

        eventos_relevantes = (
            "payment_intent.succeeded",
            "payment_intent.payment_failed",
            "payment_intent.processing",
        )
        if tipo_evento not in eventos_relevantes:
            # Confirmamos 200 igual, para que Stripe no siga
            # reintentando eventos que no nos interesan.
            return HttpResponse(status=200)

        payment_intent = evento["data"]["object"]
        pago = self._buscar_pago(payment_intent)

        if pago is None:
            # No es un error de firma ni de formato — simplemente no
            # tenemos ese pago (puede pasar en pruebas manuales desde
            # el dashboard de Stripe). Devolvemos 200 para no generar
            # reintentos infinitos de un evento que nunca vamos a
            # poder resolver.
            return HttpResponse(status=200)

        if not pago.esta_pendiente:
            return HttpResponse(status=200)

        respuesta = {
            "webhook_event": tipo_evento,
            "payment_intent_id": _campo(payment_intent, "id"),
            "status": _campo(payment_intent, "status"),
        }

        if tipo_evento == "payment_intent.succeeded":
            pago.marcar_aprobado(
                id_transaccion=_campo(payment_intent, "id") or pago.id_transaccion,
                respuesta=respuesta,
            )
        elif tipo_evento == "payment_intent.payment_failed":
            pago.marcar_rechazado(respuesta=respuesta)
        elif tipo_evento == "payment_intent.processing":
            # Todavía no hay resultado definitivo (ej: métodos de pago
            # que tardan, como algunas transferencias locales que
            # Stripe soporta). Solo dejamos constancia, sin cambiar
            # el estado del pago.
            pago.respuesta_pasarela = respuesta
            pago.save(update_fields=["respuesta_pasarela", "fecha_actualizacion"])

        return HttpResponse(status=200)

    def _buscar_pago(self, payment_intent) -> Pago | None:
        """
        Busca el Pago correspondiente a un PaymentIntent.

        Primero por metadata.pago_id (nuestro UUID, la forma más
        confiable). Como respaldo, busca por id_transaccion de forma
        case-insensitive, porque Pago.clean() normaliza ese campo a
        mayúsculas y el id de Stripe llega en minúsculas.
        """
        metadata = _campo(payment_intent, "metadata", {}) or {}
        pago_id = _campo(metadata, "pago_id")

        if pago_id:
            pago = Pago.objects.filter(pk=pago_id).first()
            if pago:
                return pago

        payment_intent_id = _campo(payment_intent, "id", "")
        if not payment_intent_id:
            return None

        return Pago.objects.filter(
            pasarela=Pago.Pasarela.STRIPE,
            id_transaccion__iexact=payment_intent_id,
        ).first()