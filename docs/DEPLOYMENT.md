# Production preparation

Prepared for a single Railway web replica and a separate Railway MySQL service. Nothing is deployed by adding these files.

## Hosting setup (next phase)

1. Connect the repository and use the included Dockerfile.
2. Add MySQL and reference its private-network variables as MYSQL_DATABASE, MYSQL_USER, MYSQL_PASSWORD, MYSQL_HOST and MYSQL_PORT on the web service. Never use local workstation credentials.
3. Generate a new 50+ character random DJANGO_SECRET_KEY privately. Set all variables in .env.production.example in Railway, replacing the hostname with the actual public domain. Production ignores local .env files and forces DEBUG off.
4. Mount a persistent volume at /data; set DJANGO_MEDIA_ROOT=/data/media. Keep one web replica for this MVP. Sample images remain behind authenticated application endpoints; do not expose the media directory publicly.
5. Start runs deployment checks, migrations, static collection, checksum-verified sample import and Gunicorn. The import repairs missing sample files without changing image pixels. No demo reset or account creation happens automatically.
6. Provision the administrator and shared demo accounts privately after deployment. Keep passwords in private hosting configuration/password storage, never in Git. Login fields remain empty. Existing local users and validation data are not copied automatically.
7. Verify HTTPS redirects, signup and return login, private case/image access, every assessment branch, report downloads, feedback and administrator analytics. Verify persistence through a restart. Test the Linux container/startup on Railway before calling deployment verified.

## Security and operations

Railway must terminate TLS and overwrite X-Forwarded-Proto; Gunicorn must not be directly internet-accessible. Host and CSRF origin lists are explicit, secure cookies are mandatory, and HSTS initially lasts one hour without subdomain/preload commitments. Increase HSTS only after HTTPS is verified. Static assets use WhiteNoise compressed manifests. Secrets are environment-only, and Docker/Git ignore credentials, database dumps and generated reports.

Configure database backups and test restore before collecting important validation data. Password recovery/email verification, distributed rate limiting and the final public privacy/contact review remain wider-public-launch work. The current signup/enquiry cooldowns are not a full abuse-prevention service. This remains a workflow prototype, not a clinical deployment.

## Local verification

Run `python manage.py test --settings=config.test_settings --noinput` for the isolated suite. Production checks require explicit placeholder environment settings and must not point to the production database during local QA. Never run demo resets or test-schema creation against a live production database.

References: https://docs.railway.com/guides/django and https://docs.djangoproject.com/en/5.2/howto/deployment/checklist/

Deployment checks intentionally retain Django warnings W005 and W021 until subdomain HTTPS and HSTS preload ownership can be confirmed; errors stop startup. Do not enable preload merely to silence these warnings.
