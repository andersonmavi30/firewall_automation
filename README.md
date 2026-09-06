# Firewall Network Automation

🇨🇴 [Español](README.es.md)

NetDevOps proof of concept for firewall automation, using **NetBox as the source of truth** and **Ansible as the execution engine**.

The repository currently automates **Fortinet FortiGate** configuration backups through the FortiOS REST API. It is designed to grow into a multi-vendor automation project that will also support **Palo Alto Networks (PAN-OS)** and **Check Point (Gaia / Management API)**.

## Vendor support

| Vendor | Platform | Status | Automation |
| --- | --- | --- | --- |
| Fortinet | FortiOS | Available | Full configuration backup via `fortinet.fortios.fortios_monitor` |
| Palo Alto Networks | PAN-OS | Planned | Configuration backup and operational tasks via `paloaltonetworks.panos` |
| Check Point | Gaia / Management API | Planned | Configuration backup and policy tasks via `check_point.mgmt` |

## How it works

1. **NetBox bootstrap** — Python scripts in `scripts/netbox/` create the lab inventory in NetBox through its REST API: the `FortiOS` platform, the `Fortinet` manufacturer, the `firewall` device role, the lab site, the `FortiGate VM` device type, and the lab firewalls with their interfaces and IP addresses.
2. **Dynamic inventory** — Ansible builds its inventory from NetBox with the `netbox.netbox.nb_inventory` plugin (`inventories/netbox/netbox_inventory.yml`). Devices are grouped by site, role, and platform, and only active devices with a primary IP and the `fortios` platform are included.
3. **Backup execution** — `playbooks/01_fortigate_backup.yml` runs the `fortigate_backup` role against the `platform_fortios` group, one firewall at a time (`serial: 1`). The role validates the REST access token, downloads the full configuration (`backup.system.config`), and stores it locally in `artifacts/backups/` with a UTC timestamp.

Backups are written on the Ansible control node with restrictive permissions (`0700` directory, `0600` files), and tasks that handle tokens use `no_log: true`.

## Repository layout

```
ansible.cfg                          # Ansible configuration: NetBox inventory, roles and collections paths
collections/requirements.yml         # Required Ansible collections (netbox.netbox, fortinet.fortios)
requirements.txt                     # Python dependencies
.env.example                         # Template for NETBOX_API and NETBOX_TOKEN
inventories/netbox/
  netbox_inventory.yml               # NetBox dynamic inventory plugin configuration
  group_vars/all.yml                 # Default FortiOS httpapi connection settings (https/443)
playbooks/
  01_fortigate_backup.yml            # FortiGate backup playbook (overrides connection to http/80)
roles/fortigate_backup/
  defaults/main.yml                  # Backup scope, destination path and timestamped filename
  tasks/main.yml                     # Token validation, config download and local save
  templates/backup_report.j2         # Placeholder for a future backup report
scripts/netbox/
  bootstrap_fortios_platform.py      # Ensures the FortiOS platform exists in NetBox
  bootstrap_firewall_lab.py          # Loads the FortiGate lab into NetBox (idempotent)
  get_fortigates.py                  # Placeholder for a future query utility
artifacts/backups/                   # Backup output directory (gitignored)
```

## Requirements

- Python 3 with the packages in `requirements.txt`.
- Ansible core with the collections in `collections/requirements.yml`.
- A reachable NetBox instance and an API token with write permissions for the bootstrap scripts.
- FortiGate REST API access tokens, one per firewall.
- Optional: AWX, using this repository as the project source.

## Quick start

```bash
# Create and activate a virtual environment
python3 -m venv .venv && source .venv/bin/activate

# Install Python and Ansible dependencies
pip install -r requirements.txt
ansible-galaxy collection install -r collections/requirements.yml

# Configure NetBox credentials
cp .env.example .env   # then edit the values
set -a; source .env; set +a

# Bootstrap NetBox (the platform must exist before the lab)
python scripts/netbox/bootstrap_fortios_platform.py
python scripts/netbox/bootstrap_firewall_lab.py

# Verify the dynamic inventory
ansible-inventory --graph

# Run the FortiGate backup
ansible-playbook playbooks/01_fortigate_backup.yml \
  -e '{"fortios_access_tokens": {"FortiGate_A": "<token>", "FortiGate_B": "<token>"}}'
```

Backups are stored as `artifacts/backups/<hostname>_<UTC timestamp>.conf`.

## Configuration and secrets

- `NETBOX_API` / `NETBOX_TOKEN`: required by the NetBox scripts and the dynamic inventory.
- `fortios_access_tokens`: dictionary mapping `hostname -> REST token`. It is **not** stored in the repository; inject it with `--extra-vars`, Ansible Vault, or AWX credentials. The role fails fast if a token is missing.
- `fortios_backup_scope`, `fortios_backup_root` and `fortios_backup_filename`: role defaults controlling the backup scope, destination and naming.
- Real `.env` files, vault files, keys and generated backups are excluded through `.gitignore`. The GitLab pipeline runs Secret Detection.
- Known discrepancy: `inventories/netbox/group_vars/all.yml` defines `https/443`, while `playbooks/01_fortigate_backup.yml` overrides the connection to `http/80` without certificate validation. Choose the connection settings deliberately when adding new playbooks.

## Verification

There is no automated test or lint pipeline yet. Validate changes manually with:

```bash
ansible-playbook --syntax-check playbooks/01_fortigate_backup.yml
ansible-inventory --graph
python -m py_compile scripts/netbox/*.py
```

## Roadmap

- Implement the pending placeholders: `scripts/netbox/get_fortigates.py` and `roles/fortigate_backup/templates/backup_report.j2`.
- Add Ansible lint and playbook syntax checks to CI.
- Add **Palo Alto Networks PAN-OS** support: NetBox platform bootstrap, inventory filters, and a backup role based on `paloaltonetworks.panos`.
- Add **Check Point** support: NetBox platform bootstrap, inventory filters, and a backup role based on `check_point.mgmt`.
- Define a shared backup contract (input variables, output layout and reporting) so all vendors produce consistent artifacts.

## Contributing

Changes are integrated through merge requests to `main` from `feature/...` branches. Commit messages follow Conventional Commits in English (`feat:`, `fix:`, ...). Project content (play and task names, messages, docstrings) is written in Spanish; this README is the bilingual exception.
