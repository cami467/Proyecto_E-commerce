from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

Usuario = get_user_model()


class UsuarioModelTestCase(TestCase):
    """
    Suite de pruebas QA para el modelo Usuario.

    Cubre:
        - Creacion de usuario con create_user (password hasheado).
        - El email debe ser unico.
        - nombre_completo se construye a partir de first_name/last_name.
    """

    def test_create_user_hashea_la_password(self):
        """create_user() nunca guarda la password en texto plano."""
        usuario = Usuario.objects.create_user(
            username="hash_test",
            email="hash_test@tienda.com",
            password="Password123"
        )
        self.assertNotEqual(usuario.password, "Password123")
        self.assertTrue(usuario.check_password("Password123"))

    def test_email_duplicado_no_permitido(self):
        """No se pueden crear dos usuarios con el mismo email."""
        Usuario.objects.create_user(
            username="usuario_uno",
            email="duplicado@tienda.com",
            password="Password123"
        )
        with self.assertRaises(Exception):
            Usuario.objects.create_user(
                username="usuario_dos",
                email="duplicado@tienda.com",
                password="Password123"
            )

    def test_nombre_completo_se_construye_correctamente(self):
        """nombre_completo combina first_name y last_name."""
        usuario = Usuario.objects.create_user(
            username="nombre_test",
            email="nombre_test@tienda.com",
            password="Password123",
            first_name="Camila",
            last_name="Benitez"
        )
        self.assertEqual(usuario.nombre_completo, "Camila Benitez")


class AutenticacionAPITestCase(APITestCase):
    """
    Suite de pruebas QA para los endpoints de autenticacion JWT.

    Cubre:
        - Registro exitoso de un nuevo usuario.
        - Registro con email duplicado falla con 400.
        - Login exitoso retorna access y refresh token.
        - Login con password incorrecta falla con 401.
        - Acceder a un endpoint protegido sin token falla con 401.
        - Acceder a un endpoint protegido con token valido funciona.
    """

    def setUp(self):
        self.usuario_existente = Usuario.objects.create_user(
            username="usuario_login_test",
            email="usuario_login_test@tienda.com",
            password="Password123!"
        )
        self.usuario_existente.is_active = True
        self.usuario_existente.save()
        
    def test_registro_rechaza_password_debil(self):
        """El registro rechaza passwords cortas, sin mayuscula y sin caracter especial."""
        response = self.client.post(reverse("registro"), {
            "username": "camila",
            "email": "camila@tienda.com",
            "password": "cami123",
            "password2": "cami123",
            "telefono": "0981123456",
        })
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("password", response.data)
        
    def test_registro_rechaza_telefono_con_letras(self):
        """El registro no acepta telefonos con letras."""
        response = self.client.post(reverse("registro"), {
            "username": "telefono_test",
            "email": "telefono_test@tienda.com",
            "password": "Password123!",
            "password2": "Password123!",
            "telefono": "abc123",
        })
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("telefono", response.data)
        
    def test_registro_acepta_email_con_alias_y_subdominio(self):
        """Los alias y subdominios son emails validos y no deben bloquearse."""
        response = self.client.post(reverse("registro"), {
            "username": "email_valido",
            "email": "user+test@sub.domain.com",
            "password": "Password123!",
            "password2": "Password123!",
            "telefono": "0981123456",
        })
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(Usuario.objects.filter(email="user+test@sub.domain.com").exists())
        
    def test_registro_rechaza_password_demasiado_largo(self):
        """El registro rechaza contraseñas de mas de 64 caracteres."""
        password_largo = "A" + "a" * 65 + "1!"
        response = self.client.post(reverse("registro"), {
            "username": "password_largo",
            "email": "password_largo@tienda.com",
            "password": password_largo,
            "password2": password_largo,
            "telefono": "0981123456",
        })
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("password", response.data)
        
    def test_registro_normaliza_telefono_paraguayo(self):
        """El registro guarda telefonos paraguayos en formato internacional normalizado."""
        response = self.client.post(reverse("registro"), {
            "username": "telefono_ok",
            "email": "telefono_ok@tienda.com",
            "password": "Password123!",
            "password2": "Password123!",
            "telefono": "0981 123-456",
        })
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        usuario = Usuario.objects.get(username="telefono_ok")
        self.assertEqual(usuario.telefono, "+595981123456")

    def test_login_exitoso_retorna_tokens(self):
        """Login con credenciales correctas retorna access y refresh."""
        response = self.client.post(reverse("token_obtain_pair"), {
            "email": "usuario_login_test@tienda.com",
            "password": "Password123!",
        })
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access", response.data)
        self.assertIn("refresh", response.data)
        self.assertIn("usuario", response.data)
        self.assertEqual(response.data["usuario"]["email"], "usuario_login_test@tienda.com")
        self.assertNotIn("username", response.data["usuario"])

    def test_login_con_password_incorrecta_falla(self):
        """Login con password incorrecta retorna 401."""
        response = self.client.post(reverse("token_obtain_pair"), {
            "email": "usuario_login_test@tienda.com",
            "password": "PasswordIncorrecta",
        })
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


    @override_settings(
        REST_FRAMEWORK={
            "DEFAULT_AUTHENTICATION_CLASSES": [
                "rest_framework_simplejwt.authentication.JWTAuthentication",
            ],
            "DEFAULT_PERMISSION_CLASSES": [
                "rest_framework.permissions.IsAuthenticated",
            ],
            "DEFAULT_THROTTLE_CLASSES": [
                "rest_framework.throttling.ScopedRateThrottle",
            ],
            "DEFAULT_THROTTLE_RATES": {
                "login": "3/minute",
            },
        },
        CACHES={
            "default": {
                "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
                "LOCATION": "test-login-throttle",
            }
        },
    )
    @override_settings(
        CACHES={
            "default": {
                "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
                "LOCATION": "test-login-throttle",
            }
        },
    )
    def test_login_limita_intentos_repetidos(self):
        """El login debe limitar intentos repetidos para mitigar fuerza bruta."""
        from django.core.cache import cache
        from rest_framework.throttling import ScopedRateThrottle

        cache.clear()

        # override_settings NO actualiza THROTTLE_RATES porque DRF lo copia
        # como atributo de clase una sola vez al importar el modulo.
        # Por eso se parchea directamente aqui, y se restaura al final.
        rates_originales = ScopedRateThrottle.THROTTLE_RATES
        ScopedRateThrottle.THROTTLE_RATES = {"login": "5/minute"}

        try:
            for _ in range(5):
                response = self.client.post(reverse("token_obtain_pair"), {
                    "email": "usuario_login_test@tienda.com",
                    "password": "PasswordIncorrecta",
                })
                self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

            response = self.client.post(reverse("token_obtain_pair"), {
                "email": "usuario_login_test@tienda.com",
                "password": "PasswordIncorrecta",
            })

            self.assertEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)
        finally:
            ScopedRateThrottle.THROTTLE_RATES = rates_originales

        self.assertEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)
    def test_acceder_a_perfil_sin_token_falla(self):
        """Acceder al perfil sin autenticacion retorna 401."""
        response = self.client.get(reverse("perfil"))
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_acceder_a_perfil_con_token_valido_funciona(self):
        """Con un token valido, el endpoint de perfil retorna 200."""
        login_response = self.client.post(reverse("token_obtain_pair"), {
            "email": "usuario_login_test@tienda.com",
            "password": "Password123!",
        })
        access_token = login_response.data["access"]
        
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {access_token}")
        response = self.client.get(reverse("perfil"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["email"], "usuario_login_test@tienda.com")
        self.assertNotIn("username", response.data)
        
    def test_registro_sin_username_genera_username_interno(self):
        """El registro publico no debe obligar al cliente a elegir username."""
        response = self.client.post(reverse("registro"), {
            "email": "cliente.nuevo+test@sub.tienda.com",
            "password": "Password123!",
            "password2": "Password123!",
            "telefono": "0981123456",
        })

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        usuario = Usuario.objects.get(email="cliente.nuevo+test@sub.tienda.com")
        self.assertTrue(usuario.username)

    def test_registro_sin_username_no_colisiona_si_email_local_repetido(self):
        """Si dos emails tienen la misma parte local, el username interno debe seguir siendo unico."""
        primer_response = self.client.post(reverse("registro"), {
            "email": "cliente@tienda.com",
            "password": "Password123!",
            "password2": "Password123!",
        })
        segundo_response = self.client.post(reverse("registro"), {
            "email": "cliente@sub.tienda.com",
            "password": "Password123!",
            "password2": "Password123!",
        })

        self.assertEqual(primer_response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(segundo_response.status_code, status.HTTP_201_CREATED)
        usernames = list(Usuario.objects.filter(email__startswith="cliente@").values_list("username", flat=True))
        self.assertEqual(len(usernames), len(set(usernames)))
    def test_registro_normaliza_email_nombre_y_apellido(self):
        """El registro debe limpiar espacios y guardar el email en minusculas."""
        response = self.client.post(reverse("registro"), {
            "email": "  Cliente.Normalizado@GMAIL.COM  ",
            "first_name": "  María   José  ",
            "last_name": "  Benítez   López  ",
            "password": "Password123!",
            "password2": "Password123!",
            "telefono": "0981123456",
        })

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        usuario = Usuario.objects.get(email="cliente.normalizado@gmail.com")
        self.assertEqual(usuario.first_name, "María José")
        self.assertEqual(usuario.last_name, "Benítez López")

    def test_registro_rechaza_nombre_con_numeros_o_simbolos(self):
        """El registro no debe aceptar nombres falsos como Carlos123."""
        response = self.client.post(reverse("registro"), {
            "email": "nombre_invalido@tienda.com",
            "first_name": "Carlos123",
            "last_name": "@@@@@",
            "password": "Password123!",
            "password2": "Password123!",
            "telefono": "0981123456",
        })

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("first_name", response.data)
        self.assertIn("last_name", response.data)

    def test_perfil_no_permite_modificar_username_interno(self):
        """El username queda como dato interno y no debe editarse desde el perfil publico."""
        login_response = self.client.post(reverse("token_obtain_pair"), {
            "email": "usuario_login_test@tienda.com",
            "password": "Password123!",
        })
        access_token = login_response.data["access"]
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {access_token}")
        response = self.client.patch(reverse("perfil"), {
            "username": "nuevo_username_no_permitido",
            "first_name": "Camila",
            "last_name": "Benítez",
        })

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.usuario_existente.refresh_from_db()
        self.assertEqual(self.usuario_existente.username, "usuario_login_test")
        self.assertEqual(self.usuario_existente.first_name, "Camila")
        self.assertEqual(self.usuario_existente.last_name, "Benítez")
        self.assertIn("access", login_response.data)


    def test_perfil_rechaza_nombre_invalido_al_editar(self):
        """El perfil debe aplicar las mismas reglas de nombres que el registro."""
        login_response = self.client.post(reverse("token_obtain_pair"), {
            "email": "usuario_login_test@tienda.com",
            "password": "Password123!",
        })
        access_token = login_response.data["access"]
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {access_token}")

        response = self.client.patch(reverse("perfil"), {
            "first_name": "Carlos123",
            "last_name": "@@@@@",
        })

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("first_name", response.data)
        self.assertIn("last_name", response.data)


class UsuarioAdminListAPITestCase(APITestCase):
    """
    Suite de pruebas QA para el endpoint de listado de usuarios
    para administradores (GET /api/usuarios/).

    Cubre:
        - Un admin (is_staff=True) puede listar usuarios.
        - Un cliente normal no puede acceder (403).
        - Un usuario no autenticado no puede acceder (401).
    """

    def setUp(self):
        self.admin = Usuario.objects.create_user(
            username="admin_test",
            email="admin@gmail.com",
            password="Password123!",
            is_staff=True,
        )
        self.cliente = Usuario.objects.create_user(
            username="cliente_test_admin_list",
            email="cliente@gmail.com",
            password="Password123!",
        )
        self.url = reverse("usuarios-admin-list")

    def test_admin_puede_listar_usuarios(self):
        self.client.force_authenticate(user=self.admin)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_cliente_no_puede_listar_usuarios(self):
        self.client.force_authenticate(user=self.cliente)
        response = self.client.get(self.url)
        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN,
        )

    def test_usuario_no_autenticado_no_puede_listar(self):
        response = self.client.get(self.url)
        self.assertEqual(
            response.status_code,
            status.HTTP_401_UNAUTHORIZED,
        )