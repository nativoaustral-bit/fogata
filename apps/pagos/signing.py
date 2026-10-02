"""
Servicio centralizado de firmado y verificación HMAC SHA-256 para Flow Chile.
Especificación oficial: developers.flow.cl
"""

import hmac
import hashlib


def generar_firma_flow(params: dict, secret_key: str) -> str:
    """
    Genera la firma requerida por Flow:
    1. Excluye el parámetro 's'.
    2. Ordena las claves alfabéticamente.
    3. Concatena 'nombre + valor'.
    4. Genera HMAC SHA-256 con secret_key.
    5. Retorna el resultado en hexadecimal en minúsculas.
    """
    if not secret_key:
        raise ValueError("FLOW_SECRET_KEY es obligatoria para firmar peticiones a Flow.")

    claves_ordenadas = sorted(k for k in params.keys() if k != 's')
    to_sign = "".join(f"{k}{params[k]}" for k in claves_ordenadas)

    return hmac.new(
        secret_key.encode('utf-8'),
        to_sign.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()


def verificar_firma_flow(params: dict, firma_recibida: str, secret_key: str) -> bool:
    """
    Verifica con compare_digest si una firma recibida corresponde al cálculo oficial.
    """
    if not firma_recibida or not secret_key:
        return False
    firma_calculada = generar_firma_flow(params, secret_key)
    return hmac.compare_digest(firma_calculada, firma_recibida)
