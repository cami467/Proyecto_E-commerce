from django.contrib.auth.models import AbstractUser
from django.db import models


class Usuario(AbstractUser):
    """
    Usuario personalizado que extiende el modelo base de Django.
    Campos extra: telefono y avatar.
    """
    telefono = models.CharField(
        max_length=20,
        blank=True,
        null=True,
        help_text="Numero de contacto del usuario"
    )
    avatar = models.ImageField(
        upload_to="avatars/",
        blank=True,
        null=True,
        help_text="Foto de perfil del usuario"
    )

    class Meta:
        verbose_name = "Usuario"
        verbose_name_plural = "Usuarios"
        ordering = ["-date_joined"]


    # Método especial que define la representación en texto del objeto Usuario.
    def __str__(self):
        return self.email or self.username or f"Usuario {self.pk}"
    
    
    # - Si ambos están vacíos, retorna el username como alternativa.
    @property
    def nombre_completo(self):
        """Retorna el nombre completo del usuario."""
        return f"{self.first_name} {self.last_name}".strip() or self.username