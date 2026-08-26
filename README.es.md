# Firewall Network Automation

[English](README.md) | **Español**

Prueba de concepto de NetDevOps para automatización de firewalls, usando **NetBox como fuente de verdad** y **Ansible como motor de ejecución**.

Actualmente el repositorio automatiza **backups de configuración de Fortinet FortiGate** a través de la API REST de FortiOS. Está diseñado para crecer hacia un proyecto multi-vendor que también incluya **Palo Alto Networks (PAN-OS)** y **Check Point (Gaia / Management API)**.

## Soporte por vendor

| Vendor | Plataforma | Estado | Automatización |
| --- | --- | --- | --- |
| Fortinet | FortiOS | Disponible | Backup completo de configuración vía `fortinet.fortios.fortios_monitor` |
| Palo Alto Networks | PAN-OS | Planificado | Backup de configuración y tareas operativas vía `paloaltonetworks.panos` |
| Check Point | Gaia / Management API | Planificado | Backup de configuración y tareas de políticas vía `check_point.mgmt` |

## Cómo funciona

1. **Bootstrap de NetBox** — los scripts Python de `scripts/netbox/` crean el inventario del laboratorio en NetBox mediante su API REST: la plataforma `FortiOS`, el fabricante `Fortinet`, el rol de dispositivo `firewall`, el site del laboratorio, el device type `FortiGate VM` y los firewalls del lab con sus interfaces y direcciones IP.
2. **Inventario dinámico** — Ansible construye su inventario desde NetBox con el plugin `netbox.netbox.nb_inventory` (`inventories/netbox/netbox_inventory.yml`). Los dispositivos se agrupan por site, rol y plataforma, y solo se incluyen dispositivos activos, con IP primaria y plataforma `fortios`.
3. **Ejecución del backup** — `playbooks/01_fortigate_backup.yml` ejecuta el rol `fortigate_backup` contra el grupo `platform_fortios`, un firewall a la vez (`serial: 1`). El rol valida el token REST, descarga la configuración completa (`backup.system.config`) y la guarda localmente en `artifacts/backups/` con timestamp UTC.

Los backups se escriben en el nodo de control de Ansible con permisos restrictivos (directorio `0700`, archivos `0600`), y las tareas que manejan tokens usan `no_log: true`.

## Estructura del repositorio

```
ansible.cfg                          # Configuración de Ansible: inventario NetBox, rutas de roles y colecciones
collections/requirements.yml         # Colecciones de Ansible requeridas (netbox.netbox, fortinet.fortios)
requirements.txt                     # Dependencias de Python
.env.example                         # Plantilla para NETBOX_API y NETBOX_TOKEN
inventories/netbox/
  netbox_inventory.yml               # Configuración del plugin de inventario dinámico de NetBox
  group_vars/all.yml                 # Conexión httpapi de FortiOS por defecto (https/443)
playbooks/
  01_fortigate_backup.yml            # Playbook de backup de FortiGate (sobreescribe la conexión a http/80)
roles/fortigate_backup/
  defaults/main.yml                  # Scope del backup, ruta destino y nombre de archivo con timestamp
  tasks/main.yml                     # Validación del token, descarga de la configuración y guardado local
  templates/backup_report.j2         # Placeholder para un futuro reporte de backups
scripts/netbox/
  bootstrap_fortios_platform.py      # Asegura que la plataforma FortiOS exista en NetBox
  bootstrap_firewall_lab.py          # Carga el laboratorio FortiGate en NetBox (idempotente)
  get_fortigates.py                  # Placeholder para una futura utilidad de consulta
artifacts/backups/                   # Directorio de salida de los backups (gitignored)
```

## Requisitos

- Python 3 con los paquetes de `requirements.txt`.
- Ansible core con las colecciones de `collections/requirements.yml`.
- Una instancia de NetBox alcanzable y un token de API con permisos de escritura para los scripts de bootstrap.
- Tokens de la API REST de FortiGate, uno por firewall.
- Opcional: AWX, usando este repositorio como fuente del proyecto.

## Inicio rápido

```bash
# Crear y activar un entorno virtual
python3 -m venv .venv && source .venv/bin/activate

# Instalar dependencias de Python y Ansible
pip install -r requirements.txt
ansible-galaxy collection install -r collections/requirements.yml

# Configurar credenciales de NetBox
cp .env.example .env   # luego editar los valores
set -a; source .env; set +a

# Bootstrap de NetBox (la plataforma debe existir antes del laboratorio)
python scripts/netbox/bootstrap_fortios_platform.py
python scripts/netbox/bootstrap_firewall_lab.py

# Verificar el inventario dinámico
ansible-inventory --graph

# Ejecutar el backup de FortiGate
ansible-playbook playbooks/01_fortigate_backup.yml \
  -e '{"fortios_access_tokens": {"FortiGate_A": "<token>", "FortiGate_B": "<token>"}}'
```

Los backups se guardan como `artifacts/backups/<hostname>_<timestamp UTC>.conf`.

## Configuración y secretos

- `NETBOX_API` / `NETBOX_TOKEN`: requeridas por los scripts de NetBox y por el inventario dinámico.
- `fortios_access_tokens`: diccionario que mapea `hostname -> token REST`. **No** se almacena en el repositorio; se inyecta con `--extra-vars`, Ansible Vault o credenciales de AWX. El rol falla de inmediato si falta un token.
- `fortios_backup_scope`, `fortios_backup_root` y `fortios_backup_filename`: defaults del rol que controlan el scope del backup, el destino y el nombrado de archivos.
- Los `.env` reales, archivos vault, claves y backups generados están excluidos en `.gitignore`. El pipeline de GitLab ejecuta Secret Detection.
- Discrepancia conocida: `inventories/netbox/group_vars/all.yml` define `https/443`, mientras que `playbooks/01_fortigate_backup.yml` sobreescribe la conexión a `http/80` sin validación de certificados. Elegir la configuración de conexión de forma explícita al crear playbooks nuevos.

## Verificación

Todavía no hay pipeline de tests ni lint. Validar los cambios manualmente con:

```bash
ansible-playbook --syntax-check playbooks/01_fortigate_backup.yml
ansible-inventory --graph
python -m py_compile scripts/netbox/*.py
```

## Roadmap

- Implementar los placeholders pendientes: `scripts/netbox/get_fortigates.py` y `roles/fortigate_backup/templates/backup_report.j2`.
- Agregar lint de Ansible y chequeos de sintaxis de playbooks al CI.
- Agregar soporte para **Palo Alto Networks PAN-OS**: bootstrap de la plataforma en NetBox, filtros de inventario y un rol de backup basado en `paloaltonetworks.panos`.
- Agregar soporte para **Check Point**: bootstrap de la plataforma en NetBox, filtros de inventario y un rol de backup basado en `check_point.mgmt`.
- Definir un contrato de backup común (variables de entrada, estructura de salida y reportes) para que todos los vendors produzcan artefactos consistentes.

## Contribuciones

Los cambios se integran mediante merge requests a `main` desde ramas `feature/...`. Los mensajes de commit siguen Conventional Commits en inglés (`feat:`, `fix:`, ...). El contenido del proyecto (nombres de plays y tasks, mensajes, docstrings) está en español; este README es la excepción bilingüe.
