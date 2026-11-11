# Modelo de amenazas y controles de ciberdefensa

Complemento técnico del Módulo 6 (Corte 3).

## Superficie de ataque

| Activo | Amenaza | Control implementado |
|---|---|---|
| Formularios de diseño (M1) | Valores fuera de rango, CIDR mal formados, nombres con caracteres que rompen el CLI | Validación con lista blanca y `ipaddress(strict=True)`; el plan se recalcula antes de guardar (fail-closed) |
| Consola NetDevOps (M5) | Inyección de comandos (`;`, `&&`, `` ` ``, `$()`, saltos de línea ocultos) | `validate_command`: tokens prohibidos, caracteres de control, longitud máx. 256, máx. 50 comandos |
| Consola NetDevOps (M5) | Ejecución accidental de `reload`, `erase`, `factoryreset` | Detección de comandos destructivos por fabricante; requieren interruptor explícito |
| Terminal web | XSS a partir de la salida de un equipo comprometido | `html.escape` antes de pintar; Mermaid con `securityLevel: "strict"` y código pasado como JSON |
| Transporte SSH | MITM / suplantación del equipo | `RejectPolicy` contra `known_hosts`; aceptar claves solo con `ALLOW_UNKNOWN_HOSTS=true` (laboratorio) |
| Despliegue a equipos (M5) | Cambio accidental en el equipo equivocado, configuración a medias, bloqueo del acceso | Confirmación escribiendo el hostname, respaldo previo, fail-fast sin guardar, hardening bloqueado sin usuario local en `.env`, validación de cada línea (sin control ni marcadores) |
| Transporte Telnet | Credenciales en claro | Solo IP privadas/loopback y con `ENABLE_TELNET_LAB=true` |
| Credenciales | Fuga a git, logs o pantalla | `.env` en `.gitignore`, `repr=False` en la contraseña, `redact_secrets` en toda salida y log |
| Configuraciones generadas | Secretos en archivos descargables | Plantillas con marcadores `<<ADMIN_SECRET>>`, `<<VPN_PSK>>`, etc.; `configs_out/` ignorado |
| Streamlit | CSRF, fuga de trazas | `enableXsrfProtection = true`, `showErrorDetails = false` en `.streamlit/config.toml` |

## Hardening incluido en las configuraciones

- SSH v2 únicamente, Telnet deshabilitado, ACL de gestión limitada a la VLAN 99, timeouts de sesión.
- Contraseñas con hash fuerte (`scrypt` en Cisco, `irreversible-cipher` en Huawei).
- Bloqueo por intentos fallidos (`login block-for`, `admin-lockout-threshold`).
- SNMPv3 con autenticación y cifrado (sin comunidades v2c).
- Acceso: port-security, BPDU guard, DHCP snooping, VLAN nativa 999 y puertos sin uso apagados.
- Borde: ACL anti-spoofing RFC 1918, PAT, IPsec IKEv2 con AES-256-GCM y DH 19/20.

## Procedimiento ante una fuga de credenciales

1. Rotar inmediatamente la credencial en los equipos afectados.
2. Eliminar el secreto del historial de git (`git filter-repo`) y forzar la actualización del remoto.
3. Revisar los logs de autenticación de los equipos en la ventana de exposición.
4. Registrar el incidente y volver a ejecutar `python scripts/generate_test_report.py`.
