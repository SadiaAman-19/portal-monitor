# Portal Monitor

A cloud-hosted uptime monitor for campus portals (result sites, admission pages, fee systems).
It checks many URLs in parallel, opens an incident only after 3 failed checks in a row, warns about
expiring SSL certificates, and publishes a public status board. Built with Django + Django REST Framework.

## 1. Run it on your laptop (Windows / VS Code)

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
python manage.py migrate
python manage.py seed_demo          # creates user demo / demo12345 and 5 sample monitors
python manage.py runserver
```

Open http://127.0.0.1:8000/ . In a **second terminal** (venv activated) start the background checker:

```powershell
python manage.py check_monitors
```

Run the tests: `python manage.py test`

## 2. Demo script (about 4 minutes)

1. Home page: the public status board and the search box.
2. Log in as `demo`. The dashboard shows the 48-check strips, uptime, and SSL days.
3. Open a monitor, press **Check now**, and show the response-time chart and recent checks.
4. Open the "Missing site" monitor: show **consecutive failures 1, 2, 3**, then the incident opening and the alert.
5. Add a monitor with `http://127.0.0.1` and show the **SSRF protection** message.
6. Open `/status/demo/` (the public status page) and the **Alerts** page.
7. Show the API in Postman (section 3) and the AWS URL.

To show **recovery**, add a working URL, wait for it to be UP, change nothing, then pause it. Or edit the
URL in `/admin/` from a bad one to a good one and watch the incident close.

## 3. REST API

```
POST /api/token/                      body: username, password  ->  {"token": "..."}
GET  /api/monitors/                   header: Authorization: Token <token>
POST /api/monitors/                   {"name":"MUET","url":"https://www.muet.edu.pk","interval_seconds":60}
GET  /api/monitors/<id>/results/
POST /api/monitors/<id>/check_now/
```

## 4. Deploy on AWS EC2 (Ubuntu 22.04/24.04, free-tier t2/t3.micro)

1. **Launch EC2.** Security group: allow SSH (22) from your IP and HTTP (80) from anywhere.
2. **Connect and install:**
   ```bash
   sudo apt update && sudo apt install -y python3-venv python3-pip nginx git
   git clone <your-github-repo> campuspulse && cd campuspulse
   python3 -m venv venv && source venv/bin/activate
   pip install -r requirements.txt
   cp deploy/env.example .env      # then edit .env (SECRET_KEY, ALLOWED_HOSTS = your public IP)
   set -a; source .env; set +a
   python manage.py migrate
   python manage.py collectstatic --noinput
   python manage.py createsuperuser
   ```
3. **Run web + checker as services:**
   ```bash
   sudo cp deploy/campuspulse-web.service deploy/campuspulse-worker.service /etc/systemd/system/
   sudo systemctl daemon-reload
   sudo systemctl enable --now campuspulse-web campuspulse-worker
   ```
4. **Nginx:** `sudo cp deploy/nginx.conf /etc/nginx/sites-available/campuspulse`, then
   `sudo ln -s /etc/nginx/sites-available/campuspulse /etc/nginx/sites-enabled/`,
   `sudo rm /etc/nginx/sites-enabled/default`, `sudo nginx -t && sudo systemctl restart nginx`.
5. Open `http://<EC2 public IP>/`. Take screenshots for your report.
6. **Optional (extra marks): PostgreSQL on RDS.** Create a free-tier RDS PostgreSQL instance, allow port 5432 from the
   EC2 security group, `pip install psycopg2-binary`, and set `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST` in `.env`.

**Cost warning:** stop or terminate EC2/RDS after the demo, and check the AWS Free Tier limits for your account.

## 5. Known limits (say these yourself in the viva)

- DNS-rebinding is not fully prevented (we validate the IP before the request, not on the connection itself).
- Redirects are not followed on purpose (SSRF); a 3xx counts as "up".
- One checker process. Several checkers would need a queue or row locking.
