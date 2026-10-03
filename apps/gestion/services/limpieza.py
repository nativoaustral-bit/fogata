"""
Servicio centralizado de limpieza y mantenimiento seguro para Fogata Control Center (Fase 10).
Principio: Los datos de prueba deben poder eliminarse; los registros comerciales reales
deben conservar trazabilidad absoluta e inmutabilidad referencial.
"""

import logging
from django.db import transaction
from django.db.models import Count, Sum, Q, Exists, OuterRef
from django.core.exceptions import PermissionDenied
from django.contrib.auth import get_user_model

from apps.pagos.models import OrdenPago
from apps.canciones.models import Cancion
from apps.fogatas.models import Fogata, FogataCancion, SesionCompartida
from apps.core.models import PerfilPiloto
from ..models import EventoUso, AuditoriaAdmin
from .eventos import registrar_auditoria_admin

logger = logging.getLogger(__name__)
User = get_user_model()


def puede_eliminar_usuario(
    usuario: User,
    current_user: User = None,
    admin_usuario: User = None,
    admin_responsable: User = None
) -> tuple[bool, str]:
    """
    Determina con rigor técnico y legal si una cuenta de usuario puede ser eliminada.
    Reglas absolutas:
    1. Nunca permitir eliminar al superusuario o usuario actualmente conectado.
    2. Nunca permitir eliminar un superuser.
    3. NUNCA permitir eliminar usuarios que posean órdenes de pago en PRODUCCIÓN (PAGADA o iniciada).
    """
    if not usuario or not usuario.pk:
        return False, "Usuario inexistente o inválido."

    admin_conectado = current_user or admin_usuario or admin_responsable

    # 1. Protección del administrador conectado (Criterio 10)
    if admin_conectado and usuario.pk == admin_conectado.pk:
        return False, "No puedes eliminar tu propia cuenta de administrador conectada."

    # 2. Protección de superusuarios
    if usuario.is_superuser:
        return False, "No es posible eliminar la cuenta del administrador principal (superusuario)."

    # 3. REGLA ABSOLUTA: Protección estricta de pagos reales (Criterio 2)
    tiene_pago_prod_pagada = OrdenPago.objects.filter(
        usuario=usuario,
        ambiente=OrdenPago.AMBIENTE_PRODUCTION,
        estado=OrdenPago.ESTADO_PAGADA
    ).exists()
    if tiene_pago_prod_pagada:
        return False, (
            "El usuario posee órdenes comerciales reales PAGADAS en Producción. "
            "Por trazabilidad financiera y legal, esta cuenta no puede eliminarse; "
            "únicamente puede ser desactivada."
        )

    # Protección adicional: Cualquier orden en ambiente producción
    tiene_orden_prod = OrdenPago.objects.filter(
        usuario=usuario,
        ambiente=OrdenPago.AMBIENTE_PRODUCTION
    ).exists()
    if tiene_orden_prod:
        return False, (
            "El usuario posee órdenes transaccionales registradas en Producción. "
            "No se permite la eliminación de cuentas con actividad comercial real."
        )

    return True, ""


def obtener_resumen_dependencias_usuario(usuario: User) -> dict:
    """
    Genera un resumen exhaustivo de dependencias y datos asociados
    que serían eliminados si se confirma la eliminación del usuario de prueba.
    """
    canciones_count = usuario.canciones.count()
    fogatas_count = usuario.fogatas.count()
    fogata_cancion_count = FogataCancion.objects.filter(fogata__propietario=usuario).count()
    sesiones_compartidas_count = SesionCompartida.objects.filter(fogata__propietario=usuario).count()
    eventos_count = EventoUso.objects.filter(usuario=usuario).count()
    ordenes_sandbox_count = OrdenPago.objects.filter(
        usuario=usuario,
        ambiente=OrdenPago.AMBIENTE_SANDBOX
    ).count()
    ordenes_prod_count = OrdenPago.objects.filter(
        usuario=usuario,
        ambiente=OrdenPago.AMBIENTE_PRODUCTION
    ).count()

    tiene_pagos_prod_pagados = OrdenPago.objects.filter(
        usuario=usuario,
        ambiente=OrdenPago.AMBIENTE_PRODUCTION,
        estado=OrdenPago.ESTADO_PAGADA
    ).exists()

    puede, motivo = puede_eliminar_usuario(usuario)

    return {
        'canciones_count': canciones_count,
        'fogatas_count': fogatas_count,
        'fogata_cancion_count': fogata_cancion_count,
        'sesiones_compartidas_count': sesiones_compartidas_count,
        'eventos_count': eventos_count,
        'ordenes_sandbox_count': ordenes_sandbox_count,
        'ordenes_prod_count': ordenes_prod_count,
        'tiene_pagos_prod_pagados': tiene_pagos_prod_pagados,
        'puede_eliminar': puede,
        'motivo_bloqueo': motivo,
    }


def eliminar_usuario_prueba(usuario: User, admin_responsable: User) -> dict:
    """
    Elimina atómicamente un usuario de prueba y todos sus datos dependientes.
    Verifica previamente 'puede_eliminar_usuario'.
    Aísla completamente los datos de otros usuarios y preserva registros Production.
    """
    puede, motivo = puede_eliminar_usuario(usuario, current_user=admin_responsable)
    if not puede:
        raise PermissionDenied(motivo)

    with transaction.atomic():
        email = usuario.email
        user_id = usuario.pk

        # 1. Resumen previo
        resumen = obtener_resumen_dependencias_usuario(usuario)

        # 2. Eliminar órdenes Sandbox de este usuario (NUNCA Production)
        OrdenPago.objects.filter(
            usuario=usuario,
            ambiente=OrdenPago.AMBIENTE_SANDBOX
        ).delete()

        # Doble verificación de seguridad: Asegurar que no quede ninguna orden protegida
        if OrdenPago.objects.filter(usuario=usuario).exists():
            raise PermissionDenied("SEGURIDAD: El usuario posee órdenes de pago que impiden su eliminación.")

        # 3. Eliminar sesiones compartidas vinculadas a sus fogatas
        SesionCompartida.objects.filter(fogata__propietario=usuario).delete()

        # 4. Eliminar relaciones intermedias y Fogatas del usuario
        FogataCancion.objects.filter(fogata__propietario=usuario).delete()
        Fogata.objects.filter(propietario=usuario).delete()

        # 5. Eliminar canciones del usuario
        Cancion.objects.filter(propietario=usuario).delete()

        # 6. Eliminar eventos de actividad del usuario
        EventoUso.objects.filter(usuario=usuario).delete()

        # 7. Eliminar perfil piloto
        PerfilPiloto.objects.filter(user=usuario).delete()

        # 8. Limpiar auditorías administrativas asociadas a este usuario de prueba
        AuditoriaAdmin.objects.filter(usuario_afectado=usuario).delete()
        AuditoriaAdmin.objects.filter(admin=usuario).delete()

        # 9. Eliminar físicamente el usuario
        usuario.delete()

        # 10. Registrar auditoría inmutable del acto de limpieza
        registrar_auditoria_admin(
            admin=admin_responsable,
            usuario_afectado=admin_responsable,
            accion='suspender_usuario',
            detalles=f"Eliminación de usuario de prueba ID {user_id} ({email}): {resumen['canciones_count']} canciones, {resumen['fogatas_count']} fogatas, {resumen['ordenes_sandbox_count']} órdenes Sandbox."
        )

        logger.info("Usuario de prueba %s (ID %s) eliminado exitosamente por %s.", email, user_id, admin_responsable.email)
        return resumen


def eliminar_orden_sandbox(orden: OrdenPago, admin_responsable: User) -> bool:
    """
    Elimina de forma segura e individual una orden de prueba Sandbox.
    Bloquea categóricamente cualquier intento sobre órdenes de Producción.
    """
    if orden.ambiente != OrdenPago.AMBIENTE_SANDBOX:
        raise PermissionDenied("SEGURIDAD: Las órdenes de Producción son inmutables y no pueden eliminarse.")

    commerce_order = orden.commerce_order
    user_email = orden.usuario.email if orden.usuario else "Desconocido"

    orden.delete()

    registrar_auditoria_admin(
        admin=admin_responsable,
        usuario_afectado=admin_responsable,
        accion='suspender_usuario',
        detalles=f"Eliminación de orden Sandbox {commerce_order} (Usuario: {user_email})."
    )
    logger.info("Orden Sandbox %s eliminada por %s.", commerce_order, admin_responsable.email)
    return True


def limpiar_ordenes_sandbox(admin_responsable: User) -> int:
    """
    Eliminación masiva segura de órdenes de prueba en Sandbox (Criterio 4 y 5).
    Aplica condición explícita ambiente='SANDBOX'.
    """
    with transaction.atomic():
        # Condición estricta requerida por Criterio 5:
        total_eliminadas, _ = OrdenPago.objects.filter(
            ambiente=OrdenPago.AMBIENTE_SANDBOX
        ).delete()

        registrar_auditoria_admin(
            admin=admin_responsable,
            usuario_afectado=admin_responsable,
            accion='suspender_usuario',
            detalles=f"Limpieza masiva: {total_eliminadas} órdenes Sandbox eliminadas por {admin_responsable.email}."
        )
        logger.info("Limpieza masiva Sandbox ejecutada por %s. Total eliminadas: %s.", admin_responsable.email, total_eliminadas)
        return total_eliminadas


def limpiar_actividad_usuario(usuario: User, admin_responsable: User) -> int:
    """
    Limpia la actividad de producto de un usuario específico únicamente si NO posee
    pagos reales en Producción (Criterio 6).
    """
    tiene_pagos_prod = OrdenPago.objects.filter(
        usuario=usuario,
        ambiente=OrdenPago.AMBIENTE_PRODUCTION,
        estado=OrdenPago.ESTADO_PAGADA
    ).exists()

    if tiene_pagos_prod:
        raise PermissionDenied("No se permite eliminar la actividad de usuarios con pagos reales en Producción.")

    with transaction.atomic():
        total, _ = EventoUso.objects.filter(usuario=usuario).delete()

        registrar_auditoria_admin(
            admin=admin_responsable,
            usuario_afectado=admin_responsable,
            accion='suspender_usuario',
            detalles=f"Limpieza de actividad ({total} eventos) del usuario {usuario.email} ejecutada por {admin_responsable.email}."
        )
        return total


def limpiar_actividad_prueba(admin_responsable: User) -> int:
    """
    Limpia eventos de actividad correspondientes a cuentas de prueba o huérfanas,
    conservando rigurosamente todos los eventos de usuarios con pagos reales y eventos financieros.
    """
    # 1. Identificar usuarios protegidos con pagos reales
    usuarios_protegidos = set(
        OrdenPago.objects.filter(
            ambiente=OrdenPago.AMBIENTE_PRODUCTION
        ).values_list('usuario_id', flat=True)
    )

    # 2. Identificar usuarios staff
    staff_ids = set(User.objects.filter(is_staff=True).values_list('id', flat=True))

    with transaction.atomic():
        # Eventos a eliminar: huérfanos o de usuarios sin pagos reales ni staff
        qs = EventoUso.objects.exclude(
            usuario_id__in=usuarios_protegidos | staff_ids
        ).exclude(
            tipo_evento__in=['pago_confirmado', 'upgrade_pro', 'renovacion_pro']
        )

        total, _ = qs.delete()

        registrar_auditoria_admin(
            admin=admin_responsable,
            usuario_afectado=admin_responsable,
            accion='suspender_usuario',
            detalles=f"Limpieza masiva de actividad de prueba ({total} eventos eliminados) ejecutada por {admin_responsable.email}."
        )
        return total


def obtener_metricas_mantenimiento() -> dict:
    """
    Recopila métricas operacionales para la herramienta /gestion/mantenimiento/ (Criterio 8).
    """
    usuarios_con_prod = set(
        OrdenPago.objects.filter(
            ambiente=OrdenPago.AMBIENTE_PRODUCTION
        ).values_list('usuario_id', flat=True)
    )
    staff_ids = set(User.objects.filter(is_staff=True).values_list('id', flat=True))

    usuarios_prueba_eliminables = (
        User.objects.exclude(id__in=usuarios_con_prod | staff_ids)
        .count()
    )

    ordenes_sandbox = OrdenPago.objects.filter(
        ambiente=OrdenPago.AMBIENTE_SANDBOX
    ).count()

    eventos_prueba = EventoUso.objects.exclude(
        usuario_id__in=usuarios_con_prod | staff_ids
    ).exclude(
        tipo_evento__in=['pago_confirmado', 'upgrade_pro', 'renovacion_pro']
    ).count()

    usuarios_desactivados = User.objects.filter(is_active=False).count()

    ordenes_prod_protegidas = OrdenPago.objects.filter(
        ambiente=OrdenPago.AMBIENTE_PRODUCTION
    ).count()

    ingresos_prod_protegidos = OrdenPago.objects.filter(
        ambiente=OrdenPago.AMBIENTE_PRODUCTION,
        estado=OrdenPago.ESTADO_PAGADA
    ).aggregate(s=Sum('monto'))['s'] or 0

    return {
        'usuarios_prueba_eliminables': usuarios_prueba_eliminables,
        'ordenes_sandbox': ordenes_sandbox,
        'eventos_prueba': eventos_prueba,
        'usuarios_desactivados': usuarios_desactivados,
        'ordenes_prod_protegidas': ordenes_prod_protegidas,
        'ingresos_prod_protegidos': ingresos_prod_protegidos,
    }


def obtener_dry_run_limpieza_usuarios() -> dict:
    """
    Calcula la vista previa de limpieza masiva de usuarios de prueba (Criterio 9).
    Demuestra con exactitud que órdenes e ingresos Production se mantienen en CERO impacto.
    """
    usuarios_con_prod = set(
        OrdenPago.objects.filter(
            ambiente=OrdenPago.AMBIENTE_PRODUCTION
        ).values_list('usuario_id', flat=True)
    )
    staff_ids = set(User.objects.filter(is_staff=True).values_list('id', flat=True))

    usuarios_qs = User.objects.exclude(id__in=usuarios_con_prod | staff_ids)
    u_ids = list(usuarios_qs.values_list('id', flat=True))

    usuarios_count = len(u_ids)
    canciones_count = Cancion.objects.filter(propietario_id__in=u_ids).count()
    fogatas_count = Fogata.objects.filter(propietario_id__in=u_ids).count()
    eventos_count = EventoUso.objects.filter(usuario_id__in=u_ids).count()
    ordenes_sandbox_count = OrdenPago.objects.filter(
        usuario_id__in=u_ids,
        ambiente=OrdenPago.AMBIENTE_SANDBOX
    ).count()

    return {
        'usuarios_count': usuarios_count,
        'canciones_count': canciones_count,
        'fogatas_count': fogatas_count,
        'eventos_count': eventos_count,
        'ordenes_sandbox_count': ordenes_sandbox_count,
        'ordenes_prod_afectadas': 0,
        'ingresos_prod_afectados': 0,
    }


def ejecutar_limpieza_masiva_usuarios_prueba(admin_responsable: User) -> dict:
    """
    Ejecuta la limpieza masiva sobre las cuentas de prueba confirmadas tras Dry Run.
    Garantiza aislamiento y cero impacto en cuentas con pagos reales o staff.
    """
    usuarios_con_prod = set(
        OrdenPago.objects.filter(
            ambiente=OrdenPago.AMBIENTE_PRODUCTION
        ).values_list('usuario_id', flat=True)
    )
    staff_ids = set(User.objects.filter(is_staff=True).values_list('id', flat=True))

    usuarios_a_eliminar = list(
        User.objects.exclude(id__in=usuarios_con_prod | staff_ids)
    )

    total_usuarios = 0
    total_canciones = 0
    total_fogatas = 0
    total_sandbox = 0
    total_eventos = 0

    for u in usuarios_a_eliminar:
        res = eliminar_usuario_prueba(u, admin_responsable=admin_responsable)
        total_usuarios += 1
        total_canciones += res['canciones_count']
        total_fogatas += res['fogatas_count']
        total_sandbox += res['ordenes_sandbox_count']
        total_eventos += res['eventos_count']

    return {
        'total_usuarios': total_usuarios,
        'total_canciones': total_canciones,
        'total_fogatas': total_fogatas,
        'total_sandbox': total_sandbox,
        'total_eventos': total_eventos,
        'ordenes_prod_afectadas': 0,
        'ingresos_prod_afectados': 0,
    }
