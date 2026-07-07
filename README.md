# Base Airdrop Eligibility Checker

A ready-to-use GitHub Actions template that daily checks wallets on
**Base** and computes:

1. **Activity score (0-100)** — an estimate of on-chain activity
   (transaction count, unique active days, contract diversity, wallet
   age, balance). A rough indicator of "does this wallet look alive"
   for future airdrop campaigns whose criteria aren't known yet.
2. **Specific airdrop campaign checks** — add a link to a published
   list of eligible addresses for any project in `campaigns.json`, and
   the script will check your wallets against that list.

This is a template — there are no real wallets or keys baked in here.
Fork the repository and add your own data.

## Quick start

### 1. Fork or copy this repository

### 2. Get a free Blockscout Pro API key

1. https://dev.blockscout.com/ → Login
2. Create an API key (the free tier covers Base)

### 3. Add the secret to your repository

**Settings → Secrets and variables → Actions → New repository secret**
- Name: `BLOCKSCOUT_API_KEY`
- Value: your key

### 4. Replace the example in `wallets.json` with your own addresses

```json
[
  "0xYourAddress1",
  "0xYourAddress2"
]
```

### 5. (Optional) Add specific airdrop campaigns to `campaigns.json`

When a project publishes a list of recipient addresses (typically JSON —
either a flat array or an address -> amount object):

```json
{
  "campaigns": [
    {
      "name": "ProjectName",
      "url": "https://raw.githubusercontent.com/project/airdrop/main/eligible.json"
    }
  ]
}
```

Two response formats are supported at that URL:
- `["0xabc...", "0xdef..."]` — a plain array of addresses
- `{"0xabc...": "1500000000000000000", ...}` — address → amount (wei)

### 6. Run it manually

**Actions → Base Airdrop Eligibility Checker → Run workflow**

After that it runs automatically once a day at 09:00 UTC (change the
`cron` line in `.github/workflows/check.yml` to adjust).

## Structure

```
.
├── wallets.json                  # your wallets (replace the example)
├── campaigns.json                # airdrop campaigns to check (optional)
├── checker.py                    # main script
├── requirements.txt
└── .github/workflows/check.yml   # daily run + manual trigger
```

## Example output

```
🔍 Checking 1 wallet(s) on Base (chainId=8453)
📋 Campaigns to check: 1

=== 0xYourAddress ===
📊 Activity score: 42/100 | tx: 12 | active days: 5 | unique contacts: 4 | wallet age: 30 days | balance: 0.004500 ETH
✅ [ProjectName] Eligible for airdrop | amount: 1500000000000000000
```

## Limitations

- The `activity score` is a simple heuristic for orientation, not an
  official criterion of any specific airdrop.
- Campaign support only handles a plain JSON response at a URL; if a
  project's API requires a signed POST request or authentication,
  you'll need to extend the `fetch_campaign_list` function in
  `checker.py`.

## License

MIT — use it, modify it, fork it freely.
