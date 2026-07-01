from rest_framework import serializers
from rest_framework import serializers as drf_serializers
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.validators import UniqueValidator
from drf_spectacular.utils import extend_schema_field
from django.contrib.auth import get_user_model, password_validation
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from django.contrib.auth import authenticate
import re
import unicodedata

Usuario = get_user_model()

USERNAME_REGEX = re.compile(r"^[a-zA-Z0-9_.-]+$")
TELEFONO_CHARS_REGEX = re.compile(r"^[+0-9()\s-]+$")
TELEFONO_NORMALIZADO_REGEX = re.compile(r"^\+5959\d{8}$")
PASSWORD_ESPECIAL_REGEX = re.compile(r"[^A-Za-z0-9]")
NOMBRE_MIN_LENGTH = 2
NOMBRE_MAX_LENGTH = 50

def normalizar_espacios(value):
    """Elimina espacios innecesarios y compacta espacios internos."""
    return re.sub(r"\s+", " ", value.strip())


def validar_nombre_persona(value, nombre_campo):
    """
    Valida nombres y apellidos reales sin bloquear acentos.

    Permitido:
        - Letras unicode: Maria, María, José, Ña        - Espacios internos: María José
        - Guion: José-Luis
        - Apostrofe: O'Connor

    No permitido:
        - Números: Carlos123
        - Emojis
        - Símbolos repetidos o nombres formados solo por signos
    """
    if value in (None, ""):
        return ""

    value = normalizar_espacios(value)

    if not (NOMBRE_MIN_LENGTH <= len(value) <= NOMBRE_MAX_LENGTH):
        raise serializers.ValidationError(
            f"{nombre_campo} debe tener entre {NOMBRE_MIN_LENGTH} y {NOMBRE_MAX_LENGTH} caracteres."
        )

    tiene_letra = False
    caracter_anterior = ""

    for caracter in value:
        categoria = unicodedata.category(caracter)
        es_letra = categoria.startswith("L")
        es_espacio = caracter == " "
        es_separador_valido = caracter in "-'"

        if es_letra:
            tiene_letra = True
        elif not (es_espacio or es_separador_valido):
            raise serializers.ValidationError(
                f"{nombre_campo} solo puede contener letras, espacios, guiones o apostrofes."
            )

        if caracter in " -'" and caracter_anterior in " -'":
            raise serializers.ValidationError(
                f"{nombre_campo} no puede contener separadores consecutivos."
            )

        caracter_anterior = caracter

    if not tiene_letra:
        raise serializers.ValidationError(
            f"{nombre_campo} debe contener al menos una letra."
        )

    if value[0] in "-'" or value[-1] in "-'":
        raise serializers.ValidationError(
            f"{nombre_campo} no puede comenzar ni terminar con guion o apostrofe."
        )

    return value


def generar_username_unico(email):
    """
    Genera un username interno a partir del email.

    En el contrato publico del ecommerce el usuario inicia sesion con email,
    por lo tanto el username no debe ser un dato obligatorio para el cliente.
    Django lo sigue necesitando internamente porque el modelo hereda de AbstractUser.
    """
    parte_local = email.split("@", 1)[0]
    base = re.sub(r"[^a-zA-Z0-9_.-]", "", parte_local).strip("._-").lower()

    if not base:
        base = "usuario"

    base = base[:24]
    username = base
    contador = 1

    while Usuario.objects.filter(username__iexact=username).exists():
        sufijo = str(contador)
        username = f"{base[:30 - len(sufijo)]}{sufijo}"
        contador += 1

    return username

# ==============================================================================
# SERIALIZER DE REGISTRO
# ==============================================================================

class RegistroSerializer(serializers.ModelSerializer):
    """
    Serializer para registro de nuevos usuarios.
    Valida email unico, contraseña segura y coincidencia de passwords.
    """
    email = serializers.EmailField(
        required=True,
        validators=[
            UniqueValidator(
                queryset=Usuario.objects.all(),
                lookup="iexact",
                message="Ya existe una cuenta con este email."
            )
        ]
    )
    username = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=30,
        help_text="Campo opcional. Si no se envia, se genera automaticamente desde el email."
    )
    first_name = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=NOMBRE_MAX_LENGTH
    )
    last_name = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=NOMBRE_MAX_LENGTH
    )
    password = serializers.CharField(
        write_only=True,
        min_length=10,
        max_length=64,
        trim_whitespace=False,
        style={"input_type": "password"}
   )
    password2 = serializers.CharField(
        write_only=True,
        style={"input_type": "password"}
    )

    class Meta:
        model = Usuario
        fields = [
            "username",
            "email",
            "first_name",
            "last_name",
            "password",
            "password2",
            "telefono",
        ]  
    
    def validate_first_name(self, value):
        """Valida y normaliza el nombre del cliente."""
        return validar_nombre_persona(value, "El nombre")

    def validate_last_name(self, value):
        """Valida y normaliza el apellido del cliente."""
        return validar_nombre_persona(value, "El apellido") 
        
    def validate_username(self, value):
        """Valida un nombre de usuario seguro y consistente."""
        value = value.strip()
        
        if not value:
            return value

        if len(value) < 3 or len(value) > 30:
            raise serializers.ValidationError(
                "El usuario debe tener entre 3 y 30 caracteres."
            )
                                                                                                                
        if not USERNAME_REGEX.fullmatch(value):
            raise serializers.ValidationError(
                "El usuario solo puede contener letras, números, punto, guion y guion bajo."
            )

        if Usuario.objects.filter(username__iexact=value).exists():
            raise serializers.ValidationError(
                "Ya existe una cuenta con este nombre de usuario."
            )

        return value

    def validate_email(self, value):
        """Normaliza el email sin bloquear formatos validos como alias o subdominios."""
        value = value.strip().lower()
        if len(value) > 254:
            raise serializers.ValidationError("El email no puede superar 254 caracteres.")
        return value
    
    def validate_first_name(self, value):
        """Valida y normaliza el nombre al editar perfil."""
        return validar_nombre_persona(value, "El nombre")

    def validate_last_name(self, value):
        """Valida y normaliza el apellido al editar perfil."""
        return validar_nombre_persona(value, "El apellido")
    
    def validate_telefono(self, value):
        """Valida y normaliza telefonos paraguayos al formato +5959XXXXXXXX."""
        if value in (None, ""):
            return value

        value = value.strip()
        if not TELEFONO_CHARS_REGEX.fullmatch(value):
            raise serializers.ValidationError(
                "El telefono solo puede contener numeros, espacios, guiones, parentesis o el prefijo +."
            )

        digitos = re.sub(r"\D", "", value)

        if digitos.startswith("0") and len(digitos) == 10:
            normalizado = "+595" + digitos[1:]
        elif digitos.startswith("595") and len(digitos) == 12:
            normalizado = "+" + digitos
        else:
            raise serializers.ValidationError(
                "Ingrese un telefono paraguayo valido. Ejemplo: 0981123456 o +595981123456."
            )

        if not TELEFONO_NORMALIZADO_REGEX.fullmatch(normalizado):
            raise serializers.ValidationError(
                "Ingrese un telefono paraguayo valido. Ejemplo: 0981123456 o +595981123456."
            )
            
        return normalizado

    def validate_password(self, value):
        """Aplica validaciones de seguridad para contraseñas de usuarios."""
        try:
            password_validation.validate_password(value)
        except DjangoValidationError as e:
            raise serializers.ValidationError(list(e.messages))

        errores = []
        if not any(char.islower() for char in value):
            errores.append("La contraseña debe incluir al menos una letra minuscula.")
        if not any(char.isupper() for char in value):
            errores.append("La contraseña debe incluir al menos una letra mayuscula.")
        if not any(char.isdigit() for char in value):
            errores.append("La contraseña debe incluir al menos un numero.")
        if not PASSWORD_ESPECIAL_REGEX.search(value):
            errores.append("La contraseña debe incluir al menos un caracter especial.")

        if errores:
            raise serializers.ValidationError(errores)

        return value

    def validate(self, data):
        """Verifica coincidencia de contraseñas y evita datos personales dentro de la clave."""
        password = data.get("password")
        password2 = data.get("password2")

        if password and password2 and password != password2:
            raise serializers.ValidationError({
                "password2": "Las contraseñas no coinciden."
            })

        if password:
            password_lower = password.lower()
            datos_personales = [
                data.get("username", ""),
                data.get("email", "").split("@")[0],
                re.sub(r"\D", "", data.get("telefono") or ""),
            ]
            for dato in datos_personales:
                dato = str(dato).strip().lower()
                if dato and len(dato) >= 4 and dato in password_lower:
                    raise serializers.ValidationError({
                        "password": "La contraseña no debe contener datos personales del usuario."
                    })

        return data

    def create(self, validated_data):
        """Crea el usuario con contraseña hasheada de forma escalable."""
        validated_data.pop("password2", None)
        if not validated_data.get("username"):
            validated_data["username"] = generar_username_unico(validated_data["email"])
        return Usuario.objects.create_user(**validated_data)


# ==============================================================================
# SERIALIZER DE PERFIL
# ==============================================================================

class UsuarioSerializer(serializers.ModelSerializer):
    """
    Serializer para ver y editar el perfil del usuario autenticado.
    Incluye validacion de email unico excluyendo al usuario actual.
    """
    nombre_completo = serializers.SerializerMethodField()
    email = serializers.EmailField(required=True)

    class Meta:
        model = Usuario
        fields = [
            "id",
            "username",
            "email",
            "first_name",
            "last_name",
            "nombre_completo",
            "telefono",
            "avatar",
            "date_joined",
        ]
        read_only_fields = ["id","username", "date_joined"]

    @extend_schema_field(drf_serializers.CharField(allow_null=True))
    def get_nombre_completo(self, obj):
        """
        Genera nombre completo dinamicamente.
        Usa username como fallback si no hay nombre.
        """
        nombre = f"{obj.first_name} {obj.last_name}".strip()
        return nombre if nombre else obj.username

    def validate_email(self, value):
        """
        Normaliza email y verifica unicidad excluyendo al usuario actual.
        Funciona tanto en creacion como en edicion.
        """
        value = value.strip().lower()
        if len(value) > 254:
            raise serializers.ValidationError("El email no puede superar 254 caracteres.")
        queryset = Usuario.objects.filter(email__iexact=value)
        if self.instance:
            queryset = queryset.exclude(pk=self.instance.pk)
        if queryset.exists():
            raise serializers.ValidationError(
                "Ya existe una cuenta con este email."
            )
        return value
    
    def validate_telefono(self, value):
        """Reutiliza la misma regla de telefono del registro al editar perfil."""
        return RegistroSerializer().validate_telefono(value)
    


# ==============================================================================
# SERIALIZER DE LOGIN POR EMAIL
# ==============================================================================

class EmailTokenObtainPairSerializer(TokenObtainPairSerializer):
    """
    Serializer JWT personalizado para iniciar sesión con email y password.
    Devuelve access y refresh tokens.
    """
    username_field = "email"

    email = serializers.EmailField(write_only=True, required=True)
    password = serializers.CharField(write_only=True, required=True, style={"input_type": "password"})

    def validate(self, attrs):
        email = attrs.get("email", "").strip().lower()
        password = attrs.get("password")

        try:
            usuario = Usuario.objects.get(email__iexact=email)
        except Usuario.DoesNotExist:
            raise AuthenticationFailed("Credenciales inválidas.")

        if not usuario.is_active:
            raise AuthenticationFailed("La cuenta se encuentra inactiva.")

        self.user = authenticate(
            request=self.context.get("request"),
            username=usuario.get_username(),
            password=password,
        )

        if self.user is None:
            raise AuthenticationFailed("Credenciales inválidas.")

        refresh = self.get_token(self.user)

        return {
            "refresh": str(refresh),
            "access": str(refresh.access_token),
        }



# ==============================================================================
# SERIALIZER DE LOGOUT
# ==============================================================================

class LogoutSerializer(serializers.Serializer):
    """
    Serializer para invalidar (blacklistear) un refresh token al cerrar sesión.

    El frontend debe enviar el refresh token que tiene almacenado.
    Una vez blacklisteado, ese token ya no puede usarse para generar
    nuevos access tokens, incluso si todavia no expiro.
    """
    refresh = serializers.CharField(
        help_text="Refresh token a invalidar."
    )
    
    def validate_refresh(self, value):
        """Valida que el refresh token tenga un formato mínimo válido."""
        if not value or len(value) < 20:
            raise serializers.ValidationError("El token de refresco no es válido.")
        return value