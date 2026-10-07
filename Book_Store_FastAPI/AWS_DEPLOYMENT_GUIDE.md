# Deploying the Book Store to AWS (step by step)

This is the last link in the stack (`LEARNING_GUIDE.md` Section 18): the same
`Dockerfile` / `docker-compose.yml` from Section 17, run on managed AWS
services instead of your laptop. It is **documentation only** — no resources
are created by working through this repo; everything below is a guide for
when you're ready to actually deploy (it will incur AWS cost).

Two paths are covered:
- **Path A — EC2** (simplest; a single server runs everything via Docker Compose).
- **Path B — ECS/Fargate** (no servers to patch; the app and worker scale independently).

Start with Path A if this is your first AWS deployment — it's the same mental
model as your laptop, just on a rented machine. Move to Path B once you
understand why you'd want the app and worker to scale separately.

---

## 0. What you're replacing

| Local (`docker-compose.yml`) | AWS service | Section in LEARNING_GUIDE.md |
|---|---|---|
| `db` (MySQL container) | **RDS for MySQL** | 4, 10 |
| `redis` container | **ElastiCache for Redis** | 12, 13 |
| `app` container | **EC2** or **ECS/Fargate** | 6 |
| `worker` container | a second EC2/ECS process, same image | 13 |
| `app/static/*` folders | **S3** | 6, 15 |
| `.env` | **SSM Parameter Store** (or Secrets Manager) | 4 |

Nothing about the *application code* changes — only where its dependencies
live and how it's configured to reach them.

---

## 1. Prerequisites

- An AWS account with billing enabled.
- The [AWS CLI](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html)
  installed and configured (`aws configure` — access key, secret key, default
  region). Use an IAM user with programmatic access, **not** your root account.
- This repo pushed to a container registry later (Section 5) — for now, just
  have it built locally (`docker build -t book-store .` from Section 17 works
  as-is).

Pick one AWS region for everything below (e.g. `ap-south-1` or `us-east-1`) —
resources in different regions can't talk to each other without extra setup.

---

## 2. Networking — a VPC with public + private subnets

Use the AWS-managed default VPC to start (Console → VPC → your account
already has one per region). For a first deployment this is fine; production
setups isolate the database in a private subnet with no direct internet route.

You will create, in this VPC:
- A **security group for the app** (`sg-app`): inbound 8000 (or 80/443 behind
  a load balancer) from the internet, inbound 22 (SSH) from your IP only.
- A **security group for the database** (`sg-db`): inbound 3306 **only from
  `sg-app`** — never open 3306 to the internet.
- A **security group for Redis** (`sg-redis`): inbound 6379 **only from
  `sg-app`**, same reasoning.

This mirrors `docker-compose.yml`'s network isolation (only `app`/`worker`
can reach `db`/`redis` — nothing external can) using AWS's equivalent primitive.

---

## 3. RDS for MySQL (replaces the `db` service)

1. Console → RDS → **Create database**.
2. Engine: **MySQL** (8.0, matching `docker-compose.yml`'s `mysql:8.0`).
3. Templates: "Free tier" for testing, "Production" for real traffic.
4. Settings: DB instance identifier `book-store-db`, master username (e.g.
   `admin`), master password — **generate and save this**, it becomes
   `DB_PASSWORD`.
5. Connectivity: the VPC from Section 2, **no public access**, VPC security
   group = `sg-db`.
6. Additional configuration: initial database name = `book_store_product`
   (matches `DB_DATABASE` in `.env.example` — the app never has to create it).
7. Create it, wait for status **Available**, then copy its **endpoint**
   (looks like `book-store-db.xxxxx.ap-south-1.rds.amazonaws.com`) — this is
   your new `DB_HOST`.

**Migrations against RDS:** once the app can reach RDS (Section 6), run
`alembic upgrade head` against it exactly once per deploy — Section 4 below
shows where that command runs.

---

## 4. ElastiCache for Redis (replaces the `redis` service)

1. Console → ElastiCache → **Create Redis cluster** (or "Serverless" for a
   pay-per-use option that needs no capacity planning up front).
2. Same VPC as RDS, security group = `sg-redis`.
3. No public access — only `sg-app` should ever reach it.
4. Create it, wait for **Available**, copy the **primary endpoint** — this is
   your new `REDIS_HOST` (`REDIS_PORT` stays `6379`).

This one endpoint serves both roles from Sections 12–13 of
`LEARNING_GUIDE.md` (the book-catalogue cache **and** the Celery broker/result
backend) — exactly like the single local Redis container does, just using
`CELERY_BROKER_DB`/`CELERY_RESULT_DB` to keep them logically separate.

---

## 5. S3 (replaces the `app/static/book-covers` and `.../reports` folders)

Container disks are **not durable** and **not shared** across multiple app
instances — a book cover uploaded to one EC2 instance / Fargate task would be
invisible to requests served by another. S3 fixes both problems.

1. Console → S3 → **Create bucket** (e.g. `book-store-static-<your-account-id>`,
   bucket names must be globally unique). Keep "Block all public access" ON —
   serve files through the app or via signed URLs/CloudFront, not a public bucket.
2. This repo's code currently writes uploads to local disk
   (`app/books/web.py::_save_image`, `app/reports/tasks.py::REPORTS_DIR`).
   Swapping those two spots to write to S3 (via `boto3`) instead of the local
   filesystem is the only code change this migration needs — everything else
   in the app is already environment-driven.

---

## 6. Path A — EC2 (single server, Docker Compose)

1. Console → EC2 → **Launch instance**. Amazon Linux 2023, `t3.small` or
   larger, the VPC/subnet from Section 2, security group `sg-app`, a key pair
   you can SSH in with.
2. SSH in, install Docker + the Compose plugin:
   ```bash
   sudo yum install -y docker
   sudo systemctl enable --now docker
   sudo usermod -aG docker $USER   # log out/in once for this to take effect
   sudo curl -SL https://github.com/docker/compose/releases/latest/download/docker-compose-linux-x86_64 \
     -o /usr/libexec/docker/cli-plugins/docker-compose
   sudo chmod +x /usr/libexec/docker/cli-plugins/docker-compose
   ```
3. Copy this repo to the instance (`git clone` or `scp`), then create a `.env`
   there with the **RDS** and **ElastiCache** endpoints from Sections 3–4:
   ```
   DB_HOST=book-store-db.xxxxx.ap-south-1.rds.amazonaws.com
   DB_PASSWORD=<the RDS master password>
   REDIS_HOST=<your ElastiCache primary endpoint>
   CREATE_TABLES=false
   SECRET_KEY=<a long random string — never reuse the repo's dev default>
   ```
4. Drop the `db`/`redis` services out of `docker-compose.yml` on this box
   (you're using RDS/ElastiCache instead) and remove the `depends_on:` blocks
   that reference them — `app`/`worker` now just read `.env` directly. Then:
   ```bash
   docker compose up --build -d
   ```
   `app`'s command still runs `alembic upgrade head` first (Section 17) — your
   RDS schema comes up to date automatically on every deploy.
5. Open port 8000 (or put a load balancer + port 80/443 with a TLS cert in
   front — see Section 7) and browse to `http://<instance-public-ip>:8000/`.

This is the fastest path to "it's live," and a reasonable place to stop for a
learning project or a small internal tool.

---

## 7. Path B — ECS/Fargate (no servers to patch, scales independently)

Once EC2 feels like more server management than you want, move the same
Docker image to Fargate — AWS runs the containers, you never SSH into a host.

1. **Push the image**: Console → ECR → create a repository (e.g.
   `book-store`), then:
   ```bash
   aws ecr get-login-password | docker login --username AWS --password-stdin <account-id>.dkr.ecr.<region>.amazonaws.com
   docker build -t book-store .
   docker tag book-store:latest <account-id>.dkr.ecr.<region>.amazonaws.com/book-store:latest
   docker push <account-id>.dkr.ecr.<region>.amazonaws.com/book-store:latest
   ```
2. **Cluster**: Console → ECS → **Create cluster** → "Networking only" (Fargate).
3. **Task definitions** — create two, both pointing at the image just pushed:
   - `book-store-web`: container command `uvicorn app.main:app --host 0.0.0.0 --port 8000`,
     port mapping 8000, environment variables from Section 6's `.env` list
     (or better: reference them from SSM Parameter Store / Secrets Manager
     instead of typing secrets into the task definition).
   - `book-store-worker`: same image, command
     `celery -A app.core.celery_app worker --loglevel=info` (no port mapping needed).
4. **Services**: run `book-store-web` behind an **Application Load Balancer**
   (target group → port 8000, health check path `/docs`), security group
   `sg-app`. Run `book-store-worker` as a service with **no** load balancer —
   nothing calls it over HTTP, it only reads from the Redis broker.
5. **Migrations**: don't put `alembic upgrade head` in the long-running web
   service's command (every task restart would re-run it concurrently).
   Instead, run it as a **one-off ECS task** (same image, override the
   command to `alembic upgrade head`) as a manual or CI/CD deploy step, before
   updating the web/worker services to the new image.
6. Scale `book-store-web` and `book-store-worker` independently in their
   service settings — e.g. more worker tasks during a bulk report-generation
   period, without touching the web tier at all.

---

## 8. Secrets — SSM Parameter Store instead of a `.env` file on disk

`.env` is fine on your laptop and even on a single EC2 box you control, but
doesn't scale to multiple instances/tasks and shouldn't be baked into a
Docker image. Store each value from `.env.example` as a parameter instead:
```bash
aws ssm put-parameter --name /book-store/DB_PASSWORD --type SecureString --value '...'
aws ssm put-parameter --name /book-store/SECRET_KEY --type SecureString --value '...'
```
Both EC2 (via a startup script that fetches parameters into `.env` before
`docker compose up`) and ECS (via the task definition's `secrets:` block,
which injects them as environment variables at container start — no code
changes needed) can consume these the same way.

---

## 9. A minimal go-live checklist

- [ ] RDS reachable only from `sg-app` (Section 2–3).
- [ ] ElastiCache reachable only from `sg-app` (Section 2–4).
- [ ] `SECRET_KEY` is a real random value, not the repo's dev default.
- [ ] `CREATE_TABLES=false` — Alembic (`alembic upgrade head`) is the only
      thing that changes the schema (LEARNING_GUIDE.md Section 11).
- [ ] Book covers / reports read from and write to S3, not local container disk.
- [ ] The Celery worker is a separate, independently-restartable
      process/service from the web app (never the same container command).
- [ ] HTTPS in front of the app (ALB + ACM certificate, or a reverse proxy) —
      nothing above sets this up, and JWTs/session cookies over plain HTTP
      are visible to anyone on the network path.
