import { identityRuntime } from "../../server/auth";
import { safeReturnTo } from "../../server/settings";
import { Shell } from "../../server/route-shell";

export const dynamic = "force-dynamic";
export default async function SignIn({ searchParams }: { searchParams: Promise<Record<string, string>> }) {
  const params = await searchParams;
  let configured = false;
  try { configured = !!identityRuntime(); } catch { /* Honest unavailable state. */ }
  return <Shell title="Sign in to AirshedOS">
    {params.status === "failed" && <p role="alert">Sign-in could not complete. Please try again.</p>}
    {params.status === "signed-out" && <p role="status">You are signed out of this application.</p>}
    <p className="sign-in-description">Residents can access their own reports. Authority access requires an approved unit membership.</p>
    {configured ? <a className="pilot-button" href={`/auth/login?returnTo=${encodeURIComponent(safeReturnTo(params.returnTo))}`}>Continue to secure sign-in</a>
      : <p role="status">Managed sign-in is not configured in this deployment.</p>}
  </Shell>;
}
