# RED-LION-INTERCONNECTION

Herramienta web en **Python + Streamlit** para diseñar, direccionar, documentar, configurar y verificar
la infraestructura de red de un edificio corporativo, campus o conjunto de sedes. Un cambio en los
requerimientos se propaga automáticamente al plan IP, la topología, las configuraciones CLI de cuatro
fabricantes y la consola de automatización.

| Módulo | Qué hace |
|---|---|
| 1 · Requerimientos | Escenario, pisos/zonas, hosts, presupuesto, ancho de banda, servicios, VPN, redes base. BOM y viabilidad. |
| 2 · Planificación IP | VLSM IPv4 con `ipaddress`, gateways, broadcast, máscaras, /64 IPv6 por VLAN, enlaces WAN /30 y /127. |
| 3 · Topología | Diagrama jerárquico Graphviz y Mermaid generado desde el plan. Exporta .dot, .mmd, .svg. |
| 4 · Configuraciones | Cisco IOS-XE, Huawei VRP, Fortinet FortiOS/FortiSwitchOS y MikroTik RouterOS v7. Un .txt por equipo o .zip. |
| 5 · Conexión y despliegue | Se conecta por SSH (paramiko) o Telnet de laboratorio y **aplica en el equipo** nombre, VLAN, IP, puertos (y opcionalmente OSPF, DHCP, hardening, servicios) desde el plan; respaldo, fail-fast y verificación. Incluye terminal y simulador. |
| 6 · Ciberdefensa y pruebas | Controles anti-fuga, laboratorio anti-inyección y cálculo del % de confianza → `docs/pruebas.md`. |

## Instalación

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env               # Windows: copy .env.example .env
streamlit run app.py               # Windows: doble clic en INICIAR.bat
```

Requisitos: Python 3.11+ (probado en 3.13). Opcional: binario **Graphviz** (`dot`) para exportar SVG
(`sudo apt install graphviz` / `brew install graphviz` / instalador de graphviz.org).

## Estructura del proyecto

```
enterprise-wan-architect/
├── app.py                      # Punto de entrada Streamlit y navegación
├── requirements.txt
├── .env.example                # Plantilla de variables (sin secretos)  → copiar a .env
├── .gitignore                  # Excluye .env, configs_out/, llaves
├── .streamlit/config.toml      # Tema oscuro, XSRF, sin trazas al usuario
│
├── core/                       # Lógica pura (no importa Streamlit → testeable)
│   ├── state.py                # ProjectConfig + st.session_state (estado global)
│   ├── validators.py           # Validación estricta, anti-inyección, redacción de secretos
│   ├── ipam.py                 # VLSM, /30, IPv6 /64 y /127
│   ├── topology.py             # Grafo jerárquico → DOT / Mermaid
│   ├── capacity.py             # BOM referencial y demanda de ancho de banda
│   └── quality.py              # Auditoría de seguridad + % de confianza
│
├── generators/                 # Módulo 4: un motor por fabricante
│   ├── common.py               # Contexto, plan de puertos, encabezados, marcadores de secretos
│   ├── cisco.py  huawei.py  fortinet.py  mikrotik.py
│   └── __init__.py             # Registro, render_all(), bundle_zip()
│
├── netdevops/                  # Módulo 5
│   ├── ssh_client.py           # paramiko con RejectPolicy, lotes, manejo de excepciones
│   ├── telnet_client.py        # Telnet solo laboratorio (IP privadas)
│   ├── serial_client.py        # Cable de consola (COM, 9600 8N1) para equipos de fábrica
│   ├── deploy.py               # Despliegue guiado: bloques por categoría, respaldo, aplicar, verificar
│   └── simulator.py            # Respuestas derivadas del diseño
│
├── ui/                         # Sistema de diseño (CSS) y componentes HTML seguros
├── views/                      # m1_requirements.py … m6_security.py
├── scripts/
│   ├── generate_test_report.py # Escribe docs/pruebas.md (usar --min 90 en CI)
│   └── export_configs.py       # Exporta configuraciones por consola a configs_out/
├── tests/                      # pytest + streamlit.testing.AppTest
└── docs/
    ├── arquitectura.md         # Corte 2
    ├── plan-direccionamiento.md# Corte 2
    ├── entregables-cortes.md   # Mapa criterio → archivo
    ├── seguridad.md            # Corte 3
    ├── pruebas.md              # Corte 3 (generado)
    └── politicas-ia.md         # Corte 3 (completar declaración)
```

## Uso por módulo

1. **Requerimientos.** Elija una plantilla o defina los parámetros y pulse *Guardar y recalcular*. Si la red
   base no alcanza, el formulario lo rechaza con un mensaje explicativo y no cambia el diseño vigente.
2. **Planificación IP.** Revise las tablas, descargue CSV/Markdown para el informe y use la calculadora para
   comprobar a mano cualquier subred.
3. **Topología.** Vista Graphviz (sin conexión a Internet) o Mermaid interactiva (Ctrl/⌘ + rueda para zoom).
4. **Configuraciones.** Escoja el fabricante, complete la IP pública del peer y la LAN remota si usa IPsec, y
   descargue un archivo o el .zip. Reemplace los marcadores `<<…>>` desde su gestor de secretos.
5. **Conexión y despliegue.** Modos: *Simulación*, *Consola serial (COM)* —cable de consola, como
   PuTTY → Serial, ideal para equipos recién sacados de la caja—, *SSH* y *Telnet (lab)*.
   Pestaña *Despliegue guiado*: elija modo, equipo y qué configurar
   (por defecto nombre, VLAN, IP y puertos), revise la vista previa y pulse *Desplegar*. En SSH/Telnet
   debe escribir el nombre del equipo para confirmar. La app respalda la configuración actual en
   `configs_out/backups/`, aplica bloque por bloque, se detiene si el equipo responde con error (sin
   guardar) y al final guarda y verifica. Hardening solo se habilita si `ADMIN_SECRET` (y en Cisco
   `ENABLE_SECRET`) están en el `.env`. Pestaña *Terminal*: comandos de consulta en lote.
   *Simulación* funciona sin equipos: cada equipo arranca de fábrica y cambia al desplegarle. Para *SSH*, agregue la clave del equipo a
   `~/.ssh/known_hosts` (`ssh-keyscan -H 10.20.6.130 >> ~/.ssh/known_hosts`) o, solo en laboratorio,
   `ALLOW_UNKNOWN_HOSTS=true`. *Telnet* exige `ENABLE_TELNET_LAB=true` y una IP privada.
6. **Ciberdefensa y pruebas.** Ejecute la batería: corre pytest, audita el repositorio y escribe
   `docs/pruebas.md` con el porcentaje de confianza.

## Pruebas

```bash
pytest -q                                   # toda la batería
python scripts/generate_test_report.py      # regenera docs/pruebas.md
python scripts/generate_test_report.py --min 90   # falla si la confianza < 90 %
```

## Seguridad en una línea

Las credenciales viven solo en `.env` (fuera de git) o en un gestor de secretos; las configuraciones
generadas usan marcadores; toda salida se escapa y se enmascara. Detalle en `docs/seguridad.md`.
