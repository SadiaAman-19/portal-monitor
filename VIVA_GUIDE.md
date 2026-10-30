# Viva Guide: where each concept lives in the code

| Cloud concept (sir's list) | Where | One-sentence explanation |
|---|---|---|
| REST API | `pulse/api_views.py`, `serializers.py`, `api_urls.py` | Token-secured JSON endpoints to manage monitors and read results |
| MVC | `models.py` / `templates/` / `views.py` | Django's MVT: models hold data, views hold logic, templates show it |
| Multithreading | `services.py` -> `run_due_checks()` | `ThreadPoolExecutor` checks many URLs at once; threads only do network I/O |
| Database | `models.py` | Monitor, CheckResult, Incident, Alert; SQLite locally, PostgreSQL on RDS |
| Security | `services.validate_public_url`, `views.py`, settings | SSRF block, login required, per-user queries, API tokens, CSRF, throttling (300/hour) |
| Cloud deployment | `deploy/`, README section 4 | EC2 + gunicorn + nginx + systemd, optional RDS |
| Distributed communication | web app, checker process, DB, REST API | Web server and checker are separate processes that coordinate through the database; clients talk to it over REST |

## Features that make it ours
- **Retry rule:** a monitor is DOWN only after 3 consecutive failures (`FAILURE_THRESHOLD`), so one slow response does not trigger a false alarm.
- **Incidents:** opened when a monitor goes down, closed on recovery, with duration.
- **SSL expiry warning:** at most one alert per day when the certificate has 14 days or fewer left.
- **Public status board and per-user status page:** anyone can check whether a campus portal is down.
- **48-check strip:** a visual history of the last 48 checks.

## Likely viva questions and answers
1. **Why threads and not processes or async?** Each check mostly waits for the network (I/O-bound), so threads are enough and simple. The GIL is released while waiting.
2. **Why do worker threads not write to the database?** SQLite locks under concurrent writes, and Django connections are per thread. Threads return results; the main thread saves them.
3. **How do you stop one slow site blocking the others?** Request timeout (10 s) and a pool of 10 workers.
4. **What is SSRF and how do you prevent it?** A user could make our server request internal addresses (like the AWS metadata IP 169.254.169.254). We resolve the hostname, reject non-public IPs, allow only http/https, and do not follow redirects.
5. **What are the limits of that protection?** DNS rebinding: the IP could change between validation and the request. A fix is to connect to the validated IP directly.
6. **Why wait for 3 failures?** Networks fail briefly. Requiring consecutive failures reduces false alarms.
7. **How is user data isolated?** Every query filters by `owner=request.user`; other users get 404 (tests prove it).
8. **What if the checker crashes?** systemd restarts it (`Restart=always`). Monitors keep their `next_check`, so overdue checks run immediately on restart.
9. **How would you scale it?** Several checker instances claiming monitors with `select_for_update(skip_locked=True)` on PostgreSQL, or a queue such as SQS, plus a load balancer for the web tier.
10. **Why Django?** Built-in auth, ORM, admin, CSRF protection, and templates; REST via DRF.

## Each member should be able to explain
- **Member 1:** `models.py`, database design, admin, tests.
- **Member 2:** `services.py` (SSRF, checker, retry/incident rules, thread pool), `check_monitors`.
- **Member 3:** `views.py`, templates, REST API, deployment on AWS.
Everyone should still be able to run the demo and describe the whole flow.

## Report checklist (documentation marks)
Architecture diagram, ER diagram, screenshots of every page, API screenshots from Postman, test output (`python manage.py test`), AWS screenshots (EC2 running, security group, public URL), a "technology choices and why" section, limitations, and GitHub commit history from all three members.
