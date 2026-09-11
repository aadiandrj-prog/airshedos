# Sanitized provider-shaped fixtures

These are hand-authored test examples shaped after official Google/NASA schemas, not recorded live observations. They contain no credentials or user data. Dates and values must never be presented as current observations in the running application. Only automated tests read these files.

`sentinel5p.json` is a synthetic reduced Earth Engine response for three products, with clearly synthetic scene/product IDs. It is not a live observation or a raw credential-bearing response. It tests native units, timestamps, QA and normalization only.
