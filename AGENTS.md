# AGENTS.md

Guía para agentes de IA que trabajen en este repositorio.

## Descripción del proyecto

PoC de NetDevOps para automatización de firewalls FortiGate usando **NetBox como fuente de verdad (source of truth)** y **Ansible** como motor de ejecución. El flujo actual implementa:

1. Carga del inventario del laboratorio en NetBox mediante scripts Python (API REST).
2. Inventario dinámico de Ansible generado desde NetBox (plugin `netbox.netbox.nb_inventory`).
3. Backup automático de la configuración de los FortiGate vía API REST de FortiOS (`fortinet.fortios.fortios_monitor`, selector `backup.system.config`), guardado en `artifacts/backups/`.

Repositorio alojado en GitLab (`gitlab.com/andersonmavi30/firewall-network-automation`). Está pensado también para ejecutarse desde AWX (el historial de git menciona el plugin de inventario para AWX).

## Stack tecnológico

- **Ansible** (core) con colecciones: `netbox.netbox` y `fortinet.fortios` (`collections/requirements.yml`).
- **Python 3** con `requests`, `pynetbox` y `pytz` (`requirements.txt`). Los scripts actuales solo usan `requests`; `pynetbox` está declarado pero no se usa aún.
- **NetBox** como inventario externo (variables `NETBOX_API` y `NETBOX_TOKEN`).
- **FortiOS REST API** vía conexión Ansible `httpapi` con token de acceso (`ansible_httpapi_session_key`).
- No hay `pyproject.toml`, `package.json` ni otro manifiesto de build: el proyecto no se compila, se ejecuta directamente.

## Estructura del repositorio

```
README.md / README.es.md             # Documentación principal bilingüe (inglés / español)
ansible.cfg                          # Config Ansible: inventario NetBox, roles_path, collections_path
collections/requirements.yml         # Colecciones Ansible requeridas
requirements.txt                     # Dependencias Python
.env / .env.example                  # NETBOX_API y NETBOX_TOKEN (el .env real está gitignored)
inventories/netbox/
  netbox_inventory.yml               # Plugin nb_inventory: agrupa por site/role/platform,
                                     # filtra devices activos, con primary IP y platform fortios
  group_vars/all.yml                 # Conexión httpapi FortiOS por defecto (https/443)
playbooks/
  01_fortigate_backup.yml            # Playbook de backup; corre sobre el grupo platform_fortios,
                                     # serial: 1, y sobreescribe la conexión a http/80 sin SSL
roles/fortigate_backup/
  defaults/main.yml                  # scope del backup, ruta destino y nombre de archivo con timestamp UTC
  tasks/main.yml                     # Valida token, descarga config con fortios_monitor y la guarda local
  templates/backup_report.j2         # VACÍO (placeholder, aún no implementado)
scripts/netbox/
  bootstrap_fortios_platform.py      # Crea la plataforma "FortiOS" (slug fortios) en NetBox si no existe
  bootstrap_firewall_lab.py          # Carga fabricante, rol, site, device type y los firewalls
                                     # FortiGate_A / FortiGate_B con interfaces e IPs (idempotente)
  get_fortigates.py                  # VACÍO (placeholder, aún no implementado)
artifacts/backups/                   # Destino de los backups (gitignored excepto .gitkeep)
docs/                                # Vacío
```

## Comandos habituales

```bash
# Instalar dependencias (usar un entorno virtual)
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
ansible-galaxy collection install -r collections/requirements.yml

# Cargar credenciales de NetBox
set -a; source .env; set +a   # o: export NETBOX_API=... NETBOX_TOKEN=...

# Bootstrap de NetBox (en este orden: la plataforma debe existir antes del lab)
python scripts/netbox/bootstrap_fortios_platform.py
python scripts/netbox/bootstrap_firewall_lab.py

# Verificar el inventario dinámico
ansible-inventory --graph

# Ejecutar el backup de FortiGate (requiere los tokens REST, ver abajo)
ansible-playbook playbooks/01_fortigate_backup.yml \
  -e '{"fortios_access_tokens": {"FortiGate_A": "<token>", "FortiGate_B": "<token>"}}'
```

## Variables y secretos

- `fortios_access_tokens`: diccionario `{hostname: token_rest}` consumido por el playbook y el rol. **No está definido en el repositorio**: debe inyectarse con `--extra-vars`, Ansible Vault o credenciales de AWX. Sin él, el rol falla en la primera tarea de validación.
- `NETBOX_API` / `NETBOX_TOKEN`: requeridas por todos los scripts de `scripts/netbox/`; salen con error si faltan.
- El `.env` real, archivos `*.vault`, claves y los backups generados están excluidos en `.gitignore`; nunca commitear secretos. El pipeline de GitLab incluye Secret Detection.
- Los backups se escriben con permisos `0600` en un directorio `0700`, y las tareas que manejan tokens usan `no_log: true`. Mantener estas protecciones al modificar el rol.

## Convenciones de código

- **Idioma**: el contenido del proyecto (nombres de plays/tasks, mensajes, docstrings, comentarios de `.gitignore`) está en **español**; mantener ese idioma en el código nuevo. Excepción: la documentación principal es bilingüe — `README.md` en inglés con enlace a `README.es.md` en español; ambos deben mantenerse sincronizados. Los mensajes de commit usan Conventional Commits en inglés (`feat:`, `fix:`).
- **Ansible**: YAML con documento `---` inicial, módulos con FQCN (`ansible.builtin.*`, `fortinet.fortios.*`), nombres de playbooks numerados con prefijo (`01_...`), roles con estructura estándar (`defaults/`, `tasks/`, `templates/`). Los defaults del rol llevan el prefijo `fortios_backup_`.
- **Python**: `#!/usr/bin/env python3`, type hints (`dict[str, Any]`, `| None`), docstrings en español, scripts idempotentes estilo "ensure" (buscar por filtros → crear o hacer PATCH), validación de variables de entorno al inicio con `sys.exit(1)` si faltan.
- **Discrepancia conocida**: `group_vars/all.yml` define conexión https/443, pero `playbooks/01_fortigate_backup.yml` la sobreescribe a http/80 sin SSL. Al crear playbooks nuevos, decidir explícitamente qué valor aplica.

## Pruebas y CI

- **No hay tests automatizados ni lint configurado.** La verificación se hace de forma manual:
  - `ansible-playbook --syntax-check playbooks/<playbook>.yml`
  - `ansible-inventory --graph` para validar el inventario dinámico
  - `python -m py_compile scripts/netbox/*.py` para los scripts
- `.gitlab-ci.yml` solo define el template de **Secret Detection** de GitLab; no hay jobs de build, test ni deploy.
- Los cambios se integran por merge requests en GitLab hacia `main` (ramas `feature/...`).

## Despliegue / ejecución

- `ansible.cfg` fija `collections_path` empezando por `/opt/firewall-automation/collections`, lo que sugiere que el nodo de control (o AWX) despliega el proyecto bajo `/opt/firewall-automation`.
- El playbook corre con `serial: 1` (un firewall a la vez) y guarda los artefactos en el nodo de control vía `delegate_to: localhost`.
