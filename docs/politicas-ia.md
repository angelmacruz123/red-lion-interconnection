# docs/politicas-ia.md — Ciberdefensa y uso de IA en la herramienta

Proyecto: **RED-LION-INTERCONNECTION** · Autor: Angel Mauricio Cruz Gonzalez · Materia: Interconexión de Redes WAN

## Políticas (plantilla del curso)

1. La herramienta nunca guarda contraseñas ni tokens en el código; van en `.env`
   (protegido por `.gitignore`).
2. Con IA pública solo se usan datos de ejemplo, nunca IPs reales, credenciales
   ni topologías sensibles.
3. Todo lo que ingresa el usuario se valida y sanea antes de usarse.
4. La herramienta advierte cuando una configuración es insegura (puertos abiertos,
   credenciales por defecto) y aplica el mínimo privilegio.
5. No se ejecuta ningún comando o configuración que no se entienda; lo generado por
   IA se revisa y se prueba primero.
6. Toda automatización/acceso a equipos se hace solo en el laboratorio autorizado.
7. La calidad se mide con pruebas y se reporta el % de confianza (`docs/pruebas.md`).

## Cómo la herramienta aplica cada política

| # | Política | Dónde se cumple en la herramienta | Prueba que lo verifica |
|---|---|---|---|
| 1 | Sin secretos en el código | Las configuraciones generadas usan marcadores `<<ADMIN_SECRET>>`, `<<VPN_PSK>>`…; las credenciales se leen solo de `.env`; `.gitignore` excluye `.env` y `configs_out/`; un escáner busca secretos en el código (Módulo 6) | `tests/test_security.py`, `tests/test_generators.py::test_sin_secretos_reales_solo_marcadores` |
| 2 | Solo datos de ejemplo con IA | Los escenarios usan redes de documentación y privadas (`10.20.0.0/16`, `2001:db8::/32`, `200.10.10.0/30`); `.env.example` no trae valores; las salidas de equipos se enmascaran antes de mostrarse o guardarse | `tests/test_security.py::test_env_example_sin_valores_secretos` |
| 3 | Validar y sanear entradas | `core/validators.py`: lista blanca en formularios, CIDR estrictos, hostnames RFC 1123, bloqueo de `;`, `&&`, `$()` y saltos de línea en comandos, escape HTML de la terminal; la topología importada se valida completa antes de aceptarse | `tests/test_validators.py`, `tests/test_topology_io.py` |
| 4 | Advertir configuraciones inseguras | `core/security_audit.py` revisa cada archivo generado (Módulo 4), cada lote antes de desplegar (Módulo 5) y cualquier configuración pegada (Módulo 6): Telnet, HTTP, SSH v1, credenciales por defecto, contraseñas en claro, SNMP `public`, ACL «permit any», VTY sin ACL, gestión desde la WAN. Las plantillas aplican mínimo privilegio: solo SSH v2, gestión limitada a la VLAN 99, SNMPv3, puertos sin uso apagados | `tests/test_security_audit.py` |
| 5 | No ejecutar lo que no se entiende | El despliegue muestra la vista previa exacta de lo que se enviará; en equipos reales exige escribir el nombre del equipo; los comandos destructivos (`reload`, `erase`…) requieren confirmación explícita; respaldo previo y detención ante el primer error | `tests/test_deploy.py`, `tests/test_validators.py::test_lote_rechaza_destructivo_sin_confirmacion` |
| 6 | Solo laboratorio autorizado | SSH verifica la clave del equipo (`known_hosts`); Telnet solo hacia IP privadas y con `ENABLE_TELNET_LAB=true`; la consola serial es una conexión física local | `tests/test_netdevops.py`, `tests/test_serial.py` |
| 7 | Medir con pruebas | `pytest` + `scripts/generate_test_report.py` escriben `docs/pruebas.md` con «X de Y = Z% de confianza»; se ejecutan en vivo en la sustentación | `docs/pruebas.md` |

## Amenazas relacionadas con IA y respuesta

| Amenaza | Respuesta en este proyecto |
|---|---|
| Fuga de datos al pegar en una IA pública IPs reales, credenciales o el `.env` | Solo se compartieron con la IA datos de ejemplo; el `.env` nunca se sube ni se comparte |
| Prompt injection desde fuentes externas | Ningún comando sugerido por una IA o leído de afuera se ejecuta sin pasar por la vista previa, la auditoría y la validación de la herramienta |
| Código inseguro generado por IA | Todo el código se revisó y se cubrió con pruebas automáticas antes de subirlo |
| Configuraciones peligrosas | Auditoría automática de configuraciones (política 4) |
| Sobreconfianza en la IA | Cada respuesta se trató como borrador; la calidad se mide con el % de confianza |

## Declaración de uso de IA

| Campo | Respuesta |
|---|---|
| Herramienta de IA utilizada | Asistente de IA conversacional (Claude, de Anthropic) |
| Para qué se usó | Generar y explicar el código de la aplicación, las plantillas de configuración, las pruebas automáticas y borradores de la documentación |
| Qué hice yo | Definí los requerimientos y el escenario, revisé y probé cada módulo, ejecuté las pruebas, verifiqué el subnetting a mano y validé las configuraciones en laboratorio *(completar con lo que corresponda)* |
| Datos compartidos con la IA | Solo datos de ejemplo; ninguna IP, credencial ni topología real |

**Declaración:** declaro que revisé, comprendí y probé el contenido entregado, y que puedo explicarlo en la sustentación.

| Nombre | Firma | Fecha |
|---|---|---|
| Angel Mauricio Cruz Gonzalez | | |
