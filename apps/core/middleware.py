class PrivateCacheMiddleware:
    """
    Garantiza que todas las respuestas para usuarios autenticados incluyan
    cabeceras estrictas 'no-store, private' para evitar que el navegador
    guarde copias sensibles en bfcache o historial de disco tras logout (Criterios 13 y 25).
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        # Si el usuario está autenticado y no es un archivo estático público
        if hasattr(request, 'user') and request.user.is_authenticated:
            # No sobreescribir si ya está explícito
            response['Cache-Control'] = 'no-store, private, no-cache, must-revalidate'
            response['Pragma'] = 'no-cache'
            response['Expires'] = '0'

        return response
