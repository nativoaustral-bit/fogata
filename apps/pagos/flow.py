"""
Cliente HTTP para la API oficial de Flow Chile (developers.flow.cl).
Construido exclusivamente sobre la librería estándar de Python.
"""

import json
import logging
import urllib.request
import urllib.parse
from django.conf import settings
from .signing import generar_firma_flow

logger = logging.getLogger(__name__)


class FlowError(Exception):
    """Excepción base para integraciones con Flow."""
    pass


class FlowNetworkError(FlowError):
    """Errores de red, timeout o indisponibilidad temporal de Flow."""
    pass


class FlowAPIError(FlowError):
    """Errores devueltos por la API de Flow con código de error."""
    def __init__(self, message, code=None, status_code=None):
        super().__init__(message)
        self.code = code
        self.status_code = status_code


class FlowClient:
    """
    Cliente para la API oficial de Flow.
    Soporta Sandbox y Producción de forma segura y controlada.
    """
    def __init__(self, api_key=None, secret_key=None, base_url=None, environment=None, timeout_segundos=6):
        self.environment = environment or getattr(settings, 'FLOW_ENVIRONMENT', 'sandbox').lower()
        self.api_key = api_key or getattr(settings, 'FLOW_API_KEY', '')
        self.secret_key = secret_key or getattr(settings, 'FLOW_SECRET_KEY', '')
        self.timeout_segundos = timeout_segundos or getattr(settings, 'FLOW_HTTP_TIMEOUT', 15)

        default_base = 'https://sandbox.flow.cl/api' if self.environment == 'sandbox' else 'https://www.flow.cl/api'
        self.base_url = (base_url or getattr(settings, 'FLOW_BASE_URL', default_base)).rstrip('/')

        # Fail-safe estricto para ambiente de Producción (Ajuste 9)
        if self.environment == 'production':
            if not self.api_key or not self.secret_key:
                raise FlowError("Configuración de Flow incompleta en ambiente de producción (falta API Key o Secret Key).")
            if 'sandbox' in self.base_url.lower():
                raise FlowError("Inconsistencia crítica: FLOW_ENVIRONMENT=production pero FLOW_BASE_URL apunta a sandbox.")

    def crear_pago(self, commerce_order: str, subject: str, amount: int, email: str,
                   url_confirmation: str, url_return: str, timeout_orden: int = 3600) -> dict:
        """
        Llama al endpoint /payment/create de Flow.
        timeout_orden: Expiración en segundos para la sesión de pago (por defecto 3600 = 60 min).
        """
        if not self.api_key or not self.secret_key:
            raise FlowError("Credenciales de Flow no configuradas.")

        params = {
            'apiKey': self.api_key,
            'commerceOrder': commerce_order,
            'subject': subject,
            'currency': 'CLP',
            'amount': str(amount),
            'email': email,
            'urlConfirmation': url_confirmation,
            'urlReturn': url_return,
            'timeout': str(timeout_orden),
        }

        # Generar firma HMAC SHA-256 oficial
        params['s'] = generar_firma_flow(params, self.secret_key)

        endpoint = f"{self.base_url}/payment/create"
        data_encoded = urllib.parse.urlencode(params).encode('utf-8')
        req = urllib.request.Request(
            endpoint,
            data=data_encoded,
            headers={
                'Content-Type': 'application/x-www-form-urlencoded',
                'User-Agent': 'Fogata-FlowClient/1.0',
            },
            method='POST'
        )

        try:
            with urllib.request.urlopen(req, timeout=self.timeout_segundos) as response:
                status_code = response.getcode()
                body = response.read().decode('utf-8')
                data = json.loads(body)

                if status_code != 200:
                    raise FlowAPIError(
                        f"Flow respondió con código HTTP {status_code}: {data.get('message', 'Error')}",
                        code=data.get('code'),
                        status_code=status_code
                    )

                # Validar presencia de llaves requeridas
                if 'url' not in data or 'token' not in data:
                    raise FlowAPIError(f"Respuesta inesperada de Flow: faltan url o token. {data}")

                return data

        except urllib.error.HTTPError as e:
            try:
                err_data = json.loads(e.read().decode('utf-8'))
                msg = err_data.get('message', str(e))
                code = err_data.get('code')
            except Exception:
                msg = str(e)
                code = None
            logger.error("Error HTTP al llamar Flow /payment/create: %s (código: %s)", msg, code)
            raise FlowAPIError(f"Error de API Flow: {msg}", code=code, status_code=e.code)

        except (urllib.error.URLError, TimeoutError, OSError) as e:
            logger.error("Error de conectividad al llamar Flow /payment/create: %s", str(e))
            raise FlowNetworkError(f"Error de conexión con Flow: {str(e)}")

    def obtener_estado_pago(self, token: str, timeout: int = None) -> dict:
        """
        Llama al endpoint /payment/getStatus de Flow.
        Utiliza GET con parámetros firmados apiKey, token y s.
        Usa timeout controlado de 7s por defecto para responder oportunamente en el callback.
        """
        if not self.api_key or not self.secret_key:
            raise FlowError("Credenciales de Flow no configuradas.")

        params = {
            'apiKey': self.api_key,
            'token': token,
        }
        params['s'] = generar_firma_flow(params, self.secret_key)

        query_string = urllib.parse.urlencode(params)
        endpoint = f"{self.base_url}/payment/getStatus?{query_string}"

        req = urllib.request.Request(
            endpoint,
            headers={
                'User-Agent': 'Fogata-FlowClient/1.0',
            },
            method='GET'
        )

        timeout_efectivo = timeout or getattr(settings, 'FLOW_CONFIRMATION_TIMEOUT', 7)
        try:
            with urllib.request.urlopen(req, timeout=timeout_efectivo) as response:
                status_code = response.getcode()
                body = response.read().decode('utf-8')
                data = json.loads(body)

                if status_code != 200:
                    raise FlowAPIError(
                        f"Flow respondió con código HTTP {status_code}: {data.get('message', 'Error')}",
                        code=data.get('code'),
                        status_code=status_code
                    )

                return data

        except urllib.error.HTTPError as e:
            try:
                err_data = json.loads(e.read().decode('utf-8'))
                msg = err_data.get('message', str(e))
                code = err_data.get('code')
            except Exception:
                msg = str(e)
                code = None
            logger.error("Error HTTP al llamar Flow /payment/getStatus: %s (código: %s)", msg, code)
            raise FlowAPIError(f"Error de API Flow: {msg}", code=code, status_code=e.code)

        except (urllib.error.URLError, TimeoutError, OSError) as e:
            logger.error("Error de conectividad al llamar Flow /payment/getStatus: %s", str(e))
            raise FlowNetworkError(f"Error de conexión con Flow: {str(e)}")
