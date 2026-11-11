# AirshedOS

**Report local pollution. Review the evidence. Keep the reporter informed.**

AirshedOS connects a resident reporting experience with a private, unit-scoped reviewer workspace. It is a prototype for controlled demonstrations and pilot preparation; no government partnership or official dispatch is established.

## The application

- **Residents:** sign in, submit a text report with an optional approved private image, track their own reports and respond to reviewer questions.
- **Reviewers:** work on cases assigned to their approved unit, inspect evidence, record internal notes and follow-up, and deliberately publish separate reporter-visible updates.
- **Durable processing:** PostgreSQL saves a report and its job atomically. A separate worker handles bounded retries and freezes evidence versions without changing human decisions.
- **Privacy and access:** backend ownership/unit checks protect every case, export and media read. Internal notes and reporter updates use separate response models. Expiry/deletion and recovery safeguards apply to retained content.

Gemini and environmental sources are advisory and optional. A provider failure does not erase an accepted report. Unknown capture time remains unknown; text-only reports are valid. Google forecast values are separate window peaks, not additional corroboration votes. The isolated forecasting research remains `MODEL_NOT_ACCEPTED`.

## Deployment and demo status

- Website: [airshedos.vercel.app](https://airshedos.vercel.app) — the new interface and configured sign-in are deployed on the clean production URL.
- Pilot API: [airshedos-pilot-api.onrender.com](https://airshedos-pilot-api.onrender.com/health).
- Neon: PostgreSQL 18 with the application schema and restricted service accounts.
- Preview sign-in was confirmed by the owner after correcting the session database variable’s environment scope. Production redirects to the correct Auth0 tenant and callback; a complete production resident/reviewer rehearsal remains pending.
- The hosted connection currently supports text-only setup. Private image storage, an approved reviewer unit and worker/cleanup operation remain deployment dependencies.

For a hackathon demonstration, the processing worker and cleanup can be prepared to run on the presenter's laptop with hosted frontend/API/database services. This arrangement still needs a full rehearsal; it is not an independently running hosted pilot. An isolated local synthetic browser harness already verifies both journeys without paid provider calls. The previous command-center demo and its records are separate historical material.

## Development

The monorepo uses Next.js/React/TypeScript in `apps/web` and FastAPI/Pydantic/SQLAlchemy in `apps/api`. PostgreSQL migrations are explicit operator tasks; application startup does not migrate or bootstrap access.

```sh
# Frontend
cd apps/web
npm ci
npm run dev
```

For backend installation, the guarded disposable PostgreSQL target and synthetic verification, follow [development instructions](docs/DEVELOPMENT.md). Keep hosted credentials in private service settings. Never run database-resetting tests against Neon.

## Documentation

| Topic | Guide |
|---|---|
| Current configuration, limitations and checks | [Deployment status](docs/seva/DEPLOYMENT_STATUS.md) |
| Hosting and clean/custom domains | [Hosting guide](docs/HOSTING.md) |
| Release, recovery and controlled local demonstration | [Pilot runbook](docs/seva/PILOT_RUNBOOK.md) |
| Architecture | [System architecture](docs/ARCHITECTURE.md) |
| Development and tests | [Developer guide](docs/DEVELOPMENT.md) |
| Resident/reviewer implementation | [Implementation status](docs/seva/PHASE_STATUS.md) |
| Source semantics and scientific limits | [Data sources](docs/DATA_SOURCES.md), [rules](docs/CORROBORATION_RULES.md), [forecasting](docs/FORECASTING.md) |
| Historical prototype documentation | [Archive](docs/archive/prototype/README.md) |

There is no public individual-case feed, self-selected reviewer signup, automatic legal finding or real inter-agency transport. Demonstrations must distinguish synthetic inputs, unavailable sources and actual provider results.
