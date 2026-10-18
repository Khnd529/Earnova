Earnova Mini App starter

1. GitHub repo root-এ index.html, style.css, app.js রাখো। GitHub Settings > Pages > Deploy from branch > main > /(root) > Save। GitHub Free-তে Pages চালাতে public repo লাগতে পারে; secret কখনো repo-তে রেখো না.
2. Cloudflare Dashboard > Workers & Pages > D1 SQL Database > Create database (earnova-db)। D1 Console-এ schema.sql-এর SQL চালাও।
3. Workers & Pages > Create Worker > Deploy > Edit code। worker.js paste করে Save and Deploy।
4. Worker Settings > Variables and Secrets: BOT_TOKEN (Secret), BOT_USERNAME (Text, @ ছাড়া) যোগ করো।
5. Worker Settings > Bindings > Add binding > D1 database; Variable name DB, database earnova-db. Save and Deploy.
6. Worker URL কপি করে app.js-এর API_BASE-এ বসিয়ে GitHub-এ commit করো।
7. BotFather > /mybots > bot > Bot Settings/Menu Button/Mini App URL-এ GitHub Pages URL সেট করো। Telegram app-এর ভেতর থেকে খুলে পরীক্ষা করো.

Security: Telegram initData signature/auth_date Worker-এ validate হয়. Task rewards, referral bonus, admin approval, payment integration এই starter-এ নেই. Withdrawal request শুধু pending record করে; টাকা পাঠায় না. Real money launch-এর আগে ledger, admin controls, rate limits, backups, audit trail ও payment reconciliation যোগ করো.