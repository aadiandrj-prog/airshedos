`environment.test.json` is a synthetic normalized response generated from the backend's synthetic provider fixtures. It is intercepted only by Playwright to test the renderer. Its LIVE/CACHED statuses exercise UI states; they are not proof of external connectivity or present-day observations. Screenshots named `mocked` show these test values. Production code never imports this fixture.

`satellite.test.json` is a synthetic normalized satellite context matching the backend contract. Its values, times and synthetic image identifiers are browser-test data only, never production fallback values.
