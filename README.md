# Herramienta de Redes WAN — Angel Mauricio Cruz Gonzalez (trabajo individual)

**RED-LION-INTERCONNECTION**

Materia: Interconexión de Redes WAN · Docente: Jhon Harold Perez Calderon · Fundación Universitaria Compensar

Repositorio (público): https://github.com/angelmacruz123/redes-wan-cruz

## Qué hace esta herramienta

Es una aplicación web en Python y Streamlit para diseñar y gestionar una red WAN corporativa (por ejemplo, un edificio
de 15 pisos o varias sedes). A partir de los requerimientos calcula el subnetting, propone o carga la topología, genera
las configuraciones para Cisco, Huawei, Fortinet y MikroTik y se conecta a los equipos para aplicarlas, con
ciberdefensa integrada en cada paso.

## Funciones

- **Subnetting / IP Planning** (IPv4/IPv6, público/privado): VLSM por piso, enlaces WAN /30, /64 y /127 IPv6, calculadora de subredes.
- **Carga de la topología** (dispositivos, enlaces, ISP): tablas editables e importación/exportación JSON y CSV, con validación.
- **Generación de configuraciones:** Cisco (IOS), Huawei (VRP), Fortinet (FortiOS) y MikroTik (RouterOS), un archivo por equipo.
- **Ciberdefensa contra IA** (aplica [docs/politicas-ia.md](docs/politicas-ia.md)): sin secretos en el código, validación de entradas, advertencia de configuraciones inseguras.
- **Conexión a los equipos:** consola serial (COM), SSH, Telnet de laboratorio y simulación, con respaldo y verificación.

## Cómo ejecutarla

1. Instale Python 3.11 o superior (en Windows marque «Add Python to PATH»).
2. Descargue el repositorio (**Code → Download ZIP**) y descomprímalo.
3. En Windows haga doble clic en **`INICIAR.bat`**. En otro sistema:
   ```bash
   python -m venv .venv && source .venv/bin/activate
   pip install -r requirements.txt
   cp .env.example .env
   streamlit run app.py
   ```
4. La app abre en `http://localhost:8501`. El paso a paso completo está en [docs/manual.md](docs/manual.md).

## Pruebas y % de confianza (Corte 3)

- Pruebas superadas: **284 de 284 = 100% de confianza** (ver [docs/pruebas.md](docs/pruebas.md))
- Cómo correrlas: `pytest -q` o, en la app, Módulo 6 → «Ejecutar batería de pruebas».

## Documentos

- [docs/informe-corte2.pdf](docs/informe-corte2.pdf) · [docs/informe-corte3.pdf](docs/informe-corte3.pdf)
- [docs/manual.md](docs/manual.md) · [docs/seguridad.md](docs/seguridad.md) · [docs/politicas-ia.md](docs/politicas-ia.md) · [docs/pruebas.md](docs/pruebas.md)
- Complementarios: [docs/arquitectura.md](docs/arquitectura.md) · [docs/plan-direccionamiento.md](docs/plan-direccionamiento.md) · [docs/informe-tecnico.pdf](docs/informe-tecnico.pdf)

## Capturas (evidencias)

[docs/capturas/](docs/capturas/) (01-subnetting.png … 10-app-final.png)

| # | Archivo | Qué muestra |
|---|---|---|
| 01 | [01-subnetting.png](docs/capturas/01-subnetting.png) | Calculadora: IP, prefijo, red, broadcast y hosts |
| 02 | [02-topologia.png](docs/capturas/02-topologia.png) | Topología cargada: dispositivos y enlaces |
| 03 | [03-config-cisco.png](docs/capturas/03-config-cisco.png) | Configuración Cisco: hostname, VLAN e IP |
| 04 | [04-config-huawei.png](docs/capturas/04-config-huawei.png) | Configuración Huawei: hostname, VLAN e IP |
| 05 | [05-github-commits.png](docs/capturas/05-github-commits.png) | Pestaña Commits del repositorio |
| 06 | [06-config-fortinet.png](docs/capturas/06-config-fortinet.png) | Configuración Fortinet |
| 07 | [07-config-mikrotik.png](docs/capturas/07-config-mikrotik.png) | Configuración MikroTik |
| 08 | [08-ciberdefensa.png](docs/capturas/08-ciberdefensa.png) | Advertencia de configuración insegura |
| 09 | [09-pruebas.png](docs/capturas/09-pruebas.png) | Pruebas con resultado X de Y |
| 10 | [10-app-final.png](docs/capturas/10-app-final.png) | Pantalla principal de la herramienta |

## Autoevaluación (marca Sí/No)

| Criterio | ¿Cumplido? | Evidencia |
|-----------------------------------|------------|----------------------|
| Subnetting funciona | Sí | 01-subnetting.png |
| Carga de topología | Sí | 02-topologia.png |
| Config Cisco y Huawei | Sí | 03 / 04 |
| Config Fortinet y MikroTik (C3) | Sí | 06 / 07 |
| Ciberdefensa (politicas-ia.md) | Sí | 08-ciberdefensa.png |
| Pruebas con % de confianza (C3) | Sí | docs/pruebas.md |

## Ramas y versiones

Cada función nueva se trabajó en su propia rama y se unió a `main` con un merge: `feature/carga-topologia`,
`feature/ciberdefensa-configs` y `docs/entregables-cortes`. El historial está en la pestaña **Commits**.

## Estructura del proyecto

```
app.py                  # Punto de entrada y navegación
core/                   # Lógica: estado, validadores, IPAM, topología, carga de topología, auditoría, calidad
generators/             # Un motor de configuración por marca (cisco, huawei, fortinet, mikrotik)
netdevops/              # Conexión: SSH, consola serial, Telnet de laboratorio, despliegue, simulador
views/  ui/             # Interfaz: un archivo por módulo y el tema oscuro/rojo
tests/                  # Pruebas automáticas (pytest + AppTest)
scripts/                # Reporte de pruebas y exportación de configuraciones
docs/                   # Informes, manual, seguridad, políticas de IA, pruebas y capturas
```

## Seguridad

Las credenciales viven solo en `.env` (excluido por `.gitignore`); las configuraciones generadas usan marcadores
`<<…>>`; toda salida de equipos se escapa y enmascara. Detalle en [docs/seguridad.md](docs/seguridad.md).
