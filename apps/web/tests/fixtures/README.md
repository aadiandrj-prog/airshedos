# Synthetic overview fixture

explore-synthetic.json is generated from mocked Google-shaped responses and synthetic FIRMS CSV
by test_explore.py, never a live source call. It contains no accounts, reports, keys or photos.
Browser tests replace its expiry with a short test window and intercept only the public
same-origin endpoint. Captures, when requested, are labelled synthetic verification data.
