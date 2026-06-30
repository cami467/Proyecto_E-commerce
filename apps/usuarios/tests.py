from django.contrib.auth import get_user_model
from django.test import TestCase
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
            password="Password123"
        )
        
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
            "username": "usuario_login_test",
            "password": "Password123",
        })
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access", response.data)
        self.assertIn("refresh", response.data)

    def test_login_con_password_incorrecta_falla(self):
        """Login con password incorrecta retorna 401."""
        response = self.client.post(reverse("token_obtain_pair"), {
            "username": "usuario_login_test",
            "password": "PasswordIncorrecta",
        })
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_acceder_a_perfil_sin_token_falla(self):
        """Acceder al perfil sin autenticacion retorna 401."""
        response = self.client.get(reverse("perfil"))
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_acceder_a_perfil_con_token_valido_funciona(self):
        """Con un token valido, el endpoint de perfil retorna 200."""
        login_response = self.client.post(reverse("token_obtain_pair"), {
            "username": "usuario_login_test",
            "password": "Password123",
        })
        access_token = login_response.data["access"]

        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {access_token}")
        response = self.client.get(reverse("perfil"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["username"], "usuario_login_test")