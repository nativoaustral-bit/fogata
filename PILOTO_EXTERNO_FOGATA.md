# FOGATA — Registro y Guía de Operación del Piloto Externo

**Documento Operacional — Piloto Multiusuario Controlado**  
**Versión:** 1.0 (Post Release Gate 6.1)  
**Fecha:** Septiembre 2026  
**Alcance:** 5 a 10 usuarios iniciales seleccionados  

---

## 1. Alcance y Filosofía del Piloto

El objetivo de este piloto es observar el uso real de Fogata por parte de músicos amigos en condiciones naturales, validando que la aplicación resuelva su necesidad sin requerir explicaciones ni soporte continuo.

> **Principio clave:**  
> No enseñarles todas las funciones antes de comenzar. Queremos evaluar el **descubrimiento natural** de la herramienta. A partir de aquí Fogata debe aprender de los usuarios, no de nuevas hipótesis de desarrollo.

### Reglas estrictas de producto durante el piloto
Queda **estrictamente congelado** el desarrollo de nuevas funcionalidades hasta concluir la fase de observación. No desarrollar durante el piloto:
- Pagos o planes de suscripción.
- Perfiles de usuario públicos o redes sociales.
- Biblioteca compartida o repositorio global.
- Social login (Google, Apple, etc.).
- Herramientas externas de analítica intrusiva.
- Colaboración en tiempo real o edición multiusuario simultánea.
- Modos offline multiusuario complejos.

---

## 2. Dimensionamiento y Entrega de Accesos

- **Capacidad asignada:** 5 a 10 músicos de prueba iniciales.
- **Acceso:** Registro cerrado exclusivamente mediante código de invitación.
- **Distribución de invitaciones:** Entrega personalizada (1 a 1).
- **Código de producción:** Generado criptográficamente en el servidor mediante el comando `python manage.py crear_invitacion` y resguardado fuera de repositorios, informes y canales públicos.
- **Soporte de concurrencia:** El piloto opera sobre SQLite. Las invitaciones cuentan con validación y decremento atómico a nivel de motor de datos (`UPDATE ... WHERE usos_actuales < max_usos`), evitando sobreasignación.

---

## 3. Puntos Críticos de Observación (Qué evaluar con los amigos)

Durante la interacción del usuario de prueba, no intervenir activamente. Registrar exclusivamente las **fricciones reales** observadas en las siguientes dimensiones:

| Dimensión | Pregunta de Validación | Fricción a detectar |
| :--- | :--- | :--- |
| **1. Registro** | ¿Entienden cómo entrar y usar el código? | Confusión con el formulario, problemas de mayúsculas en correo, dudas sobre el código. |
| **2. Primera Canción** | ¿Saben qué pegar y dónde? | Dudas sobre formato de acordes `[Do]`, frustración al transcribir, dificultad para encontrar el botón de guardado. |
| **3. Comprensión de Fogata** | ¿Comprenden para qué sirve una Fogata sin explicación? | Confusión entre canción individual y setlist/agrupación, dudas al crear o nombrar una Fogata. |
| **4. Modo Tocar (Atril)** | ¿Encuentran auto-scroll, transposición y diagramas? | Dificultad para ajustar velocidad de scroll, no ver los acordes en pantalla táctil, no hallar la transposición. |
| **5. Compartir Sesión** | ¿Comprenden que el enlace es temporal y de solo lectura? | Preguntas sobre si sus amigos pueden editar, dudas sobre la caducidad (HTTP 410) del enlace. |
| **6. Retorno Espontáneo** | ¿Vuelven espontáneamente a utilizar Fogata después de la primera prueba? | ¿La abrieron en un ensayo real o fogata de fin de semana sin que se lo recordáramos? |

---

## 4. Registro Operacional de Usuarios del Piloto

> **Aviso de Privacidad:**  
> Por respeto a la privacidad y derechos de los músicos participantes, **no registrar letras ni contenido de canciones** en esta bitácora operacional. Solo registrar datos cuantitativos y fricciones de uso.

| # | Usuario piloto (Nombre/Alias) | Fecha de inicio | Canciones creadas | Fogatas creadas | Problemas encontrados (Fricciones) | Observaciones de comportamiento y retorno |
| :-: | :--- | :---: | :---: | :---: | :--- | :--- |
| **1** | *(Cupo 1)* | — | — | — | — | — |
| **2** | *(Cupo 2)* | — | — | — | — | — |
| **3** | *(Cupo 3)* | — | — | — | — | — |
| **4** | *(Cupo 4)* | — | — | — | — | — |
| **5** | *(Cupo 5)* | — | — | — | — | — |
| **6** | *(Cupo 6)* | — | — | — | — | — |
| **7** | *(Cupo 7)* | — | — | — | — | — |
| **8** | *(Cupo 8)* | — | — | — | — | — |
| **9** | *(Cupo 9)* | — | — | — | — | — |
| **10** | *(Cupo 10)* | — | — | — | — | — |

---

## 5. Protocolo de Incidencias Durante el Piloto

1. **Error 404/500 no previsto:** El usuario debe reportar captura o mensaje. En el servidor, verificar logs de Django sin exponer detalles en pantalla.
2. **Revocación de acceso:** Si un enlace compartido expira o requiere ser anulado de urgencia, el músico puede revocarlo directamente desde la pantalla de detalle de su Fogata (botón "Revocar").
3. **Pérdida de contraseña:** Utilizar el flujo blind de recuperación por correo electrónico (`/recuperar-password/`).
4. **Cierre de cuenta:** El administrador puede desactivar el usuario desde Django Admin (`is_active=False`) de forma inmediata.
