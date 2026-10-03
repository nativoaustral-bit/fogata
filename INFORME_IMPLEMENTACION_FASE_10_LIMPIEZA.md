# INFORME DE IMPLEMENTACIÓN — FASE 10
## Limpieza y Administración Segura de Usuarios y Datos de Prueba

**Fecha de ejecución:** 2 de Octubre de 2026  
**Plataforma:** Fogata (`fogata.humm.cl`)  
**Módulo:** Fogata Control Center (`/gestion/`)  
**Estado:** ✅ **COMPLETADO Y DESPLEGADO EN PRODUCCIÓN**  
**Resultado de Pruebas:** **35/35 PASS** en `apps.gestion` (204/204 PASS en suite global)

---

## 1. Resumen Ejecutivo y Principio Rector

La Fase 10 implementa en **Fogata Control Center** una suite integral de herramientas administrativas seguras para depurar cuentas de prueba, setlists, canciones auxiliares, eventos analíticos irrelevantes y órdenes de Flow Sandbox generadas durante las fases previas de certificación, sin arriesgar en ningún momento la información contable real ni la integridad referencial.

### Principio Rector
> **Los datos de prueba deben poder eliminarse.**  
> **Los registros comerciales reales deben conservar trazabilidad e inmutabilidad absoluta.**

No se implementó un borrado indiscriminado de usuarios: toda operación destructiva cuenta con validación previa en capas (servicio, vista, base de datos) y confirmación explícita.

---

## 2. Arquitectura del Servicio Centralizado

La lógica de mantenimiento y depuración se encapsuló en un servicio centralizado:
`apps/gestion/services/limpieza.py`, modularizando el paquete `apps/gestion/services/`:

- [apps/gestion/services/limpieza.py](file:///Users/rmerinog/PLATAFORMAS/FOGATA/apps/gestion/services/limpieza.py): Lógica de evaluación, cálculo de dependencias y borrado atómico.
- [apps/gestion/services/eventos.py](file:///Users/rmerinog/PLATAFORMAS/FOGATA/apps/gestion/services/eventos.py): Registro de telemetría y auditoría administrativa inmutable.
- [apps/gestion/services/__init__.py](file:///Users/rmerinog/PLATAFORMAS/FOGATA/apps/gestion/services/__init__.py): Exportación unificada y retrocompatibilidad total con el resto del proyecto.

### Funciones Principales Implementadas:
1. `puede_eliminar_usuario(usuario, current_user=None, ...)`: Determina si una cuenta puede ser eliminada física y legalmente.
2. `obtener_resumen_dependencias_usuario(usuario)`: Calcula el impacto detallado antes de confirmar una eliminación (canciones, fogatas, sesiones, eventos, órdenes Sandbox).
3. `eliminar_usuario_prueba(usuario, admin_responsable)`: Ejecuta el borrado atómico en cascada controlada dentro de `transaction.atomic()`.
4. `eliminar_orden_sandbox(orden, admin_responsable)`: Elimina de forma individual y segura una orden Sandbox, bloqueando tajantemente órdenes Production.
5. `limpiar_ordenes_sandbox(admin_responsable)`: Limpieza masiva con filtro explícito `ambiente="SANDBOX"`.
6. `limpiar_actividad_usuario(usuario, admin_responsable)`: Depura eventos operativos de un usuario específico sin pagos reales.
7. `limpiar_actividad_prueba(admin_responsable)`: Depuración masiva de eventos de cuentas de prueba conservando auditoría sensible.
8. `obtener_metricas_mantenimiento()`: Indicadores en tiempo real para el panel de mantenimiento.
9. `obtener_dry_run_limpieza_usuarios()`: Simulación técnica de limpieza masiva con desglose exacto y 0 impacto en producción.
10. `ejecutar_limpieza_masiva_usuarios_prueba(admin_responsable)`: Ejecución de limpieza masiva tras confirmación explícita.

---

## 3. Administración Segura de Usuarios (`/gestion/usuarios/`)

En la tabla general de usuarios y en la ficha 360° se incorporaron métricas comerciales y acciones administrativas:

### Nuevos Indicadores por Usuario:
- **Email, tipo de cuenta y estado** (Activo / Suspendido).
- **Fecha de registro y última actividad operativa**.
- **Repertorio:** N° de canciones, N° de Fogatas y sesiones compartidas.
- **Historial de Pagos:** Pagos Sandbox vs. Pagos Production.
- **Distintivo de Seguridad:** `🔒 Con pagos reales` (Inmutable) vs `🧪 Prueba`.

### Acciones Administrativas Disponibles:
1. **Desactivar usuario (`user.is_active = False`):**
   - Acción reversible.
   - El usuario permanece en la base de datos para trazabilidad pero se invalida su inicio de sesión.
   - Permite posteriormente: **Reactivar usuario**.
2. **Eliminar usuario de prueba:**
   - Opción habilitada **únicamente** si el usuario `NO` posee órdenes de pago en `ambiente = PRODUCTION` con `estado = PAGADA`.
   - Pantalla de confirmación previa con resumen cuantitativo de canciones, fogatas, eventos y órdenes Sandbox que se eliminarán.
   - Desafío de confirmación obligatorio mediante escritura de la palabra **`ELIMINAR`**.
   - Ejecución exclusiva mediante **POST + CSRF + Staff autenticado**.

---

## 4. Regla Absoluta de Protección para Pagos Reales

Para cualquier orden con `ambiente = PRODUCTION` y `estado = PAGADA`:
- **Bloqueo a nivel de vista:** No existe botón ni endpoint de eliminación.
- **Bloqueo a nivel de servicio:** `puede_eliminar_usuario` retorna `(False, "...")` y `eliminar_usuario_prueba` lanza `PermissionDenied`.
- **Bloqueo a nivel de base de datos:** `OrdenPago.usuario` posee `on_delete=models.PROTECT`, garantizando defensa en profundidad ante cualquier intento de borrado involuntario.
- **Opción para usuarios reales:** Únicamente se permite **Desactivar cuenta** (`is_active=False`).

---

## 5. Módulo de Pagos y Depuración Sandbox (`/gestion/pagos/`)

En la vista de pagos de Control Center:
- **Filtro de Ambiente:** `Todos`, `Producción`, `Sandbox`.
- **Eliminar orden individual Sandbox:** Para órdenes con `ambiente = SANDBOX`, con diálogo de confirmación. Las órdenes Production muestran etiqueta `🔒 Inmutable`.
- **Acción masiva:** Botón `🧹 Limpiar órdenes Sandbox` con pantalla de confirmación previa y confirmación por texto `ELIMINAR`.
- **Condición de seguridad:** Toda consulta de eliminación utiliza de forma explícita e inequívoca:
  ```python
  OrdenPago.objects.filter(ambiente=OrdenPago.AMBIENTE_SANDBOX).delete()
  ```
  **Nunca** se utiliza `.all().delete()` ni filtros ambiguos.

---

## 6. Depuración y Filtros de Actividad (`/gestion/actividad/`)

En el registro cronológico de actividad de producto se incorporaron:
- **Filtros avanzados:**
  - Búsqueda por Email de usuario.
  - Tipo de evento (login, crear canción, modo tocar, etc.).
  - Rango de fechas (`Desde` / `Hasta`).
  - Tipo de cuenta (`Solo Piloto` / `Excluir Piloto`).
  - Rol (`Solo Staff` / `Excluir Staff`).
- **Acciones seguras:**
  - `Eliminar actividad de este usuario`: Solo visible y ejecutable cuando la cuenta no tiene compras reales en Producción.
  - `Limpiar actividad de cuentas de prueba`: Depura eventos de uso de cuentas sin compras, conservando de forma estricta los eventos de pagos reales (`pago_produccion`, `activacion_pro`, etc.).

---

## 7. Panel de Mantenimiento y Dry Run Obligatorio

Se habilitó la nueva sección:
`/gestion/mantenimiento/` (visible exclusivamente para staff autorizado).

### Indicadores en Tiempo Real:
- **Usuarios de prueba eliminables:** Cuentas sin órdenes comerciales.
- **Órdenes Sandbox:** Total de transacciones de prueba acumuladas.
- **Eventos de cuentas de prueba:** Actividad no financiera descartable.
- **Usuarios desactivados:** Cuentas suspendidas administrativamente.
- **Órdenes Producción (Protegidas):** N° de órdenes inmutables.
- **Ingresos Reales Protegidos:** Monto total recaudado protegido ($5.990 CLP).

### Simulador Dry Run (`/gestion/mantenimiento/dry-run/`):
- Muestra una vista previa técnica con conteo exacto de usuarios, canciones, fogatas, eventos y órdenes Sandbox candidatas.
- Refleja explícitamente:
  - *Órdenes Production afectadas: 0*
  - *Ingresos reales afectados: $0*
- La ejecución requiere confirmación por desafío escribiendo la frase exacta **`CONFIRMAR LIMPIEZA`**.

---

## 8. Protección de Cuentas Administrativas

- Se bloquea la auto-eliminación del usuario staff o administrador actualmente autenticado.
- Se bloquea la eliminación del superusuario principal (`is_superuser=True`).
- Las acciones masivas excluyen automáticamente a cualquier usuario con `is_staff=True`.

---

## 9. Suite de Pruebas Automatizadas (15/15 Requeridas)

Se incorporó en [apps/gestion/tests.py](file:///Users/rmerinog/PLATAFORMAS/FOGATA/apps/gestion/tests.py) la clase `Fase10LimpiezaSeguraTests` cubriendo todos los escenarios obligatorios:

| # | Prueba | Escenario Validado | Resultado |
|---|---|---|:---:|
| 1 | `test_01_eliminar_usuario_sin_pagos` | Eliminación exitosa de usuario sin transacciones | **PASS** |
| 2 | `test_02_eliminar_usuario_con_datos_asociados` | Borrado en cascada controlada (canciones, fogatas, sesiones, eventos) | **PASS** |
| 3 | `test_03_eliminar_usuario_con_ordenes_sandbox` | Eliminación de usuario con órdenes Sandbox previas | **PASS** |
| 4 | `test_04_bloquear_eliminacion_si_posee_pago_production_pagada` | Bloqueo absoluto de eliminación a nivel servicio y HTTP POST | **PASS** |
| 5 | `test_05_desactivar_usuario_con_pago_production` | Desactivación reversible de usuario con orden real | **PASS** |
| 6 | `test_06_reactivar_usuario` | Reactivación funcional de cuenta suspendida | **PASS** |
| 7 | `test_07_eliminar_orden_sandbox_individual` | Eliminación de orden Sandbox y bloqueo PermissionDenied sobre Production | **PASS** |
| 8 | `test_08_eliminacion_masiva_sandbox` | Limpieza masiva Sandbox manteniendo intactas órdenes de Producción | **PASS** |
| 9 | `test_09_garantizar_que_ninguna_orden_production_sea_eliminada` | Inmutabilidad de órdenes Production tras limpiezas combinadas | **PASS** |
| 10 | `test_10_limpiar_actividad_cuenta_prueba` | Depuración de actividad individual y masiva preservando eventos reales | **PASS** |
| 11 | `test_11_impedir_eliminacion_superuser_conectado` | Bloqueo de auto-eliminación y protección de superusuario | **PASS** |
| 12 | `test_12_csrf_y_post_obligatorio` | Protección CSRF, rechazo de GET y validación de palabra clave 'ELIMINAR' | **PASS** |
| 13 | `test_13_aislamiento_entre_usuarios` | Datos de otros usuarios intactos tras eliminar una cuenta | **PASS** |
| 14 | `test_14_dry_run_produce_conteos_correctos` | Simulación Dry Run calcula conteos sin alterar la base de datos | **PASS** |
| 15 | `test_15_metricas_financieras_production_permanecen_identicas` | Métricas comerciales e ingresos idénticos antes y después de limpieza | **PASS** |

### Resultados Globales:
- **`apps.gestion`:** **35/35 PASS** (14.9s en HostGator)
- **Suite Completa Fogata:** **204/204 PASS** (43.9s)

---

## 10. Verificación en el Entorno Real de Producción

Tras el despliegue del commit `b1685bd` y reinicio de Passenger en HostGator, se ejecutó una verificación directa contra la base de datos real con las variables de producción activas:

```text
METRICAS_MANTENIMIENTO: {
    'usuarios_prueba_eliminables': 10,
    'ordenes_sandbox': 7,
    'eventos_prueba': 32,
    'usuarios_desactivados': 0,
    'ordenes_prod_protegidas': 1,
    'ingresos_prod_protegidos': 5990
}

ORDENES PRODUCTION PAGADA: [
    {
        'id': 8,
        'commerce_order': 'FOG-6M-20261002-E1DCDA18F1AFEAD7',
        'monto': 5990,
        'usuario__email': 'rmerinog@nativoaustral.cl'
    }
]

DRY RUN SIMULACIÓN: {
    'usuarios_count': 10,
    'canciones_count': 5,
    'fogatas_count': 2,
    'eventos_count': 15,
    'ordenes_sandbox_count': 5,
    'ordenes_prod_afectadas': 0,
    'ingresos_prod_afectados': 0
}

VALIDACIÓN DE PROTECCIÓN:
puede_eliminar_usuario('rmerinog@nativoaustral.cl') ->
(False, 'El usuario posee órdenes comerciales reales PAGADAS en Producción. Por trazabilidad financiera y legal, esta cuenta no puede eliminarse; únicamente puede ser desactivada.')
```

---

## 11. Conclusión y Entrega

La **Fase 10** ha quedado completamente implementada, verificada y desplegada en producción. El administrador cuenta ahora con control absoluto en **Fogata Control Center** para depurar la base de datos de pruebas técnicas previas, con la total garantía de que ningún ingreso real ni orden comercial de producción podrá ser afectada.
