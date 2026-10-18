# Earnova Telegram Bot (starter)

## Features
- Telegram ID-based profile; no separate signup/login
- Wallet balance display
- Task list (no automatic reward yet)
- Referral link capture (no automatic bonus yet)
- Withdrawal request queue for bKash/Nagad/Rocket
- Admin commands for pending, approve/reject, manual credit, and stats
- SQLite starter database

## Important limitations
- This is a starter project, not a production-ready real-money system.
- Polling requires a hosting service that permits a continuously running worker. Many free tiers sleep, restrict workers, or have ephemeral filesystems.
- SQLite data may be lost on hosts with ephemeral storage. For deployment, use a persistent database (e.g. managed PostgreSQL) and verify free-tier limits.
- No ad provider verification, task proof verification, referral bonus, or automatic payment integration is included.
- Admin approval only records an approved withdrawal and deducts the displayed balance; it does not send money.
- Configure ADMIN_IDS with your own Telegram numeric user ID.
- Never put BOT_TOKEN or database credentials in source code or commit them to GitHub.

## Run locally
1. Install Python 3.11+.
2. `pip install -r requirements.txt`
3. Set environment variables:
   - `BOT_TOKEN=your_token`
   - `ADMIN_IDS=your_telegram_numeric_id`
   - optional `MIN_WITHDRAW=500`
4. `python bot.py`

## Admin commands
- `/admin`
- `/pending`
- `/approve REQUEST_ID`
- `/reject REQUEST_ID`
- `/credit TELEGRAM_ID AMOUNT NOTE`
- `/stats`

## User commands
- `/start`
- `/wallet`
- `/tasks`
- `/withdraw 500 bkash 01XXXXXXXXX`
- `/cancel`

## Before real launch
Move to a persistent database, add migrations, rate limits, transaction/audit controls, admin confirmation, provider-compliant ad verification, backup/restore, and payment reconciliation. Test all flows with dummy users and no real money first.
