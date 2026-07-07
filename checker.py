#!/usr/bin/env python3
"""
Base Airdrop Eligibility Checker (public template).

For every wallet in wallets.json:
1. Computes an "activity score" (0-100) based on on-chain activity on
   Base — a rough indicator of "does this wallet look alive" for future
   airdrop campaigns whose criteria aren't known yet.
2. Checks the wallet's membership in each campaign from campaigns.json —
   supports two common formats for publicly published airdrop lists:
   - a flat array of addresses: ["0xabc...", "0xdef..."]
   - an address -> amount object: {"0xabc...": "1500000000000000000"}

This is a generic template — no personal wallet or project is baked in.
Add your own addresses to wallets.json and (optionally) campaigns to
campaigns.json.
"""

import os
import json
import requests

CHAIN_ID = 8453  # Base mainnet
BLOCKSCOUT_URL = "https://api.blockscout.com/v2/api"

PLACEHOLDER_ADDRESS = "0x0000000000000000000000000000000000000000"

API_KEY = os.environ.get("BLOCKSCOUT_API_KEY")
WALLETS_FILE = os.environ.get("WALLETS_FILE", "wallets.json")
CAMPAIGNS_FILE = os.environ.get("CAMPAIGNS_FILE", "campaigns.json")

if not API_KEY:
    raise SystemExit("❌ BLOCKSCOUT_API_KEY secret is not set")


def load_json(path, default):
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return default


def api_get(params, retries=2):
    query = {"chainid": CHAIN_ID, "apikey": API_KEY, **params}
    for attempt in range(retries + 1):
        try:
            resp = requests.get(BLOCKSCOUT_URL, params=query, timeout=30)
            resp.raise_for_status()
            data = resp.json()
            if data.get("status") == "0" and data.get("message") not in ("No transactions found", "OK"):
                return None
            return data.get("result")
        except requests.exceptions.RequestException as e:
            if attempt < retries:
                continue
            print(f"⚠️  Failed to fetch data ({params.get('action')}): {e}")
            return None


def get_balance_eth(address):
    result = api_get({"module": "account", "action": "balance", "address": address})
    try:
        return int(result) / 1e18
    except (TypeError, ValueError):
        return 0.0


def get_normal_txs(address):
    result = api_get({
        "module": "account",
        "action": "txlist",
        "address": address,
        "startblock": 0,
        "endblock": 99999999,
        "sort": "asc",
    })
    return result if isinstance(result, list) else []


def compute_activity_score(txs, balance_eth):
    tx_count = len(txs)

    if tx_count == 0:
        return {
            "score": 0,
            "tx_count": 0,
            "active_days": 0,
            "unique_contacts": 0,
            "wallet_age_days": 0,
            "balance_eth": balance_eth,
        }

    timestamps = sorted(int(tx["timeStamp"]) for tx in txs if tx.get("timeStamp"))
    active_days = len({ts // 86400 for ts in timestamps})
    wallet_age_days = max(1, (timestamps[-1] - timestamps[0]) // 86400)
    unique_contacts = len({tx.get("to", "").lower() for tx in txs if tx.get("to")})

    # Simple heuristic weighting of components, total capped at 100
    score = 0
    score += min(30, tx_count)                     # up to 30 points for tx count
    score += min(25, active_days * 2)               # up to 25 points for unique active days
    score += min(20, unique_contacts)                # up to 20 points for contract diversity
    score += min(15, wallet_age_days // 10)          # up to 15 points for wallet age
    score += 10 if balance_eth > 0 else 0            # 10 points for a non-zero balance
    score = min(100, score)

    return {
        "score": score,
        "tx_count": tx_count,
        "active_days": active_days,
        "unique_contacts": unique_contacts,
        "wallet_age_days": wallet_age_days,
        "balance_eth": balance_eth,
    }


def fetch_campaign_list(campaign):
    try:
        resp = requests.get(campaign["url"], timeout=30)
        resp.raise_for_status()
        data = resp.json()
    except (requests.exceptions.RequestException, json.JSONDecodeError) as e:
        print(f"⚠️  Failed to load campaign '{campaign.get('name')}': {e}")
        return None

    if isinstance(data, list):
        return {addr.lower(): None for addr in data}
    if isinstance(data, dict):
        return {addr.lower(): amount for addr, amount in data.items()}

    print(f"⚠️  Unknown data format for campaign '{campaign.get('name')}'")
    return None


def check_campaigns(address, campaigns):
    results = []
    for campaign in campaigns:
        name = campaign.get("name", "unnamed")
        eligibility_map = fetch_campaign_list(campaign)
        if eligibility_map is None:
            results.append((name, "error", None))
            continue
        amount = eligibility_map.get(address.lower())
        if address.lower() in eligibility_map:
            results.append((name, "eligible", amount))
        else:
            results.append((name, "not_eligible", None))
    return results


def main():
    wallets = load_json(WALLETS_FILE, [])
    campaigns = load_json(CAMPAIGNS_FILE, {}).get("campaigns", [])

    wallets = [w for w in wallets if w.lower() != PLACEHOLDER_ADDRESS]

    if not wallets:
        print(
            f"⚠️  {WALLETS_FILE} has no real addresses (only the example placeholder). "
            f"Add your own wallets to get a result."
        )
        return

    print(f"🔍 Checking {len(wallets)} wallet(s) on Base (chainId={CHAIN_ID})")
    if campaigns:
        print(f"📋 Campaigns to check: {len(campaigns)}")
    else:
        print("📋 No campaigns in campaigns.json — computing activity score only")

    for address in wallets:
        print("")
        print(f"=== {address} ===")

        balance = get_balance_eth(address)
        txs = get_normal_txs(address)
        stats = compute_activity_score(txs, balance)

        print(
            f"📊 Activity score: {stats['score']}/100 | "
            f"tx: {stats['tx_count']} | "
            f"active days: {stats['active_days']} | "
            f"unique contacts: {stats['unique_contacts']} | "
            f"wallet age: {stats['wallet_age_days']} days | "
            f"balance: {stats['balance_eth']:.6f} ETH"
        )

        if campaigns:
            for name, status, amount in check_campaigns(address, campaigns):
                if status == "eligible":
                    extra = f" | amount: {amount}" if amount else ""
                    print(f"✅ [{name}] Eligible for airdrop{extra}")
                elif status == "not_eligible":
                    print(f"❌ [{name}] Not in the list")
                else:
                    print(f"⚠️  [{name}] Could not be checked")


if __name__ == "__main__":
    main()
