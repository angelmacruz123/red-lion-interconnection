# Arquitectura de RED-LION-INTERCONNECTION

Documento de diseño (Corte 2). Describe la arquitectura de **software** de la herramienta y la
arquitectura de **red** que modela.

## 1. Objetivo

Automatizar el ciclo diseño → direccionamiento → topología → configuración → verificación de una red
corporativa multi-piso o multi-sede, de forma que un cambio en los requerimientos se propague sin
intervención manual a todos los entregables técnicos.

## 2. Arquitectura de software

```
                ┌─────────────────────────── app.py (Streamlit) ───────────────────────────┐
                │  views/m1 … m6  ──►  ui/components + ui/styles (sistema de diseño)         │
                └───────────────┬───────────────────────────────────────────────────────────┘
                                │ st.session_state["config"]  (única fuente de verdad)
                ┌───────────────▼───────────────┐
                │ core/state.py  ProjectConfig  │──► huella SHA-256 → caché del plan
                └───────┬───────────────────────┘
        ┌───────────────┼─────────────────┬──────────────────────┬────────────────────┐
        ▼               ▼                 ▼                      ▼                    ▼
 core/validators  core/ipam.py     core/topology.py      generators/*.py      netdevops/*.py
 (entrada segura) (VLSM, /30, /64) (grafo jerárquico)    (Cisco/Huawei/       (SSH paramiko,
                                                          Fortinet/MikroTik)   Telnet lab, simulador)
                                                                 │
                                         core/quality.py ◄── tests/ (pytest + AppTest) ──► docs/pruebas.md
```

Principios:

- **Separación núcleo / interfaz.** `core/`, `generators/` y `netdevops/` no importan Streamlit, por eso
  se prueban con pytest sin levantar la UI.
- **Estado único.** `ProjectConfig` vive en `st.session_state`. Su huella (`fingerprint()`) invalida la
  caché: cambiar un parámetro en el Módulo 1 recalcula los Módulos 2–5 automáticamente.
- **Determinismo.** Para una misma configuración, el plan IP y los archivos CLI son idénticos byte a byte
  (salvo la fecha del encabezado), lo que permite versionarlos y compararlos.
- **Extensibilidad.** Un fabricante nuevo es un archivo en `generators/` con `RENDER`, `PLATFORMS` y
  `COMMENT`, registrado en `generators/__init__.py`.

## 3. Arquitectura de red modelada

Modelo jerárquico de tres capas más borde:

| Capa | Equipo | Función |
|---|---|---|
| Borde | R-CORE (router/firewall) | NAT/PAT, ACL anti-spoofing, VPN (IPsec VTI / SSL / CE-PE MPLS), QoS de voz, DMZ |
| Distribución | R-DIST | Enrutamiento OSPF área 0, segmentación (ISFW en el perfil Fortinet) |
| Núcleo | SW-CORE (L3) | SVIs/gateways de todas las VLAN, DHCP, raíz STP, troncales a acceso |
| Acceso | SW-ACC-Pnn | Puertos de usuario con voz, cámaras PoE, AP; port-security, BPDU guard, DHCP snooping |
| Servicios | SW-SRV, DMZ | Granja de servidores interna y zona desmilitarizada colgada del borde |

### 3.1 Numeración de VLAN

| VLAN | Uso | Regla de tamaño |
|---|---|---|
| 100 + n | Datos del piso/zona *n* | ⌈hosts / pisos⌉ × (1 + crecimiento) |
| 20 | Voz IP | hosts × (1 + crecimiento) — un teléfono por puesto |
| 30 | CCTV | cámaras × pisos + 2 NVR |
| 40 | Wi-Fi clientes | 60 % de los hosts (BYOD) |
| 50 | Servidores | /27 |
| 60 | DMZ | /28 en el router de borde |
| 99 | Gestión | 1 IP por equipo y AP + 10 de margen |
| 900 | Tránsito L3 (solo FortiSwitch) | /30 |
| 999 | BLACKHOLE (nativa de troncales y puertos sin uso) | — |

### 3.2 Reglas de direccionamiento

1. **VLSM descendente**: los bloques se asignan de mayor a menor y alineados a su frontera natural, lo que
   elimina huecos y permite una ruta sumarizada única (`core/ipam.py::vlsm_allocate`).
2. **Gateway = primera IP útil**; las primeras IP (≈ 1/6 del segmento, máx. 10) se reservan para estáticos
   y el resto es pool DHCP.
3. **Enlaces punto a punto /30** tomados en orden de un bloque dedicado (`172.31.255.0/24` por defecto):
   lado A = 1.ª útil, lado B = 2.ª útil, igual que en Packet Tracer.
4. **IPv6**: un /64 por VLAN con el número de VLAN como identificador de subred legible
   (`2001:db8:acad:101::/64`); enlaces P2P en /127 (RFC 6164) desde los últimos /64 del bloque.

### 3.3 Enrutamiento

- OSPFv2 y OSPFv3 en área 0 entre R-CORE, R-DIST y SW-CORE; SVIs como interfaces pasivas.
- R-CORE inyecta la ruta por defecto (`default-information originate`) y hace PAT hacia el ISP.
- MPLS: eBGP CE (AS 65010) ↔ PE (AS 65000) anunciando la ruta sumarizada.

## 4. Despliegue guiado a los equipos

`netdevops/deploy.py` no escribe comandos propios: toma la configuración generada en el Módulo 4,
la parte en bloques de primer nivel y clasifica cada bloque en `hostname`, `vlans`, `ip`, `ports`,
`routing`, `dhcp`, `seguridad` o `servicios`.

1. **Dependencias.** En switches, IP y puertos arrastran las VLAN; enrutamiento, DHCP y servicios arrastran IP.
2. **Subcomandos dependientes.** Si no se despliegan servicios, se quitan de las interfaces `ip nat`,
   `ip access-group`, `service-policy`, etc.; si no se despliega enrutamiento, las líneas `ip ospf`.
3. **Marcadores.** Un bloque con un marcador sin valor (IP del peer, secreto ausente) se omite completo.
   Los secretos se inyectan desde el `.env` solo al enviar; la vista previa nunca los muestra.
4. **Ejecución.** Respaldo → modo configuración → bloque a bloque con detección de errores por fabricante
   (fail-fast, sin guardar) → `write memory`/`save` → comandos de verificación.

## 5. Decisiones técnicas relevantes

| Decisión | Alternativa descartada | Motivo |
|---|---|---|
| `ipaddress` de la librería estándar | Cálculo manual con bits | Exactitud y validación incluidas, sin dependencias |
| Graphviz (`st.graphviz_chart`) + Mermaid | Imagen estática | Diagrama generado del modelo, exportable a .dot/.mmd/.svg |
| `invoke_shell` en paramiko | `exec_command` | Los NOS de red no soportan bien el canal exec |
| RejectPolicy de host key | AutoAddPolicy | Evita ataques MITM; modo laboratorio solo con bandera explícita |
| Marcadores `<<SECRETO>>` en las plantillas | Contraseñas en los .txt | Ningún secreto sale de la herramienta ni llega a git |
| Telnet propio sobre socket | `telnetlib` | `telnetlib` fue eliminado en Python 3.13 |

## 6. Limitaciones conocidas

- Los precios del BOM son referenciales y deben reemplazarse por cotizaciones.
- Un único router de borde y un único núcleo: no se modela redundancia (HSRP/VRRP, doble ISP).
  Es la extensión natural para una siguiente versión.
- El simulador refleja las categorías desplegadas (nombre, VLAN, IP, puertos, OSPF), pero no interpreta
  cada comando: valida y registra lo enviado.
- El despliegue es equipo por equipo; desplegar todo el edificio en lote es la siguiente extensión.
