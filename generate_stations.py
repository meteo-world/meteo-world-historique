#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import os
import sys
import time
from pathlib import Path

import requests

API_URL = "https://public-api.meteofrance.fr/public/DPClim/v1/liste-stations/horaire"
OUTPUT_FILE = Path("data/stations-meteofrance.json")
DEPARTEMENTS = [f"{n:02d}" for n in range(1,20)] + ["2A","2B"] + [f"{n:02d}" for n in range(21,96)]
REQUEST_DELAY_SECONDS = 1.5
TIMEOUT_SECONDS = 45


def first_value(obj, *keys):
    for key in keys:
        if key in obj and obj[key] not in (None, ""):
            return obj[key]
    return None


def to_float(value):
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def normalize_station(raw, departement):
    station_id = first_value(raw, "id", "id_station", "id-station", "numero", "num_poste", "numer_sta")
    if station_id is None:
        return None
    station_id = str(station_id).strip().zfill(8)

    nom = first_value(raw, "nom", "name", "nom_station", "libelle", "lieu")
    latitude = to_float(first_value(raw, "lat", "latitude", "lat_wgs84"))
    longitude = to_float(first_value(raw, "lon", "lng", "longitude", "lon_wgs84"))
    altitude = to_float(first_value(raw, "altitude", "alti", "alt"))
    date_debut = first_value(raw, "date_debut", "date-debut", "date_ouverture", "dateDebut", "dateDeb")
    date_fin = first_value(raw, "date_fin", "date-fin", "date_fermeture", "dateFin")

    return {
        "id": station_id,
        "nom": str(nom).strip() if nom is not None else station_id,
        "departement": str(departement),
        "latitude": latitude,
        "longitude": longitude,
        "altitude": altitude,
        "date_debut": date_debut,
        "date_fin": date_fin,
    }


def fetch_department(session, api_key, departement):
    params = {"id-departement": departement, "apikey": api_key}
    response = session.get(API_URL, params=params, timeout=TIMEOUT_SECONDS)
    if response.status_code == 404:
        print(f"[{departement}] aucune donnée (404)")
        return []
    response.raise_for_status()
    data = response.json()
    if not isinstance(data, list):
        raise RuntimeError(f"Réponse inattendue pour {departement}: {type(data).__name__}")

    stations = []
    for raw in data:
        if isinstance(raw, dict):
            station = normalize_station(raw, departement)
            if station:
                stations.append(station)
    print(f"[{departement}] {len(stations)} station(s)")
    return stations


def main():
    api_key = os.environ.get("METEOFRANCE_API_KEY", "").strip()
    if not api_key:
        print("ERREUR : le secret METEOFRANCE_API_KEY est absent.", file=sys.stderr)
        sys.exit(1)

    session = requests.Session()
    session.headers.update({"User-Agent": "Meteo-World-Historique/1.0", "Accept": "application/json"})

    stations_by_id = {}
    failed = []

    for index, departement in enumerate(DEPARTEMENTS, start=1):
        print(f"\nDépartement {departement} ({index}/{len(DEPARTEMENTS)})")
        try:
            for station in fetch_department(session, api_key, departement):
                stations_by_id[station["id"]] = station
        except Exception as exc:
            print(f"ERREUR pour {departement}: {exc}", file=sys.stderr)
            failed.append(departement)
        if index < len(DEPARTEMENTS):
            time.sleep(REQUEST_DELAY_SECONDS)

    stations = sorted(stations_by_id.values(), key=lambda s: (s.get("departement") or "", s.get("nom") or "", s.get("id") or ""))
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_FILE.write_text(json.dumps(stations, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print("\n======================================")
    print(f"Stations uniques : {len(stations)}")
    print(f"Fichier généré   : {OUTPUT_FILE}")
    if failed:
        print("Départements en erreur : " + ", ".join(failed))
    if not stations:
        sys.exit(2)


if __name__ == "__main__":
    main()
