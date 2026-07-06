#!/usr/bin/env python3
"""
Base Airdrop Eligibility Checker (публічний шаблон).

Для кожного гаманця з wallets.json:
1. Рахує "activity score" (0-100) на основі on-chain активності в Base —
   орієнтир "чи виглядає гаманець живим" для майбутніх airdrop-кампаній,
   критерії яких ще невідомі.
2. Перевіряє гаманець на членство в кожній кампанії з campaigns.json —
   підтримує два поширені формати публічних airdrop-списків:
   - плаский масив адрес: ["0xabc...", "0xdef..."]
   - об'єкт адреса -> сума: {"0xabc...": "1500000000000000000"}

Це шаблон без прив'язки до конкретного гаманця чи проєкту — додай свої
адреси в wallets.json і (опційно) кампанії в campaigns.json.
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
    raise SystemExit("❌ Не заданий секрет BLOCKSCOUT_API_KEY")


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
            print(f"⚠️  Не вдалося отримати дані ({params.get('action')}): {e}")
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

    # Проста евристична вага компонентів, підсумок обмежений 100
    score = 0
    score += min(30, tx_count)                     # до 30 балів за кількість транзакцій
    score += min(25, active_days * 2)               # до 25 балів за унікальні активні дні
    score += min(20, unique_contacts)                # до 20 балів за різноманіття контрактів
    score += min(15, wallet_age_days // 10)          # до 15 балів за вік гаманця
    score += 10 if balance_eth > 0 else 0            # 10 балів за ненульовий баланс
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
        print(f"⚠️  Не вдалося завантажити кампанію '{campaign.get('name')}': {e}")
        return None

    if isinstance(data, list):
        return {addr.lower(): None for addr in data}
    if isinstance(data, dict):
        return {addr.lower(): amount for addr, amount in data.items()}

    print(f"⚠️  Невідомий формат даних для кампанії '{campaign.get('name')}'")
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
            f"⚠️  У {WALLETS_FILE} немає реальних адрес (тільки приклад-заглушка). "
            f"Додай свої гаманці, щоб отримати результат."
        )
        return

    print(f"🔍 Перевірка {len(wallets)} гаманця(ів) у мережі Base (chainId={CHAIN_ID})")
    if campaigns:
        print(f"📋 Кампаній для перевірки: {len(campaigns)}")
    else:
        print("📋 Кампаній у campaigns.json немає — рахую тільки activity score")

    for address in wallets:
        print("")
        print(f"=== {address} ===")

        balance = get_balance_eth(address)
        txs = get_normal_txs(address)
        stats = compute_activity_score(txs, balance)

        print(
            f"📊 Activity score: {stats['score']}/100 | "
            f"tx: {stats['tx_count']} | "
            f"активні дні: {stats['active_days']} | "
            f"унікальні контакти: {stats['unique_contacts']} | "
            f"вік гаманця: {stats['wallet_age_days']} дн | "
            f"баланс: {stats['balance_eth']:.6f} ETH"
        )

        if campaigns:
            for name, status, amount in check_campaigns(address, campaigns):
                if status == "eligible":
                    extra = f" | сума: {amount}" if amount else ""
                    print(f"✅ [{name}] Є в списку на airdrop{extra}")
                elif status == "not_eligible":
                    print(f"❌ [{name}] Немає в списку")
                else:
                    print(f"⚠️  [{name}] Не вдалося перевірити")


if __name__ == "__main__":
    main()
