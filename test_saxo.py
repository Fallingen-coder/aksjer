"""
Tester Saxo OpenAPI-tilkobling med 24-timers token.
Kjør: python test_saxo.py
"""

import os
import requests

BASE_URL = "https://gateway.saxobank.com/sim/openapi"
TOKEN    = os.environ["SAXO_TOKEN"]

HEADERS = {
    "Authorization": f"Bearer {TOKEN}",
    "Content-Type":  "application/json",
}


def test_account():
    r = requests.get(f"{BASE_URL}/port/v1/accounts/me", headers=HEADERS)
    if r.status_code == 200:
        data = r.json()
        accounts = data.get("Data", [])
        print(f"✓ Kontoer funnet: {len(accounts)}")
        for a in accounts:
            print(f"  - {a.get('AccountId')} | {a.get('Currency')} | {a.get('AccountType')}")
        if accounts:
            return accounts[0]["AccountKey"], accounts[0]["ClientKey"]
        return None, None
    else:
        print(f"✗ Konto-feil: {r.status_code} — {r.text[:200]}")
        return None, None


def test_balance(account_key: str, client_key: str):
    r = requests.get(
        f"{BASE_URL}/port/v1/balances",
        headers=HEADERS,
        params={"AccountKey": account_key, "ClientKey": client_key},
    )
    if r.status_code == 200:
        b = r.json()
        print(f"\n✓ Saldo:")
        print(f"  Totalverdi:    {b.get('TotalValue', '–'):>12,.2f} {b.get('Currency', '')}")
        print(f"  Kontanter:     {b.get('CashBalance', '–'):>12,.2f} {b.get('Currency', '')}")
        exp = b.get('NetExposureInBaseCurrency')
        exp_str = f"{float(exp):>12,.2f}" if exp is not None else "           –"
        print(f"  Eksponering:   {exp_str} {b.get('Currency', '')}")
    else:
        print(f"✗ Saldo-feil: {r.status_code} — {r.text[:200]}")


def test_search_oslo(query: str = "Equinor"):
    r = requests.get(
        f"{BASE_URL}/ref/v1/instruments",
        headers=HEADERS,
        params={
            "Keywords":    query,
            "AssetTypes":  "Stock",
            "ExchangeId":  "OSE",
            "$top":        5,
        },
    )
    if r.status_code == 200:
        data = r.json().get("Data", [])
        print(f"\n✓ Søk etter '{query}' på Oslo Børs:")
        for inst in data:
            print(f"  - {inst.get('Symbol'):<12} {inst.get('Description')}")
    else:
        print(f"✗ Søk-feil: {r.status_code} — {r.text[:200]}")


if __name__ == "__main__":
    print("=== Saxo OpenAPI sandbox-test ===\n")
    account_key, client_key = test_account()
    if account_key:
        test_balance(account_key, client_key)
    test_search_oslo("Equinor")
    test_search_oslo("DNB")
    print("\n=== Ferdig ===")
