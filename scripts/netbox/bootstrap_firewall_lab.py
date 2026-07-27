#!/usr/bin/env python3

import os
import sys
from typing import Any

import requests


NETBOX_API = os.environ.get("NETBOX_API", "").rstrip("/")
NETBOX_TOKEN = os.environ.get("NETBOX_TOKEN", "")

if not NETBOX_API or not NETBOX_TOKEN:
    print("ERROR: NETBOX_API y NETBOX_TOKEN deben estar definidos.")
    sys.exit(1)


session = requests.Session()
session.headers.update(
    {
        "Authorization": f"Bearer {NETBOX_TOKEN}",
        "Accept": "application/json",
        "Content-Type": "application/json",
    }
)


def api_request(
    method: str,
    endpoint: str,
    **kwargs: Any,
) -> requests.Response:
    """Ejecuta una solicitud contra la API de NetBox."""

    url = f"{NETBOX_API}/api/{endpoint.lstrip('/')}"

    response = session.request(
        method=method,
        url=url,
        timeout=15,
        **kwargs,
    )

    if not response.ok:
        print(f"ERROR HTTP {response.status_code}: {method} {url}")
        print(response.text)
        response.raise_for_status()

    return response


def get_one(endpoint: str, params: dict[str, Any]) -> dict[str, Any] | None:
    """Obtiene un objeto único usando filtros."""

    data = api_request("GET", endpoint, params=params).json()
    results = data.get("results", [])

    if len(results) > 1:
        raise RuntimeError(
            f"Más de un objeto encontrado en {endpoint} con filtros {params}"
        )

    return results[0] if results else None


def ensure_object(
    endpoint: str,
    lookup: dict[str, Any],
    payload: dict[str, Any],
    label: str,
) -> dict[str, Any]:
    """Crea un objeto solo cuando no existe."""

    obj = get_one(endpoint, lookup)

    if obj:
        print(f"EXISTS: {label} (id={obj['id']})")
        return obj

    obj = api_request("POST", endpoint, json=payload).json()
    print(f"CREATED: {label} (id={obj['id']})")
    return obj


def ensure_device(
    name: str,
    site_id: int,
    device_type_id: int,
    role_id: int,
    platform_id: int,
) -> dict[str, Any]:
    """Crea o actualiza un FortiGate."""

    endpoint = "dcim/devices/"
    device = get_one(
        endpoint,
        {
            "name": name,
            "site_id": site_id,
        },
    )

    payload = {
        "name": name,
        "site": site_id,
        "device_type": device_type_id,
        "role": role_id,
        "platform": platform_id,
        "status": "active",
    }

    if not device:
        device = api_request("POST", endpoint, json=payload).json()
        print(f"CREATED: dispositivo {name} (id={device['id']})")
        return device

    api_request(
        "PATCH",
        f"{endpoint}{device['id']}/",
        json=payload,
    )

    print(f"UPDATED: dispositivo {name} (id={device['id']})")
    return api_request("GET", f"{endpoint}{device['id']}/").json()


def ensure_interface(
    device: dict[str, Any],
    name: str,
    mgmt_only: bool = False,
) -> dict[str, Any]:
    """Crea o actualiza una interfaz del dispositivo."""

    endpoint = "dcim/interfaces/"
    interface = get_one(
        endpoint,
        {
            "device_id": device["id"],
            "name": name,
        },
    )

    payload = {
        "device": device["id"],
        "name": name,
        "type": "virtual",
        "enabled": True,
        "mgmt_only": mgmt_only,
    }

    if not interface:
        interface = api_request("POST", endpoint, json=payload).json()
        print(f"CREATED: {device['name']}:{name}")
        return interface

    api_request(
        "PATCH",
        f"{endpoint}{interface['id']}/",
        json=payload,
    )

    print(f"UPDATED: {device['name']}:{name}")
    return api_request("GET", f"{endpoint}{interface['id']}/").json()


def ensure_ip(
    address: str,
    interface: dict[str, Any],
    description: str,
) -> dict[str, Any]:
    """Crea o asigna una dirección IP a una interfaz."""

    endpoint = "ipam/ip-addresses/"
    ip_address = get_one(endpoint, {"address": address})

    payload = {
        "address": address,
        "status": "active",
        "assigned_object_type": "dcim.interface",
        "assigned_object_id": interface["id"],
        "description": description,
    }

    if not ip_address:
        ip_address = api_request("POST", endpoint, json=payload).json()
        print(f"CREATED: IP {address}")
        return ip_address

    api_request(
        "PATCH",
        f"{endpoint}{ip_address['id']}/",
        json=payload,
    )

    print(f"UPDATED: IP {address}")
    return api_request("GET", f"{endpoint}{ip_address['id']}/").json()


def set_primary_ipv4(
    device: dict[str, Any],
    ip_address: dict[str, Any],
) -> None:
    """Define la dirección de administración como primary IPv4."""

    api_request(
        "PATCH",
        f"dcim/devices/{device['id']}/",
        json={"primary_ip4": ip_address["id"]},
    )

    print(
        f"PRIMARY IPv4: {device['name']} -> "
        f"{ip_address['address']}"
    )


def main() -> None:
    """Carga el laboratorio FortiGate completo en NetBox."""

    platform = get_one(
        "dcim/platforms/",
        {"slug": "fortios"},
    )

    if not platform:
        raise RuntimeError(
            "La plataforma FortiOS con slug 'fortios' no existe."
        )

    manufacturer = ensure_object(
        "dcim/manufacturers/",
        {"slug": "fortinet"},
        {
            "name": "Fortinet",
            "slug": "fortinet",
        },
        "fabricante Fortinet",
    )

    role = ensure_object(
        "dcim/device-roles/",
        {"slug": "firewall"},
        {
            "name": "Firewall",
            "slug": "firewall",
            "color": "e53935",
        },
        "rol Firewall",
    )

    site = ensure_object(
        "dcim/sites/",
        {"slug": "firewall-automation-lab"},
        {
            "name": "Firewall Automation Lab",
            "slug": "firewall-automation-lab",
            "status": "active",
            "description": "PoC NetDevOps Firewall Network Automation",
        },
        "site Firewall Automation Lab",
    )

    device_type = ensure_object(
        "dcim/device-types/",
        {
            "manufacturer_id": manufacturer["id"],
            "slug": "fortigate-vm",
        },
        {
            "manufacturer": manufacturer["id"],
            "model": "FortiGate VM",
            "slug": "fortigate-vm",
            "u_height": 0,
            "is_full_depth": False,
            "default_platform": platform["id"],
        },
        "device type FortiGate VM",
    )

    firewalls = [
        {
            "name": "FortiGate_A",
            "interfaces": {
                "port1": {
                    "address": "172.30.30.26/26",
                    "mgmt_only": True,
                    "description": "Management FortiGate_A",
                },
                "port2": {
                    "address": "40.40.40.1/30",
                    "mgmt_only": False,
                    "description": "Transit FortiGate_A to FortiGate_B",
                },
                "port4": {
                    "address": "10.10.50.254/24",
                    "mgmt_only": False,
                    "description": "LAN gateway 10.10.50.0/24",
                },
            },
        },
        {
            "name": "FortiGate_B",
            "interfaces": {
                "port1": {
                    "address": "172.30.30.27/26",
                    "mgmt_only": True,
                    "description": "Management FortiGate_B",
                },
                "port2": {
                    "address": "40.40.40.2/30",
                    "mgmt_only": False,
                    "description": "Transit FortiGate_B to FortiGate_A",
                },
                "port4": {
                    "address": "10.10.40.254/24",
                    "mgmt_only": False,
                    "description": "LAN gateway 10.10.40.0/24",
                },
            },
        },
    ]

    for firewall_data in firewalls:
        device = ensure_device(
            name=firewall_data["name"],
            site_id=site["id"],
            device_type_id=device_type["id"],
            role_id=role["id"],
            platform_id=platform["id"],
        )

        management_ip = None

        for interface_name, interface_data in firewall_data["interfaces"].items():
            interface = ensure_interface(
                device=device,
                name=interface_name,
                mgmt_only=interface_data["mgmt_only"],
            )

            ip_address = ensure_ip(
                address=interface_data["address"],
                interface=interface,
                description=interface_data["description"],
            )

            if interface_name == "port1":
                management_ip = ip_address

        if management_ip:
            set_primary_ipv4(device, management_ip)

    print("\nOK: laboratorio FortiGate cargado en NetBox.")


if __name__ == "__main__":
    try:
        main()
    except (requests.RequestException, RuntimeError) as error:
        print(f"\nERROR: {error}")
        sys.exit(1)
