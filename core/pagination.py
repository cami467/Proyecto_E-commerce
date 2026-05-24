from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response


class BasePagination(PageNumberPagination):
    """
    Clase base para centralizar la estructura de respuesta paginada.
    """
    def get_paginated_response(self, data):
        return Response({
            "total": self.page.paginator.count,
            "paginas": self.page.paginator.num_pages,
            "pagina_actual": self.page.number,
            "siguiente": self.get_next_link(),
            "anterior": self.get_previous_link(),
            "resultados": data
        })


class PaginacionEstandar(BasePagination):
    """
    Paginacion estandar para todos los endpoints principales.
    - 20 elementos por pagina por defecto
    """
    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100


class PaginacionPequena(BasePagination):
    """
    Paginacion reducida para listas cortas (categorias, cupones).
    - 10 elementos por pagina por defecto
    """
    page_size = 10
    page_size_query_param = "page_size"
    max_page_size = 50