// Explicit test-process preload; never imported or selected by application code.
// The SDK requires a DNS hostname. Route that one synthetic host to our local HTTPS
// fixture while retaining normal CA verification. All other fetches are unchanged.
const issuer = process.env.TEST_OIDC_ISSUER;
const target = process.env.TEST_OIDC_TRANSPORT;
if (issuer !== "https://resident-fixture.invalid/" || !target?.startsWith("https://127.0.0.1:")) throw new Error("Synthetic transport required");
const networkFetch = globalThis.fetch;
globalThis.fetch = (input, init) => {
  const url = new URL(input instanceof Request ? input.url : String(input));
  if (url.origin !== new URL(issuer).origin) return networkFetch(input, init);
  const redirected = new URL(url.pathname + url.search, target);
  return networkFetch(input instanceof Request ? new Request(redirected, input) : redirected, init);
};
