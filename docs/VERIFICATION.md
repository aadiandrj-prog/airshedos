# Phase 1A verification

Verified locally on 10 September 2026. Phase 1B was not started.

## Final results

| Check | Result |
| --- | --- |
| Backend `ruff check .` | Passed; no findings |
| Backend `ruff format --check .` | Passed; 7 files already formatted |
| Backend `pytest -q` | **24 passed**, 2 third-party deprecation warnings |
| Export OpenAPI and compare generated contract | Passed; no drift |
| Frontend `npm run generate:api` | Passed; no generated-type drift |
| Frontend `npm run lint` | Passed; zero errors/warnings |
| Frontend `npm run typecheck` | Passed, including route-type generation |
| Frontend `npm run build` | Passed; Next.js 16.3.4 production output |
| Browser `npm run test:e2e` | **3 passed**, using Chromium and the production Docker app |
| Docker build | Both images built successfully with locked dependencies |
| Docker Compose stop / rebuild / start | Passed; both services reached healthy status |
| `/health` | HTTP 200, `{"status":"ok"}` |
| `/ready` | HTTP 200, `{"status":"ready","storage":"in_memory","data_mode":"demo"}` |
| Staged diff whitespace check | Passed |
| Tracked secret-pattern scan | Zero findings; no actual `.env` or credential files tracked |
| npm dependency install audit | Zero reported vulnerabilities |

Backend warnings originate in Starlette's TestClient: its httpx compatibility path and a deprecated AnyIO portal alias. They do not fail tests. npm reports that ESLint 9 is deprecated; the locked version passes the current Next.js rules. These are dependency maintenance notes, not suppressed test failures. The browser runner also reports an environment-only `NO_COLOR`/`FORCE_COLOR` warning.

## Acceptance coverage

1. Started Uvicorn locally and served the API.
2. Started Next.js locally, opened the command center, and built production output.
3. Verified health and readiness via HTTP and backend tests.
4. List and detail return the same fictional incident, including five evidence signals and the six-hour forecast.
5. The browser fetches readiness, list, and incident detail from FastAPI. No incident fixture is present in frontend source.
6. Evidence statuses, citizen confidence (88%), incident confidence (86%), and forecast probability (81%) are visible.
7. Acknowledgment sends a real POST, changes the incident status, and appends an action.
8. Sharing sends a real POST with a target jurisdiction, displays success, and records a simulated action. No external notification occurs.
9. Reload retains actions while the backend process stays running. Restart resets the demo state.
10. Demo/sample labels and field-verification wording are visible. The UI makes no definitive source claim.
11. Backend checks cover missing IDs, invalid share targets/bodies, idempotency, concurrency, copy isolation, CORS, confidence/coordinate bounds, and timezone/availability validation.
12. Browser checks exercise API failure, retry, loading, empty results, and failed mutation behavior.
13. Desktop (1280px) and mobile (390px) screenshots were captured and visually reviewed. Mobile has no horizontal overflow.
14. OpenAPI and generated TypeScript agree; confidence stays 0–1 internally and becomes percentages only in presentation.
15. Docker runs only the API and frontend, with health checks, non-root users, loopback ports, and no credentials.
16. Reviewed source and generated contracts; removed auto-generated agent scaffolding from the repository. Generated Next.js type files, caches, dependencies, and test traces are ignored.
17. README and architecture documentation distinguish current behavior from planned Google integrations.

Browser verification starts against a fresh API for the final acceptance run, so both mutations are exercised. The test is also safe to rerun against an already acknowledged/shared demo session.

## UI artifacts

- [Desktop command center](screenshots/command-center-desktop.png)
- [Mobile command center](screenshots/command-center-mobile.png)

The page has a dark operations header, clear demo notice, compact incident summary, geographic schematic, priority incident details and actions, six-hour risk card, expandable evidence/provenance rows, and a session action record.

## Repository tree

```text
.
├── .env.example
├── .gitignore
├── .github/workflows/ci.yml
├── README.md
├── docker-compose.yml
├── apps
│   ├── api
│   │   ├── .dockerignore
│   │   ├── Dockerfile
│   │   ├── pyproject.toml
│   │   ├── requirements.lock
│   │   ├── requirements-dev.lock
│   │   ├── openapi.json
│   │   ├── app
│   │   │   ├── __init__.py
│   │   │   ├── main.py
│   │   │   ├── models.py
│   │   │   ├── fixtures.py
│   │   │   └── repository.py
│   │   ├── scripts/export_openapi.py
│   │   └── tests/test_api.py
│   └── web
│       ├── .dockerignore
│       ├── Dockerfile
│       ├── package.json
│       ├── package-lock.json
│       ├── next.config.ts
│       ├── tsconfig.json
│       ├── eslint.config.mjs
│       ├── playwright.config.ts
│       ├── e2e/command-center.spec.ts
│       └── src
│           ├── app
│           │   ├── layout.tsx
│           │   ├── page.tsx
│           │   └── globals.css
│           ├── components/operations-pane.tsx
│           └── lib
│               ├── api.ts
│               └── api-schema.d.ts
└── docs
    ├── ARCHITECTURE.md
    ├── VERIFICATION.md
    └── screenshots
        ├── command-center-desktop.png
        └── command-center-mobile.png
```

Generated local artifacts (`.venv`, `node_modules`, `.next`, `next-env.d.ts`, test reports) are intentionally excluded from this source tree.
