# Reporte de pruebas y porcentaje de confianza

> Generado automáticamente por `core/quality.py` el 2026-11-10 23:59. No editar a mano: vuelva a ejecutar `python scripts/generate_test_report.py`.

## Resultado: **100.0 %** de confianza (nivel ALTA)

| Componente | Peso | Puntaje | Aporte |
|---|---:|---:|---:|
| Pruebas automatizadas superadas | 60 % | 100.0 % | 60.0 |
| Controles de seguridad cumplidos | 25 % | 100.0 % | 25.0 |
| Cobertura de categorías | 15 % | 100.0 % | 15.0 |

**Fórmula:** `Confianza = 0.60·(pruebas OK / total) + 0.25·(controles OK / total) + 0.15·(categorías con pruebas OK / categorías)`

Total de pruebas: **218** · Superadas: **218** · Fallidas: **0** · Duración: 65.7 s

## Resultados por módulo

| Categoría | Módulo | OK / Total |
|---|---|---:|
| `test_ipam` | M2 · Planificación IP | 33 / 33 |
| `test_topology` | M3 · Topología | 7 / 7 |
| `test_generators` | M4 · Configuraciones multi-marca | 36 / 36 |
| `test_netdevops` | M5 · Consola NetDevOps | 16 / 16 |
| `test_deploy` | M5 · Despliegue a equipos | 49 / 49 |
| `test_serial` | M5 · Consola serial (COM) | 16 / 16 |
| `test_validators` | M6 · Validación de entradas | 42 / 42 |
| `test_security` | M6 · Anti-fuga de credenciales | 8 / 8 |
| `test_app` | UI · Streamlit (AppTest) | 11 / 11 |

## Controles de ciberdefensa

| Control | Estado | Detalle |
|---|:---:|---|
| .gitignore existe | ✅ | .gitignore |
| .env excluido por .gitignore | ✅ | Entrada '.env' en .gitignore |
| Salidas de configuración excluidas | ✅ | configs_out/ puede contener secretos sustituidos |
| .env.example presente (sin valores reales) | ✅ | Plantilla de variables para el equipo |
| .env.example no contiene secretos | ✅ | Valores vacíos o genéricos |
| .env no está versionado en git | ✅ | git ls-files .env vacío |
| Sin secretos hardcodeados en el código | ✅ | 0 coincidencias |
| Documento docs/politicas-ia.md presente | ✅ | docs/politicas-ia.md |
| Documento docs/seguridad.md presente | ✅ | docs/seguridad.md |

## Pruebas fallidas

Ninguna.

## Detalle de casos de prueba

| Categoría | Caso | Estado |
|---|---|:---:|
| test_app | `test_modulo_renderiza_sin_errores[01  Requerimientos]` | ✅ |
| test_app | `test_modulo_renderiza_sin_errores[02  Planificaci\xf3n IP]` | ✅ |
| test_app | `test_modulo_renderiza_sin_errores[03  Topolog\xeda]` | ✅ |
| test_app | `test_modulo_renderiza_sin_errores[04  Configuraciones]` | ✅ |
| test_app | `test_modulo_renderiza_sin_errores[05  Conexi\xf3n y despliegue]` | ✅ |
| test_app | `test_modulo_renderiza_sin_errores[06  Ciberdefensa y pruebas]` | ✅ |
| test_app | `test_estado_global_sincroniza_modulos` | ✅ |
| test_app | `test_despliegue_simulado_configura_el_equipo` | ✅ |
| test_app | `test_terminal_simulada_ejecuta_lote` | ✅ |
| test_app | `test_terminal_bloquea_inyeccion` | ✅ |
| test_app | `test_modo_consola_serial_renderiza` | ✅ |
| test_deploy | `test_bloques_cubren_toda_la_configuracion[Cisco]` | ✅ |
| test_deploy | `test_bloques_cubren_toda_la_configuracion[Huawei]` | ✅ |
| test_deploy | `test_bloques_cubren_toda_la_configuracion[Fortinet]` | ✅ |
| test_deploy | `test_bloques_cubren_toda_la_configuracion[MikroTik]` | ✅ |
| test_deploy | `test_hostname_vlans_e_ip_se_clasifican[Cisco]` | ✅ |
| test_deploy | `test_hostname_vlans_e_ip_se_clasifican[Huawei]` | ✅ |
| test_deploy | `test_hostname_vlans_e_ip_se_clasifican[Fortinet]` | ✅ |
| test_deploy | `test_hostname_vlans_e_ip_se_clasifican[MikroTik]` | ✅ |
| test_deploy | `test_dependencias_se_agregan_en_switches` | ✅ |
| test_deploy | `test_plan_basico_para_todos_los_equipos[R-CORE-Cisco]` | ✅ |
| test_deploy | `test_plan_basico_para_todos_los_equipos[R-CORE-Huawei]` | ✅ |
| test_deploy | `test_plan_basico_para_todos_los_equipos[R-CORE-Fortinet]` | ✅ |
| test_deploy | `test_plan_basico_para_todos_los_equipos[R-CORE-MikroTik]` | ✅ |
| test_deploy | `test_plan_basico_para_todos_los_equipos[R-DIST-Cisco]` | ✅ |
| test_deploy | `test_plan_basico_para_todos_los_equipos[R-DIST-Huawei]` | ✅ |
| test_deploy | `test_plan_basico_para_todos_los_equipos[R-DIST-Fortinet]` | ✅ |
| test_deploy | `test_plan_basico_para_todos_los_equipos[R-DIST-MikroTik]` | ✅ |
| test_deploy | `test_plan_basico_para_todos_los_equipos[SW-CORE-Cisco]` | ✅ |
| test_deploy | `test_plan_basico_para_todos_los_equipos[SW-CORE-Huawei]` | ✅ |
| test_deploy | `test_plan_basico_para_todos_los_equipos[SW-CORE-Fortinet]` | ✅ |
| test_deploy | `test_plan_basico_para_todos_los_equipos[SW-CORE-MikroTik]` | ✅ |
| test_deploy | `test_plan_basico_para_todos_los_equipos[SW-ACC-P01-1-Cisco]` | ✅ |
| test_deploy | `test_plan_basico_para_todos_los_equipos[SW-ACC-P01-1-Huawei]` | ✅ |
| test_deploy | `test_plan_basico_para_todos_los_equipos[SW-ACC-P01-1-Fortinet]` | ✅ |
| test_deploy | `test_plan_basico_para_todos_los_equipos[SW-ACC-P01-1-MikroTik]` | ✅ |
| test_deploy | `test_plan_basico_para_todos_los_equipos[SW-SRV-Cisco]` | ✅ |
| test_deploy | `test_plan_basico_para_todos_los_equipos[SW-SRV-Huawei]` | ✅ |
| test_deploy | `test_plan_basico_para_todos_los_equipos[SW-SRV-Fortinet]` | ✅ |
| test_deploy | `test_plan_basico_para_todos_los_equipos[SW-SRV-MikroTik]` | ✅ |
| test_deploy | `test_ip_sin_servicios_quita_nat_y_acl` | ✅ |
| test_deploy | `test_puertos_encendidos_y_sin_uso_apagados` | ✅ |
| test_deploy | `test_hardening_bloqueado_sin_secretos` | ✅ |
| test_deploy | `test_hardening_con_secretos_del_env` | ✅ |
| test_deploy | `test_vpn_sin_peer_se_omite` | ✅ |
| test_deploy | `test_categoria_invalida` | ✅ |
| test_deploy | `test_sin_guardar_no_envia_write_memory` | ✅ |
| test_deploy | `test_simulador_pasa_de_fabrica_a_configurado[Cisco]` | ✅ |
| test_deploy | `test_simulador_pasa_de_fabrica_a_configurado[Huawei]` | ✅ |
| test_deploy | `test_simulador_pasa_de_fabrica_a_configurado[Fortinet]` | ✅ |
| test_deploy | `test_simulador_pasa_de_fabrica_a_configurado[MikroTik]` | ✅ |
| test_deploy | `test_respaldo_se_guarda` | ✅ |
| test_deploy | `test_deteccion_de_errores_por_fabricante[Cisco-% Invalid input detected at '^' marker.]` | ✅ |
| test_deploy | `test_deteccion_de_errores_por_fabricante[Huawei-Error: Unrecognized command found at '^' position.]` | ✅ |
| test_deploy | `test_deteccion_de_errores_por_fabricante[Fortinet-Command fail. Return code -61]` | ✅ |
| test_deploy | `test_deteccion_de_errores_por_fabricante[MikroTik-bad command name foo (line 1 column 1)]` | ✅ |
| test_deploy | `test_detenerse_en_error_no_guarda` | ✅ |
| test_deploy | `test_linea_de_configuracion_validada` | ✅ |
| test_deploy | `test_despliegue_ssh_completo` | ✅ |
| test_deploy | `test_despliegue_ssh_se_detiene_ante_error` | ✅ |
| test_generators | `test_un_archivo_por_equipo[Cisco]` | ✅ |
| test_generators | `test_un_archivo_por_equipo[Huawei]` | ✅ |
| test_generators | `test_un_archivo_por_equipo[Fortinet]` | ✅ |
| test_generators | `test_un_archivo_por_equipo[MikroTik]` | ✅ |
| test_generators | `test_ips_del_plan_aparecen_en_las_configs[Cisco]` | ✅ |
| test_generators | `test_ips_del_plan_aparecen_en_las_configs[Huawei]` | ✅ |
| test_generators | `test_ips_del_plan_aparecen_en_las_configs[Fortinet]` | ✅ |
| test_generators | `test_ips_del_plan_aparecen_en_las_configs[MikroTik]` | ✅ |
| test_generators | `test_todos_los_tipos_de_vpn[IPsec-Cisco]` | ✅ |
| test_generators | `test_todos_los_tipos_de_vpn[IPsec-Huawei]` | ✅ |
| test_generators | `test_todos_los_tipos_de_vpn[IPsec-Fortinet]` | ✅ |
| test_generators | `test_todos_los_tipos_de_vpn[IPsec-MikroTik]` | ✅ |
| test_generators | `test_todos_los_tipos_de_vpn[SSL-Cisco]` | ✅ |
| test_generators | `test_todos_los_tipos_de_vpn[SSL-Huawei]` | ✅ |
| test_generators | `test_todos_los_tipos_de_vpn[SSL-Fortinet]` | ✅ |
| test_generators | `test_todos_los_tipos_de_vpn[SSL-MikroTik]` | ✅ |
| test_generators | `test_todos_los_tipos_de_vpn[MPLS-Cisco]` | ✅ |
| test_generators | `test_todos_los_tipos_de_vpn[MPLS-Huawei]` | ✅ |
| test_generators | `test_todos_los_tipos_de_vpn[MPLS-Fortinet]` | ✅ |
| test_generators | `test_todos_los_tipos_de_vpn[MPLS-MikroTik]` | ✅ |
| test_generators | `test_todos_los_tipos_de_vpn[Ninguna-Cisco]` | ✅ |
| test_generators | `test_todos_los_tipos_de_vpn[Ninguna-Huawei]` | ✅ |
| test_generators | `test_todos_los_tipos_de_vpn[Ninguna-Fortinet]` | ✅ |
| test_generators | `test_todos_los_tipos_de_vpn[Ninguna-MikroTik]` | ✅ |
| test_generators | `test_sin_secretos_reales_solo_marcadores[Cisco]` | ✅ |
| test_generators | `test_sin_secretos_reales_solo_marcadores[Huawei]` | ✅ |
| test_generators | `test_sin_secretos_reales_solo_marcadores[Fortinet]` | ✅ |
| test_generators | `test_sin_secretos_reales_solo_marcadores[MikroTik]` | ✅ |
| test_generators | `test_parametros_remotos_reemplazan_marcadores` | ✅ |
| test_generators | `test_cisco_acceso_endurecido` | ✅ |
| test_generators | `test_huawei_usa_sintaxis_vrp` | ✅ |
| test_generators | `test_fortinet_politicas_explicitas` | ✅ |
| test_generators | `test_mikrotik_vlan_filtering_al_final` | ✅ |
| test_generators | `test_plan_de_puertos_no_excede_48` | ✅ |
| test_generators | `test_zip_contiene_todos_los_archivos` | ✅ |
| test_generators | `test_fabricante_invalido` | ✅ |
| test_ipam | `test_prefijo_minimo_para_hosts[1-29]` | ✅ |
| test_ipam | `test_prefijo_minimo_para_hosts[6-29]` | ✅ |
| test_ipam | `test_prefijo_minimo_para_hosts[7-28]` | ✅ |
| test_ipam | `test_prefijo_minimo_para_hosts[14-28]` | ✅ |
| test_ipam | `test_prefijo_minimo_para_hosts[30-27]` | ✅ |
| test_ipam | `test_prefijo_minimo_para_hosts[50-26]` | ✅ |
| test_ipam | `test_prefijo_minimo_para_hosts[62-26]` | ✅ |
| test_ipam | `test_prefijo_minimo_para_hosts[63-25]` | ✅ |
| test_ipam | `test_prefijo_minimo_para_hosts[126-25]` | ✅ |
| test_ipam | `test_prefijo_minimo_para_hosts[254-24]` | ✅ |
| test_ipam | `test_prefijo_minimo_para_hosts[510-23]` | ✅ |
| test_ipam | `test_prefijo_minimo_para_hosts[750-22]` | ✅ |
| test_ipam | `test_crecimiento_redondea_hacia_arriba` | ✅ |
| test_ipam | `test_escenario_15_pisos_genera_un_26_por_piso` | ✅ |
| test_ipam | `test_calculo_manual_de_un_26` | ✅ |
| test_ipam | `test_ninguna_subred_se_solapa` | ✅ |
| test_ipam | `test_todas_las_subredes_caben_en_la_base` | ✅ |
| test_ipam | `test_vlsm_alineado_a_frontera` | ✅ |
| test_ipam | `test_cada_segmento_aloja_sus_hosts` | ✅ |
| test_ipam | `test_enlaces_wan_son_30_estrictos` | ✅ |
| test_ipam | `test_enlaces_wan_contiguos_sin_desperdicio` | ✅ |
| test_ipam | `test_ipv6_un_64_unico_por_vlan` | ✅ |
| test_ipam | `test_ipv6_p2p_127` | ✅ |
| test_ipam | `test_ipv6_bloque_56_usa_vlan_decimal` | ✅ |
| test_ipam | `test_ruta_sumarizada_cubre_todo` | ✅ |
| test_ipam | `test_base_insuficiente_falla_con_mensaje_claro` | ✅ |
| test_ipam | `test_bloque_wan_no_puede_solapar_lan` | ✅ |
| test_ipam | `test_escalabilidad_multiples_escenarios[1-10]` | ✅ |
| test_ipam | `test_escalabilidad_multiples_escenarios[3-120]` | ✅ |
| test_ipam | `test_escalabilidad_multiples_escenarios[8-1600]` | ✅ |
| test_ipam | `test_escalabilidad_multiples_escenarios[40-4000]` | ✅ |
| test_ipam | `test_servicios_opcionales_se_omiten` | ✅ |
| test_ipam | `test_p2p_link_propiedades` | ✅ |
| test_netdevops | `test_ssh_rechaza_host_desconocido_por_defecto` | ✅ |
| test_netdevops | `test_ssh_lote_en_modo_laboratorio_y_redacta_secretos` | ✅ |
| test_netdevops | `test_ssh_contrasena_incorrecta` | ✅ |
| test_netdevops | `test_ssh_puerto_cerrado` | ✅ |
| test_netdevops | `test_ssh_parametros_invalidos` | ✅ |
| test_netdevops | `test_telnet_bloquea_destinos_publicos` | ✅ |
| test_netdevops | `test_telnet_deshabilitado_por_defecto` | ✅ |
| test_netdevops | `test_telnet_negocia_iac_y_ejecuta` | ✅ |
| test_netdevops | `test_simulador_interfaces_desde_el_plan[Cisco-show ip interface brief]` | ✅ |
| test_netdevops | `test_simulador_interfaces_desde_el_plan[Huawei-display ip interface brief]` | ✅ |
| test_netdevops | `test_simulador_interfaces_desde_el_plan[Fortinet-get system interface]` | ✅ |
| test_netdevops | `test_simulador_interfaces_desde_el_plan[MikroTik-/ip address print]` | ✅ |
| test_netdevops | `test_simulador_rutas_ospf_y_ping` | ✅ |
| test_netdevops | `test_simulador_vlans_de_acceso` | ✅ |
| test_netdevops | `test_simulador_redacta_running_config` | ✅ |
| test_netdevops | `test_simulador_valida_comandos` | ✅ |
| test_security | `test_gitignore_excluye_env_y_salidas` | ✅ |
| test_security | `test_env_example_sin_valores_secretos` | ✅ |
| test_security | `test_no_hay_secretos_hardcodeados_en_el_codigo` | ✅ |
| test_security | `test_escaner_detecta_un_secreto_plantado` | ✅ |
| test_security | `test_redaccion_multi_fabricante` | ✅ |
| test_security | `test_redaccion_de_contrasena_conocida_en_salida` | ✅ |
| test_security | `test_password_no_aparece_en_repr` | ✅ |
| test_security | `test_reporte_de_confianza_formula` | ✅ |
| test_serial | `test_equipo_de_fabrica_supera_dialogo_y_entra_a_enable` | ✅ |
| test_serial | `test_despliegue_por_consola_configura_nombre_e_ip` | ✅ |
| test_serial | `test_login_de_consola_con_usuario` | ✅ |
| test_serial | `test_login_de_consola_pide_usuario_si_falta` | ✅ |
| test_serial | `test_puerto_inexistente_mensaje_claro` | ✅ |
| test_serial | `test_puertos_validos[COM1]` | ✅ |
| test_serial | `test_puertos_validos[COM12]` | ✅ |
| test_serial | `test_puertos_validos[/dev/ttyUSB0]` | ✅ |
| test_serial | `test_puertos_validos[/dev/tty.usbserial-1410]` | ✅ |
| test_serial | `test_puertos_invalidos[COM1; del *]` | ✅ |
| test_serial | `test_puertos_invalidos[http://x]` | ✅ |
| test_serial | `test_puertos_invalidos[socket://8.8.8.8:23]` | ✅ |
| test_serial | `test_puertos_invalidos[]` | ✅ |
| test_serial | `test_puertos_invalidos[LPT1]` | ✅ |
| test_serial | `test_velocidad_invalida` | ✅ |
| test_serial | `test_listado_de_puertos_no_falla` | ✅ |
| test_topology | `test_jerarquia_completa` | ✅ |
| test_topology | `test_cada_piso_tiene_acceso` | ✅ |
| test_topology | `test_ips_de_gestion_unicas_y_en_vlan_99` | ✅ |
| test_topology | `test_etiquetas_de_enlaces_salen_del_plan` | ✅ |
| test_topology | `test_dot_y_mermaid_validos` | ✅ |
| test_topology | `test_switches_extra_si_el_piso_supera_48_puertos` | ✅ |
| test_topology | `test_ssl_vpn_dibuja_usuarios_remotos` | ✅ |
| test_validators | `test_comandos_legitimos_aceptados[show ip int brief]` | ✅ |
| test_validators | `test_comandos_legitimos_aceptados[show run | include hostname]` | ✅ |
| test_validators | `test_comandos_legitimos_aceptados[display current-configuration | include sysname]` | ✅ |
| test_validators | `test_comandos_legitimos_aceptados[/ip address print]` | ✅ |
| test_validators | `test_comandos_legitimos_aceptados[get system status]` | ✅ |
| test_validators | `test_comandos_legitimos_aceptados[ping 10.20.7.1]` | ✅ |
| test_validators | `test_inyecciones_bloqueadas[show ver ; reload]` | ✅ |
| test_validators | `test_inyecciones_bloqueadas[show ver && reload]` | ✅ |
| test_validators | `test_inyecciones_bloqueadas[show `id`]` | ✅ |
| test_validators | `test_inyecciones_bloqueadas[show $(whoami)]` | ✅ |
| test_validators | `test_inyecciones_bloqueadas[show run > /tmp/x]` | ✅ |
| test_validators | `test_inyecciones_bloqueadas[show ver\nreload]` | ✅ |
| test_validators | `test_inyecciones_bloqueadas[show ver\rreload]` | ✅ |
| test_validators | `test_inyecciones_bloqueadas[show\x00ver]` | ✅ |
| test_validators | `test_inyecciones_bloqueadas[aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa]` | ✅ |
| test_validators | `test_inyecciones_bloqueadas[]` | ✅ |
| test_validators | `test_inyecciones_bloqueadas[   ]` | ✅ |
| test_validators | `test_destructivos_detectados[reload]` | ✅ |
| test_validators | `test_destructivos_detectados[write erase]` | ✅ |
| test_validators | `test_destructivos_detectados[erase startup-config]` | ✅ |
| test_validators | `test_destructivos_detectados[reset saved-configuration]` | ✅ |
| test_validators | `test_destructivos_detectados[execute factoryreset]` | ✅ |
| test_validators | `test_destructivos_detectados[/system reset-configuration]` | ✅ |
| test_validators | `test_destructivos_detectados[delete flash:x]` | ✅ |
| test_validators | `test_lote_rechaza_destructivo_sin_confirmacion` | ✅ |
| test_validators | `test_lote_ignora_comentarios_y_limita_tamano` | ✅ |
| test_validators | `test_lote_fail_closed_indica_linea` | ✅ |
| test_validators | `test_redes_base_validas[10.20.0.0/16]` | ✅ |
| test_validators | `test_redes_base_validas[172.16.0.0/12]` | ✅ |
| test_validators | `test_redes_base_validas[192.168.0.0/22]` | ✅ |
| test_validators | `test_redes_base_validas[100.64.0.0/16]` | ✅ |
| test_validators | `test_redes_base_invalidas[10.20.0.5/16]` | ✅ |
| test_validators | `test_redes_base_invalidas[8.8.8.0/24]` | ✅ |
| test_validators | `test_redes_base_invalidas[10.0.0.0/30]` | ✅ |
| test_validators | `test_redes_base_invalidas[hola]` | ✅ |
| test_validators | `test_redes_base_invalidas[300.1.1.0/24]` | ✅ |
| test_validators | `test_redes_base_invalidas[]` | ✅ |
| test_validators | `test_ipv6_valida_e_invalida` | ✅ |
| test_validators | `test_nombres_y_hostnames` | ✅ |
| test_validators | `test_destinos_ssh` | ✅ |
| test_validators | `test_escape_html_previene_xss` | ✅ |
| test_validators | `test_config_global_reporta_todos_los_errores` | ✅ |

## Metodología

- **Unitarias:** matemática de subredes contrastada con cálculos manuales (red, broadcast, máscara, gateway) y con la regla de 2 IPs útiles en /30.
- **Propiedades:** ninguna subred se solapa, todas caben en la red base, cada VLAN tiene un /64 único.
- **Generadores:** cada fabricante produce un archivo por equipo, sin secretos reales y con las IP del plan.
- **Seguridad:** inyección de comandos, XSS en salida de terminal, enmascarado de contraseñas.
- **Interfaz:** cada módulo se ejecuta con `streamlit.testing.AppTest` sin excepciones.
