# docs/pruebas.md — Reporte de pruebas

> Generado automáticamente por `core/quality.py` el 2026-11-11 19:57 al ejecutar `pytest`. No se edita a mano: para regenerarlo, `python scripts/generate_test_report.py`.

## Resultado

**Pruebas superadas: 284 de 284 = 100% de confianza**

- Controles de seguridad del repositorio: 9 de 9
- Módulos con pruebas que pasan: 11 de 11
- Duración de la ejecución: 66.3 s

## Cómo se corren (también en la sustentación)

```bash
pytest -q                                   # ejecuta todas las pruebas
python scripts/generate_test_report.py      # vuelve a escribir este archivo
```

En la app: Módulo 6 → «Ejecutar batería de pruebas y generar docs/pruebas.md».

## Resultados por módulo

| Grupo | Módulo | Superadas / Total |
|---|---|---:|
| `test_ipam` | M2 · Planificación IP | 33 / 33 |
| `test_topology` | M3 · Topología | 7 / 7 |
| `test_topology_io` | M3 · Carga de topología | 24 / 24 |
| `test_generators` | M4 · Configuraciones multi-marca | 36 / 36 |
| `test_netdevops` | M5 · Consola NetDevOps | 16 / 16 |
| `test_deploy` | M5 · Despliegue a equipos | 49 / 49 |
| `test_serial` | M5 · Consola serial (COM) | 16 / 16 |
| `test_validators` | M6 · Validación de entradas | 42 / 42 |
| `test_security` | M6 · Anti-fuga de credenciales | 8 / 8 |
| `test_security_audit` | M6 · Configuraciones inseguras | 40 / 40 |
| `test_app` | UI · Streamlit (AppTest) | 13 / 13 |

## Qué probé

- [P1] Streamlit (AppTest): modulo renderiza sin errores [01  Requerimientos] -> OK
- [P2] Streamlit (AppTest): modulo renderiza sin errores [02  Planificaci\xf3n IP] -> OK
- [P3] Streamlit (AppTest): modulo renderiza sin errores [03  Topolog\xeda] -> OK
- [P4] Streamlit (AppTest): modulo renderiza sin errores [04  Configuraciones] -> OK
- [P5] Streamlit (AppTest): modulo renderiza sin errores [05  Conexi\xf3n y despliegue] -> OK
- [P6] Streamlit (AppTest): modulo renderiza sin errores [06  Ciberdefensa y pruebas] -> OK
- [P7] Streamlit (AppTest): estado global sincroniza modulos -> OK
- [P8] Streamlit (AppTest): despliegue simulado configura el equipo -> OK
- [P9] Streamlit (AppTest): terminal simulada ejecuta lote -> OK
- [P10] Streamlit (AppTest): terminal bloquea inyeccion -> OK
- [P11] Streamlit (AppTest): modo consola serial renderiza -> OK
- [P12] Streamlit (AppTest): carga de topologia desde la interfaz -> OK
- [P13] Streamlit (AppTest): auditoria de configuracion insegura en la interfaz -> OK
- [P14] Despliegue a equipos: bloques cubren toda la configuracion [Cisco] -> OK
- [P15] Despliegue a equipos: bloques cubren toda la configuracion [Huawei] -> OK
- [P16] Despliegue a equipos: bloques cubren toda la configuracion [Fortinet] -> OK
- [P17] Despliegue a equipos: bloques cubren toda la configuracion [MikroTik] -> OK
- [P18] Despliegue a equipos: hostname vlans e ip se clasifican [Cisco] -> OK
- [P19] Despliegue a equipos: hostname vlans e ip se clasifican [Huawei] -> OK
- [P20] Despliegue a equipos: hostname vlans e ip se clasifican [Fortinet] -> OK
- [P21] Despliegue a equipos: hostname vlans e ip se clasifican [MikroTik] -> OK
- [P22] Despliegue a equipos: dependencias se agregan en switches -> OK
- [P23] Despliegue a equipos: plan basico para todos los equipos [R-CORE-Cisco] -> OK
- [P24] Despliegue a equipos: plan basico para todos los equipos [R-CORE-Huawei] -> OK
- [P25] Despliegue a equipos: plan basico para todos los equipos [R-CORE-Fortinet] -> OK
- [P26] Despliegue a equipos: plan basico para todos los equipos [R-CORE-MikroTik] -> OK
- [P27] Despliegue a equipos: plan basico para todos los equipos [R-DIST-Cisco] -> OK
- [P28] Despliegue a equipos: plan basico para todos los equipos [R-DIST-Huawei] -> OK
- [P29] Despliegue a equipos: plan basico para todos los equipos [R-DIST-Fortinet] -> OK
- [P30] Despliegue a equipos: plan basico para todos los equipos [R-DIST-MikroTik] -> OK
- [P31] Despliegue a equipos: plan basico para todos los equipos [SW-CORE-Cisco] -> OK
- [P32] Despliegue a equipos: plan basico para todos los equipos [SW-CORE-Huawei] -> OK
- [P33] Despliegue a equipos: plan basico para todos los equipos [SW-CORE-Fortinet] -> OK
- [P34] Despliegue a equipos: plan basico para todos los equipos [SW-CORE-MikroTik] -> OK
- [P35] Despliegue a equipos: plan basico para todos los equipos [SW-ACC-P01-1-Cisco] -> OK
- [P36] Despliegue a equipos: plan basico para todos los equipos [SW-ACC-P01-1-Huawei] -> OK
- [P37] Despliegue a equipos: plan basico para todos los equipos [SW-ACC-P01-1-Fortinet] -> OK
- [P38] Despliegue a equipos: plan basico para todos los equipos [SW-ACC-P01-1-MikroTik] -> OK
- [P39] Despliegue a equipos: plan basico para todos los equipos [SW-SRV-Cisco] -> OK
- [P40] Despliegue a equipos: plan basico para todos los equipos [SW-SRV-Huawei] -> OK
- [P41] Despliegue a equipos: plan basico para todos los equipos [SW-SRV-Fortinet] -> OK
- [P42] Despliegue a equipos: plan basico para todos los equipos [SW-SRV-MikroTik] -> OK
- [P43] Despliegue a equipos: ip sin servicios quita nat y acl -> OK
- [P44] Despliegue a equipos: puertos encendidos y sin uso apagados -> OK
- [P45] Despliegue a equipos: hardening bloqueado sin secretos -> OK
- [P46] Despliegue a equipos: hardening con secretos del env -> OK
- [P47] Despliegue a equipos: vpn sin peer se omite -> OK
- [P48] Despliegue a equipos: categoria invalida -> OK
- [P49] Despliegue a equipos: sin guardar no envia write memory -> OK
- [P50] Despliegue a equipos: simulador pasa de fabrica a configurado [Cisco] -> OK
- [P51] Despliegue a equipos: simulador pasa de fabrica a configurado [Huawei] -> OK
- [P52] Despliegue a equipos: simulador pasa de fabrica a configurado [Fortinet] -> OK
- [P53] Despliegue a equipos: simulador pasa de fabrica a configurado [MikroTik] -> OK
- [P54] Despliegue a equipos: respaldo se guarda -> OK
- [P55] Despliegue a equipos: deteccion de errores por fabricante [Cisco-% Invalid input detected at '^' marker.] -> OK
- [P56] Despliegue a equipos: deteccion de errores por fabricante [Huawei-Error: Unrecognized command found at '^' po…] -> OK
- [P57] Despliegue a equipos: deteccion de errores por fabricante [Fortinet-Command fail. Return code -61] -> OK
- [P58] Despliegue a equipos: deteccion de errores por fabricante [MikroTik-bad command name foo (line 1 column 1)] -> OK
- [P59] Despliegue a equipos: detenerse en error no guarda -> OK
- [P60] Despliegue a equipos: linea de configuracion validada -> OK
- [P61] Despliegue a equipos: despliegue ssh completo -> OK
- [P62] Despliegue a equipos: despliegue ssh se detiene ante error -> OK
- [P63] Configuraciones multi-marca: un archivo por equipo [Cisco] -> OK
- [P64] Configuraciones multi-marca: un archivo por equipo [Huawei] -> OK
- [P65] Configuraciones multi-marca: un archivo por equipo [Fortinet] -> OK
- [P66] Configuraciones multi-marca: un archivo por equipo [MikroTik] -> OK
- [P67] Configuraciones multi-marca: ips del plan aparecen en las configs [Cisco] -> OK
- [P68] Configuraciones multi-marca: ips del plan aparecen en las configs [Huawei] -> OK
- [P69] Configuraciones multi-marca: ips del plan aparecen en las configs [Fortinet] -> OK
- [P70] Configuraciones multi-marca: ips del plan aparecen en las configs [MikroTik] -> OK
- [P71] Configuraciones multi-marca: todos los tipos de vpn [IPsec-Cisco] -> OK
- [P72] Configuraciones multi-marca: todos los tipos de vpn [IPsec-Huawei] -> OK
- [P73] Configuraciones multi-marca: todos los tipos de vpn [IPsec-Fortinet] -> OK
- [P74] Configuraciones multi-marca: todos los tipos de vpn [IPsec-MikroTik] -> OK
- [P75] Configuraciones multi-marca: todos los tipos de vpn [SSL-Cisco] -> OK
- [P76] Configuraciones multi-marca: todos los tipos de vpn [SSL-Huawei] -> OK
- [P77] Configuraciones multi-marca: todos los tipos de vpn [SSL-Fortinet] -> OK
- [P78] Configuraciones multi-marca: todos los tipos de vpn [SSL-MikroTik] -> OK
- [P79] Configuraciones multi-marca: todos los tipos de vpn [MPLS-Cisco] -> OK
- [P80] Configuraciones multi-marca: todos los tipos de vpn [MPLS-Huawei] -> OK
- [P81] Configuraciones multi-marca: todos los tipos de vpn [MPLS-Fortinet] -> OK
- [P82] Configuraciones multi-marca: todos los tipos de vpn [MPLS-MikroTik] -> OK
- [P83] Configuraciones multi-marca: todos los tipos de vpn [Ninguna-Cisco] -> OK
- [P84] Configuraciones multi-marca: todos los tipos de vpn [Ninguna-Huawei] -> OK
- [P85] Configuraciones multi-marca: todos los tipos de vpn [Ninguna-Fortinet] -> OK
- [P86] Configuraciones multi-marca: todos los tipos de vpn [Ninguna-MikroTik] -> OK
- [P87] Configuraciones multi-marca: sin secretos reales solo marcadores [Cisco] -> OK
- [P88] Configuraciones multi-marca: sin secretos reales solo marcadores [Huawei] -> OK
- [P89] Configuraciones multi-marca: sin secretos reales solo marcadores [Fortinet] -> OK
- [P90] Configuraciones multi-marca: sin secretos reales solo marcadores [MikroTik] -> OK
- [P91] Configuraciones multi-marca: parametros remotos reemplazan marcadores -> OK
- [P92] Configuraciones multi-marca: cisco acceso endurecido -> OK
- [P93] Configuraciones multi-marca: huawei usa sintaxis vrp -> OK
- [P94] Configuraciones multi-marca: fortinet politicas explicitas -> OK
- [P95] Configuraciones multi-marca: mikrotik vlan filtering al final -> OK
- [P96] Configuraciones multi-marca: plan de puertos no excede 48 -> OK
- [P97] Configuraciones multi-marca: zip contiene todos los archivos -> OK
- [P98] Configuraciones multi-marca: fabricante invalido -> OK
- [P99] Planificación IP: prefijo minimo para hosts [1-29] -> OK
- [P100] Planificación IP: prefijo minimo para hosts [6-29] -> OK
- [P101] Planificación IP: prefijo minimo para hosts [7-28] -> OK
- [P102] Planificación IP: prefijo minimo para hosts [14-28] -> OK
- [P103] Planificación IP: prefijo minimo para hosts [30-27] -> OK
- [P104] Planificación IP: prefijo minimo para hosts [50-26] -> OK
- [P105] Planificación IP: prefijo minimo para hosts [62-26] -> OK
- [P106] Planificación IP: prefijo minimo para hosts [63-25] -> OK
- [P107] Planificación IP: prefijo minimo para hosts [126-25] -> OK
- [P108] Planificación IP: prefijo minimo para hosts [254-24] -> OK
- [P109] Planificación IP: prefijo minimo para hosts [510-23] -> OK
- [P110] Planificación IP: prefijo minimo para hosts [750-22] -> OK
- [P111] Planificación IP: crecimiento redondea hacia arriba -> OK
- [P112] Planificación IP: escenario 15 pisos genera un 26 por piso -> OK
- [P113] Planificación IP: calculo manual de un 26 -> OK
- [P114] Planificación IP: ninguna subred se solapa -> OK
- [P115] Planificación IP: todas las subredes caben en la base -> OK
- [P116] Planificación IP: vlsm alineado a frontera -> OK
- [P117] Planificación IP: cada segmento aloja sus hosts -> OK
- [P118] Planificación IP: enlaces wan son 30 estrictos -> OK
- [P119] Planificación IP: enlaces wan contiguos sin desperdicio -> OK
- [P120] Planificación IP: ipv6 un 64 unico por vlan -> OK
- [P121] Planificación IP: ipv6 p2p 127 -> OK
- [P122] Planificación IP: ipv6 bloque 56 usa vlan decimal -> OK
- [P123] Planificación IP: ruta sumarizada cubre todo -> OK
- [P124] Planificación IP: base insuficiente falla con mensaje claro -> OK
- [P125] Planificación IP: bloque wan no puede solapar lan -> OK
- [P126] Planificación IP: escalabilidad multiples escenarios [1-10] -> OK
- [P127] Planificación IP: escalabilidad multiples escenarios [3-120] -> OK
- [P128] Planificación IP: escalabilidad multiples escenarios [8-1600] -> OK
- [P129] Planificación IP: escalabilidad multiples escenarios [40-4000] -> OK
- [P130] Planificación IP: servicios opcionales se omiten -> OK
- [P131] Planificación IP: p2p link propiedades -> OK
- [P132] Consola NetDevOps: ssh rechaza host desconocido por defecto -> OK
- [P133] Consola NetDevOps: ssh lote en modo laboratorio y redacta secretos -> OK
- [P134] Consola NetDevOps: ssh contrasena incorrecta -> OK
- [P135] Consola NetDevOps: ssh puerto cerrado -> OK
- [P136] Consola NetDevOps: ssh parametros invalidos -> OK
- [P137] Consola NetDevOps: telnet bloquea destinos publicos -> OK
- [P138] Consola NetDevOps: telnet deshabilitado por defecto -> OK
- [P139] Consola NetDevOps: telnet negocia iac y ejecuta -> OK
- [P140] Consola NetDevOps: simulador interfaces desde el plan [Cisco-show ip interface brief] -> OK
- [P141] Consola NetDevOps: simulador interfaces desde el plan [Huawei-display ip interface brief] -> OK
- [P142] Consola NetDevOps: simulador interfaces desde el plan [Fortinet-get system interface] -> OK
- [P143] Consola NetDevOps: simulador interfaces desde el plan [MikroTik-/ip address print] -> OK
- [P144] Consola NetDevOps: simulador rutas ospf y ping -> OK
- [P145] Consola NetDevOps: simulador vlans de acceso -> OK
- [P146] Consola NetDevOps: simulador redacta running config -> OK
- [P147] Consola NetDevOps: simulador valida comandos -> OK
- [P148] Anti-fuga de credenciales: gitignore excluye env y salidas -> OK
- [P149] Anti-fuga de credenciales: env example sin valores secretos -> OK
- [P150] Anti-fuga de credenciales: no hay secretos hardcodeados en el codigo -> OK
- [P151] Anti-fuga de credenciales: escaner detecta un secreto plantado -> OK
- [P152] Anti-fuga de credenciales: redaccion multi fabricante -> OK
- [P153] Anti-fuga de credenciales: redaccion de contrasena conocida en salida -> OK
- [P154] Anti-fuga de credenciales: password no aparece en repr -> OK
- [P155] Anti-fuga de credenciales: reporte de confianza formula -> OK
- [P156] Configuraciones inseguras: configuraciones generadas sin riesgos [IPsec-Cisco] -> OK
- [P157] Configuraciones inseguras: configuraciones generadas sin riesgos [IPsec-Huawei] -> OK
- [P158] Configuraciones inseguras: configuraciones generadas sin riesgos [IPsec-Fortinet] -> OK
- [P159] Configuraciones inseguras: configuraciones generadas sin riesgos [IPsec-MikroTik] -> OK
- [P160] Configuraciones inseguras: configuraciones generadas sin riesgos [SSL-Cisco] -> OK
- [P161] Configuraciones inseguras: configuraciones generadas sin riesgos [SSL-Huawei] -> OK
- [P162] Configuraciones inseguras: configuraciones generadas sin riesgos [SSL-Fortinet] -> OK
- [P163] Configuraciones inseguras: configuraciones generadas sin riesgos [SSL-MikroTik] -> OK
- [P164] Configuraciones inseguras: configuraciones generadas sin riesgos [MPLS-Cisco] -> OK
- [P165] Configuraciones inseguras: configuraciones generadas sin riesgos [MPLS-Huawei] -> OK
- [P166] Configuraciones inseguras: configuraciones generadas sin riesgos [MPLS-Fortinet] -> OK
- [P167] Configuraciones inseguras: configuraciones generadas sin riesgos [MPLS-MikroTik] -> OK
- [P168] Configuraciones inseguras: configuraciones generadas sin riesgos [Ninguna-Cisco] -> OK
- [P169] Configuraciones inseguras: configuraciones generadas sin riesgos [Ninguna-Huawei] -> OK
- [P170] Configuraciones inseguras: configuraciones generadas sin riesgos [Ninguna-Fortinet] -> OK
- [P171] Configuraciones inseguras: configuraciones generadas sin riesgos [Ninguna-MikroTik] -> OK
- [P172] Configuraciones inseguras: ejemplo inseguro detecta todo -> OK
- [P173] Configuraciones inseguras: reglas por fabricante [line vty 0 4\n transport input all\n access-class …] -> OK
- [P174] Configuraciones inseguras: reglas por fabricante [telnet server enable-telnet] -> OK
- [P175] Configuraciones inseguras: reglas por fabricante [user-interface vty 0 4\n protocol inbound telnet-t…] -> OK
- [P176] Configuraciones inseguras: reglas por fabricante [edit "port2"\n    set allowaccess ping telnet http…] -> OK
- [P177] Configuraciones inseguras: reglas por fabricante [/ip service enable telnet-telnet] -> OK
- [P178] Configuraciones inseguras: reglas por fabricante [ip ssh version 1-ssh-v1] -> OK
- [P179] Configuraciones inseguras: reglas por fabricante [snmp-agent community read public-snmp] -> OK
- [P180] Configuraciones inseguras: reglas por fabricante [/snmp community add name=public-snmp] -> OK
- [P181] Configuraciones inseguras: reglas por fabricante [snmp-server community Lab123 RW-snmp] -> OK
- [P182] Configuraciones inseguras: reglas por fabricante [local-user admin password simple admin-cred-defaul…] -> OK
- [P183] Configuraciones inseguras: reglas por fabricante [/user add name=admin password="admin" group=full-c…] -> OK
- [P184] Configuraciones inseguras: reglas por fabricante [aaa\n local-user ops password simple Zx9!kq7-clear…] -> OK
- [P185] Configuraciones inseguras: reglas por fabricante [ 10 permit ip any any-permit-any] -> OK
- [P186] Configuraciones inseguras: lineas seguras no alertan [undo telnet server enable] -> OK
- [P187] Configuraciones inseguras: lineas seguras no alertan [transport input ssh] -> OK
- [P188] Configuraciones inseguras: lineas seguras no alertan [ip ssh version 2] -> OK
- [P189] Configuraciones inseguras: lineas seguras no alertan [snmp-server group NETOPS v3 priv] -> OK
- [P190] Configuraciones inseguras: lineas seguras no alertan [/ip service disable telnet,ftp,www,api,api-ssl] -> OK
- [P191] Configuraciones inseguras: lineas seguras no alertan [! transport input telnet] -> OK
- [P192] Configuraciones inseguras: fortinet wan administrable y politica todo -> OK
- [P193] Configuraciones inseguras: mikrotik admin de fabrica activo -> OK
- [P194] Configuraciones inseguras: hallazgos ordenados por severidad -> OK
- [P195] Configuraciones inseguras: resumen del equipo hostname vlan ip -> OK
- [P196] Consola serial (COM): equipo de fabrica supera dialogo y entra a enable -> OK
- [P197] Consola serial (COM): despliegue por consola configura nombre e ip -> OK
- [P198] Consola serial (COM): login de consola con usuario -> OK
- [P199] Consola serial (COM): login de consola pide usuario si falta -> OK
- [P200] Consola serial (COM): puerto inexistente mensaje claro -> OK
- [P201] Consola serial (COM): puertos validos [COM1] -> OK
- [P202] Consola serial (COM): puertos validos [COM12] -> OK
- [P203] Consola serial (COM): puertos validos [/dev/ttyUSB0] -> OK
- [P204] Consola serial (COM): puertos validos [/dev/tty.usbserial-1410] -> OK
- [P205] Consola serial (COM): puertos invalidos [COM1; del *] -> OK
- [P206] Consola serial (COM): puertos invalidos [http://x] -> OK
- [P207] Consola serial (COM): puertos invalidos [socket://8.8.8.8:23] -> OK
- [P208] Consola serial (COM): puertos invalidos [] -> OK
- [P209] Consola serial (COM): puertos invalidos [LPT1] -> OK
- [P210] Consola serial (COM): velocidad invalida -> OK
- [P211] Consola serial (COM): listado de puertos no falla -> OK
- [P212] Topología: jerarquia completa -> OK
- [P213] Topología: cada piso tiene acceso -> OK
- [P214] Topología: ips de gestion unicas y en vlan 99 -> OK
- [P215] Topología: etiquetas de enlaces salen del plan -> OK
- [P216] Topología: dot y mermaid validos -> OK
- [P217] Topología: switches extra si el piso supera 48 puertos -> OK
- [P218] Topología: ssl vpn dibuja usuarios remotos -> OK
- [P219] Carga de topología: exportar e importar json es identico -> OK
- [P220] Carga de topología: importar csv -> OK
- [P221] Carga de topología: renombrar equipo cambia la configuracion -> OK
- [P222] Carga de topología: agregar router y enlace wan asigna 30 y configura -> OK
- [P223] Carga de topología: agregar switch de acceso reparte puertos -> OK
- [P224] Carga de topología: validacion rechaza errores [<lambda>-Hostname inv\xe1lido] -> OK
- [P225] Carga de topología: validacion rechaza errores [<lambda>-rol 'firewall'] -> OK
- [P226] Carga de topología: validacion rechaza errores [<lambda>-debe estar dentro] -> OK
- [P227] Carga de topología: validacion rechaza errores [<lambda>-piso entre 1] -> OK
- [P228] Carga de topología: validacion rechaza errores [<lambda>-no existe] -> OK
- [P229] Carga de topología: validacion rechaza errores [<lambda>-consigo mismo] -> OK
- [P230] Carga de topología: validacion rechaza errores [<lambda>-duplicado] -> OK
- [P231] Carga de topología: validacion rechaza errores [<lambda>-tipo 'satelite'] -> OK
- [P232] Carga de topología: validacion rechaza errores [<lambda>-repetido] -> OK
- [P233] Carga de topología: validacion rechaza errores [<lambda>-IP de gesti\xf3n repetida] -> OK
- [P234] Carga de topología: validacion rechaza errores [<lambda>-gateway de gesti\xf3n] -> OK
- [P235] Carga de topología: columna vertebral obligatoria -> OK
- [P236] Carga de topología: acceso sin troncal rechazado -> OK
- [P237] Carga de topología: todos los errores juntos -> OK
- [P238] Carga de topología: json invalido [no es json] -> OK
- [P239] Carga de topología: json invalido [{"dispositivos": 3}] -> OK
- [P240] Carga de topología: json invalido [\xff\xfe\x00] -> OK
- [P241] Carga de topología: csv sin columnas -> OK
- [P242] Carga de topología: archivo demasiado grande -> OK
- [P243] Validación de entradas: comandos legitimos aceptados [show ip int brief] -> OK
- [P244] Validación de entradas: comandos legitimos aceptados [show run / include hostname] -> OK
- [P245] Validación de entradas: comandos legitimos aceptados [display current-configuration / include sysname] -> OK
- [P246] Validación de entradas: comandos legitimos aceptados [/ip address print] -> OK
- [P247] Validación de entradas: comandos legitimos aceptados [get system status] -> OK
- [P248] Validación de entradas: comandos legitimos aceptados [ping 10.20.7.1] -> OK
- [P249] Validación de entradas: inyecciones bloqueadas [show ver ; reload] -> OK
- [P250] Validación de entradas: inyecciones bloqueadas [show ver && reload] -> OK
- [P251] Validación de entradas: inyecciones bloqueadas [show `id`] -> OK
- [P252] Validación de entradas: inyecciones bloqueadas [show $(whoami)] -> OK
- [P253] Validación de entradas: inyecciones bloqueadas [show run > /tmp/x] -> OK
- [P254] Validación de entradas: inyecciones bloqueadas [show ver\nreload] -> OK
- [P255] Validación de entradas: inyecciones bloqueadas [show ver\rreload] -> OK
- [P256] Validación de entradas: inyecciones bloqueadas [show\x00ver] -> OK
- [P257] Validación de entradas: inyecciones bloqueadas [aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa…] -> OK
- [P258] Validación de entradas: inyecciones bloqueadas [] -> OK
- [P259] Validación de entradas: inyecciones bloqueadas [   ] -> OK
- [P260] Validación de entradas: destructivos detectados [reload] -> OK
- [P261] Validación de entradas: destructivos detectados [write erase] -> OK
- [P262] Validación de entradas: destructivos detectados [erase startup-config] -> OK
- [P263] Validación de entradas: destructivos detectados [reset saved-configuration] -> OK
- [P264] Validación de entradas: destructivos detectados [execute factoryreset] -> OK
- [P265] Validación de entradas: destructivos detectados [/system reset-configuration] -> OK
- [P266] Validación de entradas: destructivos detectados [delete flash:x] -> OK
- [P267] Validación de entradas: lote rechaza destructivo sin confirmacion -> OK
- [P268] Validación de entradas: lote ignora comentarios y limita tamano -> OK
- [P269] Validación de entradas: lote fail closed indica linea -> OK
- [P270] Validación de entradas: redes base validas [10.20.0.0/16] -> OK
- [P271] Validación de entradas: redes base validas [172.16.0.0/12] -> OK
- [P272] Validación de entradas: redes base validas [192.168.0.0/22] -> OK
- [P273] Validación de entradas: redes base validas [100.64.0.0/16] -> OK
- [P274] Validación de entradas: redes base invalidas [10.20.0.5/16] -> OK
- [P275] Validación de entradas: redes base invalidas [8.8.8.0/24] -> OK
- [P276] Validación de entradas: redes base invalidas [10.0.0.0/30] -> OK
- [P277] Validación de entradas: redes base invalidas [hola] -> OK
- [P278] Validación de entradas: redes base invalidas [300.1.1.0/24] -> OK
- [P279] Validación de entradas: redes base invalidas [] -> OK
- [P280] Validación de entradas: ipv6 valida e invalida -> OK
- [P281] Validación de entradas: nombres y hostnames -> OK
- [P282] Validación de entradas: destinos ssh -> OK
- [P283] Validación de entradas: escape html previene xss -> OK
- [P284] Validación de entradas: config global reporta todos los errores -> OK

## Qué falta / errores encontrados

- Ninguna prueba falla en esta ejecución.
- Pendiente fuera del alcance: probar el despliegue contra equipos físicos del laboratorio (hoy se valida contra un Cisco emulado por SSH y por consola serial).

## Controles de ciberdefensa del repositorio

| Control | Estado | Detalle |
|---|:---:|---|
| .gitignore existe | OK | .gitignore |
| .env excluido por .gitignore | OK | Entrada '.env' en .gitignore |
| Salidas de configuración excluidas | OK | configs_out/ puede contener secretos sustituidos |
| .env.example presente (sin valores reales) | OK | Plantilla de variables para el equipo |
| .env.example no contiene secretos | OK | Valores vacíos o genéricos |
| .env no está versionado en git | OK | git ls-files .env vacío |
| Sin secretos hardcodeados en el código | OK | 0 coincidencias |
| Documento docs/politicas-ia.md presente | OK | docs/politicas-ia.md |
| Documento docs/seguridad.md presente | OK | docs/seguridad.md |

## Metodología

- **Unitarias:** subredes contra cálculos manuales (red, broadcast, máscara, gateway) y 2 IP útiles en /30.
- **Propiedades:** ninguna subred se solapa, todas caben en la red base, cada VLAN tiene un /64 único.
- **Topología:** importar/exportar JSON y CSV, validación de dispositivos y enlaces, /30 automáticos.
- **Generadores:** cada marca produce un archivo por equipo, sin secretos reales y con las IP del plan.
- **Ciberdefensa:** inyección de comandos, XSS, enmascarado de contraseñas, configuraciones inseguras.
- **Conexión:** despliegue por SSH y por consola serial contra un Cisco emulado; detención ante errores.
- **Interfaz:** cada módulo se ejecuta con `streamlit.testing.AppTest` sin excepciones.
