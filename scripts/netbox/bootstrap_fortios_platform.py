#!/usr/bin/env python3

import os
import sys

import requests


NETBOX_API = os.environ.get("NETBOX_API", "").rstrip("/")
NETBOX_TOKEN = os.environ.get("NETBOX_TOKEN", "")

if not NETBOX_API or not NETBOX_TOKEN:
    print("ERROR: NETBOX_API y NETBOX_TOKEN deben estar definidos.")
    sys.exit(1)

endpoint = f"{NETBOX_API}/api/dcim/platforms/"

headers = {
    "Authorization": f"Bearer {NETBOX_TOKEN}",
    "Accept": "application/json",
    "Content-Type": "application/json",
}

try:
    response = requests.get(
        endpoint,
        headers=headers,
        params={"slug": "fortios"},
        timeout=10,
    )
    response.raise_for_status()

    if response.json()["count"] > 0:
        print("OK: La plataforma FortiOS ya existe.")
        sys.exit(0)

    response = requests.post(
        endpoint,
        headers=headers,
        json={
            "name": "FortiOS",
            "slug": "fortios",
        },
        timeout=10,
    )
    response.raise_for_status()

    platform = response.json()
    print(
        f"CREATED: {platform['name']} "
        f"(slug={platform['slug']}, id={platform['id']})"
    )

except requests.RequestException as error:
    print(f"ERROR consultando NetBox: {error}")
    if getattr(error, "response", None) is not None:
        print(error.response.text)
    sys.exit(1)
