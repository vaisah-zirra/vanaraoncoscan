# MVP validation flow

## Entry points

- `/`: public platform page. **Try the MVP** leads to registration; **Join the Pilot / Waitlist** and **Request a demonstration** lead to an interest form with no account requirement.
- `/accounts/signup/`: full name, email, role, organisation, password and evaluation consent. Optional WhatsApp number and separate permission. Registration logs the participant in immediately.
- `/accounts/login/`: returning email/password login; existing administrator usernames still work. No shared credentials are prefilled.
- `/walkthrough/`: the participant's case-by-case progress and feedback.
- `/validation/`: the owner's validation dashboard. Only active superusers can access it; staff/reviewer status alone is insufficient. Sign in with the existing administrator account, then use **Validation analytics** in the sidebar.

## Workspaces and progress

Each participant receives a separate demo facility and four sample patient records. The licensed image library is shared read-only. Registration does not fabricate completed cases, assessments or feedback. Existing seeded demonstration cases do not count as participant rounds.

Each newly started case is one round. Normal completion requires case creation, an attached image, a quality result, an opened assessment, a recorded clinical decision and a successful report response after those steps. Opening the assessment measures a page view, not proof of clinical interpretation. A report response measures a download request, not proof the PDF was saved or read. Repeated requests do not increment the round count.

An inadequate-quality case completes a four-step path: case, image, quality result, quality report. It does not require an AI result or care decision. Different cases never contribute steps to each other's progress.

The feedback prompt appears after completion and can be dismissed. Feedback is also available before completion; its submission records the completion percentage at that time. Each round accepts one response. Consented pilot, pricing, deployment or demonstration interest creates an enquiry for manual follow-up.

## Reading analytics

- Visits are first-party sessions, split after 30 minutes of inactivity. Staff visits are excluded. Sessions are not verified unique people and bot filtering is not guaranteed.
- Campaign links can use `?utm_source=instagram&utm_campaign=mvp` or `?utm_source=whatsapp&utm_campaign=outreach` on the public URL. Only sanitized source/campaign labels are stored; no IP address or browser fingerprint is stored in visit records.
- Registrations and walkthrough results use the chosen registration cohort. Later activity by a member of that cohort still contributes to its completion results. Enquiry counts use the enquiry creation period. Roles are self-reported, not verified credentials.
- The participant table includes accounts that have not started. Latest-round progress is distinct from lifetime completed-round counts.
- Enquiries are requests, not necessarily unique contacts or commercial commitments. Stages and next-action notes are manual and have an audit history. Concurrent edits are detected.
- Earlier consented website enquiries are preserved in the inbox, identified as legacy source where no campaign was recorded.

## Operational boundaries

This feature saves requests locally; it does not send email or WhatsApp messages, book demonstrations, verify email addresses, collect payment or publish the site. The information notice is at `/information/`. Do not use real patient data in this demonstration.

The schema is installed through the normal Django migrations. Regression checks use `manage.py test tests --settings=config.test_settings --noinput`, which uses a separate SQLite test database. MySQL end-to-end verification was also performed with every test record rolled back.
