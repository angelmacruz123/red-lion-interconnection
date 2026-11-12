# Manual de usuario — RED-LION-INTERCONNECTION

Herramienta de diseño y gestión de redes WAN: subnetting, carga de topología, configuraciones para
Cisco, Huawei, Fortinet y MikroTik, conexión a los equipos y ciberdefensa integrada.

Autor: Angel Mauricio Cruz Gonzalez · Materia: Interconexión de Redes WAN · Docente: Jhon Harold Perez Calderon

---

## 1. Instalación

### Requisitos

| Requisito | Detalle |
|---|---|
| Sistema | Windows 10/11, macOS o Linux |
| Python | 3.11 o superior ([python.org](https://www.python.org/downloads/)); en Windows marque **Add Python to PATH** |
| Navegador | Chrome, Edge o Firefox |
| Opcional | Graphviz (para exportar el diagrama a SVG) y cable de consola USB/serial para configurar equipos |

### Opción A — Windows con doble clic

1. En GitHub: botón verde **Code → Download ZIP** y descomprímalo.
2. Abra la carpeta y haga doble clic en **`INICIAR.bat`**.
3. La primera vez instala las dependencias (1 a 3 minutos). Luego se abre el navegador en `http://localhost:8501`.
4. Para cerrar la aplicación, cierre la ventana negra.

Si Windows muestra «Windows protegió su PC»: **Más información → Ejecutar de todas formas** (el `.bat` solo crea el entorno e inicia la app; puede abrirlo con el Bloc de notas para revisarlo).

### Opción B — Línea de comandos

```bash
git clone https://github.com/angelmacruz123/redes-wan-cruz.git
cd redes-wan-cruz
python -m venv .venv
.venv\Scripts\activate            # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
copy .env.example .env            # macOS/Linux: cp .env.example .env
streamlit run app.py
```

### Configurar el archivo `.env` (solo si va a conectarse a equipos)

El `.env` guarda las credenciales en su PC y **nunca se sube a GitHub**.

| Variable | Para qué |
|---|---|
| `NET_USERNAME`, `NET_PASSWORD` | Usuario y contraseña para entrar a los equipos |
| `ENABLE_SECRET` | Contraseña de `enable` en Cisco |
| `ADMIN_SECRET` | Contraseña del usuario local que crea el hardening |
| `VPN_PSK`, `SNMPV3_AUTH`, `SNMPV3_PRIV` | Secretos de VPN y SNMPv3 |
| `ALLOW_UNKNOWN_HOSTS` | `true` solo en laboratorio, para aceptar equipos nuevos por SSH |
| `ENABLE_TELNET_LAB` | `true` para permitir Telnet hacia IP privadas de laboratorio |

---

## 2. Recorrido rápido (5 minutos)

1. **Módulo 1:** elija la plantilla «Edificio corporativo (15 pisos)» y pulse **Aplicar plantilla**.
2. **Módulo 2:** revise las subredes; en **Calculadora** escriba `192.168.10.0/26`.
3. **Módulo 3:** en **Cargar / editar topología** cambie un hostname y pulse **Aplicar topología**.
4. **Módulo 4:** elija **Cisco** y luego **Huawei**; descargue los `.txt`.
5. **Módulo 5:** en **Simulación** pulse **Desplegar**.
6. **Módulo 6:** pulse **Ejecutar batería de pruebas** y vea el % de confianza.

---

## 3. Uso por módulo

### Módulo 1 — Requerimientos

1. Elija una **plantilla de escenario** o complete los campos: nombre del proyecto, pisos o zonas, hosts, crecimiento (%), presupuesto, ancho de banda del ISP, cámaras y AP por piso, tipo de VPN y servicios.
2. Escriba las redes base: **IPv4 privada** (ej. `10.20.0.0/16`), **IPv6** (ej. `2001:db8:acad::/48`), el **bloque WAN** para los /30 y el **enlace del ISP** (/30 que entrega el proveedor).
3. Pulse **Guardar y recalcular**. Si algo no cuadra (por ejemplo, la red base no alcanza), la app explica el error y no cambia el diseño.
4. Revise **Viabilidad del diseño**: costo frente al presupuesto y demanda pico frente al enlace ISP.

Todo lo que defina aquí se propaga solo a los demás módulos.

### Módulo 2 — Planificación IP (subnetting)

- **Subredes LAN / VLAN:** una fila por VLAN con red, prefijo, máscara, gateway, rango útil, broadcast, hosts utilizables, % de uso y su /64 IPv6. Botones para descargar CSV o Markdown.
- **Enlaces WAN punto a punto:** cada enlace /30 con sus 2 IP útiles y su /127 IPv6.
- **Calculadora:** escriba una IP con prefijo (ej. `192.168.10.77/26`) y obtenga red, máscara, wildcard, primera y última IP útil, broadcast, número de hosts y si es pública o privada.

**Ejemplo resuelto — `192.168.10.0/26`:** 26 bits de red y 6 de host → bloque de 2⁶ = 64. Red `192.168.10.0`, máscara `255.255.255.192`, broadcast `192.168.10.63`, hosts útiles `.1` a `.62` = 62.

### Módulo 3 — Carga de la topología

La app propone una topología jerárquica a partir del plan. Usted puede **editarla o cargar la suya**:

1. Abra la pestaña **Cargar / editar topología**.
2. En **Dispositivos** edite `hostname`, `rol`, `piso` (solo switches de acceso) e `ip_gestion` (dentro de la VLAN 99). Puede agregar filas (ej. un router de otra sede, rol `router`) o quitarlas.
3. En **Enlaces** indique `origen`, `destino` y `tipo` (`p2p`, `trunk`, `vpn`, `wan`). Un enlace `wan` entre routers recibe automáticamente un /30 libre.
4. Pulse **Aplicar topología**. Si hay errores, se listan todos juntos (hostname inválido, IP fuera de rango, enlace a un equipo que no existe…).
5. **Importar:** en «Importar desde archivo» suba un `.json` completo o dos `.csv` (dispositivos y enlaces). Use **Exportar .json** para obtener una plantilla.
6. **Restablecer la propuesta** vuelve a la topología generada.

Ejemplo de archivo JSON:

```json
{"dispositivos": [{"id": "R-SEDE2", "hostname": "MED-R-01", "rol": "router", "piso": "", "ip_gestion": "10.20.6.200"}],
 "enlaces": [{"origen": "R-SEDE2", "destino": "R-CORE", "tipo": "wan"}]}
```

(El archivo debe incluir también los dispositivos y enlaces base; parta de **Exportar .json**.)

Las pestañas **Diagrama**, **Diagrama interactivo** e **Inventario** muestran la topología cargada.

### Módulo 4 — Configuraciones (Cisco, Huawei, Fortinet, MikroTik)

1. Elija el **fabricante**.
2. Si usa VPN IPsec, complete la **IP pública del peer** y la **LAN remota**.
3. En **Equipo** elija un dispositivo: verá su **hostname, VLAN e IP**, el resultado de la **auditoría de seguridad** y la configuración completa.
4. **Descargar** un archivo o **todos en .zip**.

Las contraseñas aparecen como marcadores `<<…>>`: reemplácelas con las del `.env` o de su gestor de secretos antes de pegar la configuración en un equipo.

### Módulo 5 — Conexión y despliegue

1. **Modo:**
   - *Simulación:* sin equipos; el equipo arranca «de fábrica» y cambia al desplegarle.
   - *Consola serial (COM):* cable de consola, como PuTTY → Serial (9600 baudios). Cierre PuTTY antes.
   - *SSH:* equipo con IP y SSH habilitado.
   - *Telnet (lab):* emuladores con IP privada (requiere `ENABLE_TELNET_LAB=true`).
2. Elija **fabricante** y **equipo**.
3. Marque qué configurar: nombre, VLAN, IP y puertos (por defecto); opcionalmente enrutamiento, DHCP, hardening y servicios.
4. Revise la **vista previa** (lo que se enviará exactamente) y las advertencias de seguridad.
5. En equipos reales escriba el nombre del equipo para confirmar y pulse **Desplegar**. La app respalda, aplica bloque por bloque, se detiene si el equipo responde con error, guarda y verifica.
6. La pestaña **Terminal de comandos** ejecuta consultas en lote (`show …`, `display …`).

### Módulo 6 — Ciberdefensa y pruebas

- **Controles de seguridad:** `.gitignore` con `.env`, sin secretos en el código, documentos presentes.
- **Auditar configuración:** pegue cualquier configuración y la app advierte Telnet, credenciales por defecto, SNMP `public`, contraseñas en claro, ACL abiertas, etc., con la corrección sugerida.
- **Laboratorio de validación:** pruebe un comando contra el filtro anti-inyección y vea el enmascarado de contraseñas.
- **Ejecutar batería de pruebas:** corre `pytest`, escribe `docs/pruebas.md` y muestra «X de Y = Z% de confianza».

---

## 4. Pruebas desde la terminal

```bash
pytest -q
python scripts/generate_test_report.py
```

## 5. Problemas frecuentes

| Mensaje | Solución |
|---|---|
| `python no se reconoce…` | Reinstale Python marcando **Add Python to PATH** o use `py` |
| `Port 8501 is already in use` | `streamlit run app.py --server.port 8502` |
| «COM1 está ocupado» | Cierre PuTTY u otro programa que use el puerto |
| «No existe COM1» | Busque el número en Administrador de dispositivos → Puertos (COM y LPT) |
| «Host desconocido» (SSH) | `ssh-keyscan -H <IP> >> ~/.ssh/known_hosts`, o `ALLOW_UNKNOWN_HOSTS=true` solo en laboratorio |
| Botón «Imagen (.svg)» deshabilitado | Instale Graphviz; el diagrama en pantalla funciona sin él |
