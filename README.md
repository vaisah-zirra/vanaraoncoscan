# VanaraOncoScan

Local workflow prototype. The blueprint is the product baseline.

## Local setup (PowerShell)

1. Activate `.venv\Scripts\Activate.ps1`.
2. Fill MYSQL_USER and MYSQL_PASSWORD in `.env` privately. Never commit this file.
3. Create the dedicated schema using `python scripts/bootstrap_database.py`.
4. Run `python manage.py migrate`.
5. Run `python manage.py seed_demo` and choose the facility demo password privately.
6. Run `python manage.py createsuperuser` for an operational administrator.
7. Run `python manage.py runserver` and open http://127.0.0.1:8000/.

`python manage.py test --settings=config.test_settings` runs portable foundation tests in memory. Run `python manage.py test` separately against MySQL before declaring database integration validated (the account needs test-schema creation rights).

## Scope and status

Implemented: MySQL foundation, facility isolation, dashboard, searchable patient selection, licensed image picker, technical quality checks, predefined assessments with source-derived annotations, and clinician care-plan confirmation. PDF reports, care planning, referral and follow-up tracking, participant signup, feedback and administrator validation analytics are available. Live specialist operations and billing remain outside this MVP. No live diagnostic model is used.

The virtual environment currently uses the locally bundled Python 3.12 runtime. Recreate it with a standalone Python installation if that runtime is removed. Install dependencies from requirements.txt.

Production configuration and Railway container startup are prepared; deployment has not yet taken place. See docs/DEPLOYMENT.md for environment variables, persistent storage, account provisioning and live verification.


## Image library and attachment workflow

After migrations, run `python manage.py seed_image_library` to install six attributed ultrasound sample images into local media. Original PNGs and checksums are versioned under `library_assets/`; this command validates them before importing. `library_assets/ATTRIBUTION.md` documents licence and provenance.

New assessment creation opens the upload-style sample picker. Attach, replace and remove actions are transactional, facility-scoped, CSRF-protected and recorded in the case timeline. Replacements after quality/assessment records exist are rejected; Try another sample creates a new case. The library images are served through authenticated endpoints rather than public media URLs.

Technical checks verify file integrity, decoding and resolution before a predefined assessment is created. Source masks supply bounding boxes; they are not model attention maps.

## Clinical review and care plans

Open Clinical review from a case or assessment result. A facility user can confirm referral details and urgency, request specialist input, or schedule follow-up. Suggested notes must be reviewed; confirmation is never preselected. Referral destinations are editable service suggestions, not a directory of connected providers. Saving a referral records it locally and does not transmit it.

Decisions preserve actor, time, notes and pathway details. Transactions, case locks, version checks and submission identifiers protect against stale or duplicate submissions. Follow-up for non-routine assessments requires a signed specialist opinion. Existing referrals and active follow-up plans cannot be overwritten by this screen. All routes retain facility and CSRF protection.

Run migrations after updating: `python manage.py migrate`. Run checks with `python manage.py check` and portable tests with `python manage.py test --settings=config.test_settings`.


## Downloadable case reports

The authenticated `cases/<uuid>/report.pdf` route produces a private PDF without mutating clinical records. Download links appear on case, quality, assessment and clinical-review screens. Reports contain history, verified source images and matching annotations, assessment, case-appropriate predefined specialist text for demo patients, recorded care plans and all milestones. Signed reviews take precedence over predefined text. Failed quality suppresses diagnostic interpretation. Pending cases and absent information are identified explicitly.

Report template and specialist content have independent versions; a content fingerprint identifies each revision. The PDF shows the prototype notice on every page and does not manufacture clinical measurements, a signature or a completed review. Files are generated in memory with no public media copy, and responses carry no-store headers. ReportLab and pypdf are pinned dependencies for generation and export tests.


## Assessment impressions and confidence rings

A shared presentation module provides consistent clinical labels, colours and illustrative confidence scores across the dashboard, case, assessment, clinical review and PDF. Scores are enabled only for demo patients with a passed quality record and an assessment matching a known sample identity, checksum and disposition. Existing assessment snapshots and clinical state are not changed. Pending, failed-quality, unmatched and non-demo cases do not receive an invented score.

The filled ring is the displayed percentage; the unfilled segment is its remainder. Labels and percentages accompany colour for accessibility. The key explains each impression and distinguishes classification confidence from cancer probability. Demo scores are explicitly identified in both interfaces and exports.


## Follow-up workspace

The Follow-ups navigation opens a facility-scoped schedule with search, status filters, pagination and overdue/today/completed counts. Users can reschedule with a reason or complete a review with an outcome and explicit confirmation. Updates preserve the original plan, record actor and time, and are protected by case locks, revision checks and idempotent submission IDs. Completed outcomes cannot be overwritten. A case in Follow-up closes only when its final open follow-up is completed; other case states are preserved. The case timeline and exported report include completion information. No patient messages or appointment notifications are sent.


### Referral coordination and specialist content
The referral register at `/referrals/` supports scoped search, stage and urgency filters, and paginated records. Staff can record acknowledgement, appointment dates, completion or cancellation with confirmed notes. Updates are transactional, version checked and idempotent; terminal records are preserved. Referral stages do not imply messages were sent or automatically close the clinical case. The case timeline and PDF include recorded updates.

Case and clinician-review screens now use the same specialist response source as the PDF. Signed reviews take precedence; automatic content is limited to prototype patients at demo facilities and never signs a review.


### Public website
The public homepage is `/`; the protected facility dashboard is `/workspace/`. Named dashboard links and post-login redirects use the new route. Public enquiries are validated and saved in Accounts → Website enquiries in Django admin, accessible only to authorised staff. No email notification or public deployment is configured by this change. The form requires reply consent, includes a honeypot and a per-session one-minute submission cooldown. Production deployment needs shared abuse prevention and an agreed contact-data retention process. Subscription categories are enquiry categories, not checkout products.


### Structured ultrasound report (BI-RADS lexicon)
Each library image has an authored structured report in `apps/clinical/report_library.py` (version `structured-us-report-1.0`): examination and technique, background echotexture, per-lesion ACR BI-RADS® ultrasound descriptors (shape, orientation, margin, echo pattern, posterior features, calcifications, associated features) with the significance of each, quantitative morphometrics from the source segmentation mask (width-to-height ratio, circularity, solidity, depth), BI-RADS category with likelihood of malignancy and standard management, numbered impression and recommendations, differential diagnosis, an explanation of how the result was reached, and a patient-friendly summary. Model confidence is shown against the teleradiology threshold (`TELERADIOLOGY_THRESHOLD = 70`). The report appears on the assessment result (full), case and clinician-review screens (compact) and in the PDF; the clinician's suggested approach leads with the BI-RADS management. Image-specific example teleradiology responses replace the generic predefined text for library images. Sizes are in pixels because the source images carry no pixel-spacing calibration. All content is predefined demo material and must be reviewed by a breast radiologist before clinical or promotional use; when a trained model is connected, it should populate the same report structure.

### Pilot experience (realistic AI journey)
The tester-facing workspace no longer labels results as demo content. Changes for the pilot build:
- **AI processing:** quality checks and assessments run through a staged pipeline dialog (`processing_dialog.html`, `static/assessment.js`) with a scanning image preview, per-step timings and a progress bar. Results are still the predefined library profiles; the server call runs in parallel with the animation.
- **First-view reveal:** directly after processing, the confidence ring counts up, the lesion box locks on, and report rows rise into view. Revisiting a result shows it static. `prefers-reduced-motion` is respected throughout.
- **Model presentation:** confidence scores carry one decimal (`apps/clinical/presentation.py`) and are tagged with the model label `VOS-BUS v0.9.4 (investigational)` (`report_library.MODEL_LABEL`). Library images display as study IDs (e.g. `US-24-10356`) via `UltrasoundSample.study_id`; CC BY attribution remains in the image-library credits, the model-information panel and the PDF.
- **Notice:** every surface keeps one line, "Investigational AI · Not for clinical diagnosis". No accuracy or training claims are made.
- **Teleradiology portal:** `/teleradiology/` lists unsigned second reads ordered Urgent → Priority → Routine (from the AI BI-RADS category). `/teleradiology/reviews/<id>/` shows the study with AI overlay, the full AI report and the referral context, plus a structured sign-off: concordance (agree / partially agree / disagree), final BI-RADS, findings, impression, recommendation and a signature. "Start from AI-drafted wording" fills editable text. Signing moves a pending case to *Specialist reviewed*, records `SPECIALIST_REVIEW_SIGNED`, and shows the signed read on the case, the clinician review and the PDF. Specialist reviewers sign for their facilities; in demo/pilot workspaces the facility user can also act as teleradiologist, so one tester can experience both sides. Reviewer-only accounts land on the queue after login. Run `python manage.py migrate` for the new review fields (migration `workflow/0006`).
- **Predefined specialist text** is no longer shown as a specialist response. The panel shows the signed review, an "Awaiting teleradiologist" status, or that no review was requested.
- **Toasts:** success messages appear as floating notifications that dismiss themselves (`static/motion.css`, `static/motion.js`).

### Simulated teleradiologist (pilot workspaces)
Until radiologists are onboarded, second reads in demo/pilot workspaces (`Facility.is_demo`) are signed automatically. When a review is requested (automatically for AI confidence below 70%, or by the clinician), the case shows a live tracker (Queued → Radiologist assigned → Reading → Signed) that polls `/teleradiology/reviews/<id>/status/`. After 5–10 seconds the image's predefined second read (`report_library.REPORTS[...]['specialist']`) is signed by the fictional, login-disabled account `vanara.teleradiology` ("Dr Adaeze Okonkwo"), the case moves to *Specialist reviewed*, and a toast announces the report. Due reviews also resolve on page load, so nothing gets stuck if the tab was closed. A reviewer who signs manually first takes precedence.
- Every auto-signed review is stored with `SpecialistReview.simulated = True`, and its `SPECIALIST_REVIEW_SIGNED` event carries `simulated: true`. Testers never see this, but exclude these records from any evidence of specialist agreement.
- Configure with `SIMULATED_TELERADIOLOGY=0` (off), `SIMULATED_TR_MIN_SECONDS` and `SIMULATED_TR_MAX_SECONDS`. It never runs for non-demo facilities. Run `python manage.py migrate` (migration `workflow/0007`).
