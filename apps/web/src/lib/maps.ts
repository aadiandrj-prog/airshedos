/** One Maps JavaScript load per page; only a dedicated, browser-restricted key. */
declare global {
  interface Window {
    airshedosMapReady?: () => void;
    gm_authFailure?: () => void;
  }
}
let loading: Promise<void> | undefined;
export const MAP_FAILURE = "airshedos-map-failure";
export async function loadMaps() {
  if (typeof google !== "undefined" && google.maps?.Map) return;
  if (!loading) {
    loading = new Promise<void>((resolve, reject) => {
      const key = process.env.NEXT_PUBLIC_GOOGLE_MAPS_BROWSER_KEY;
      if (!key) { reject(new Error("Map not configured")); return; }
      let settled = false;
      const fail = () => {
        window.dispatchEvent(new Event(MAP_FAILURE));
        if (!settled) { settled = true; clearTimeout(timer); reject(new Error("Map unavailable")); }
      };
      const timer = window.setTimeout(fail, 12000);
      window.gm_authFailure = fail;
      window.airshedosMapReady = () => {
        if (!settled) { settled = true; clearTimeout(timer); resolve(); }
      };
      const script = document.createElement("script");
      script.id = "airshedos-google-maps";
      script.async = true;
      script.referrerPolicy = "strict-origin-when-cross-origin";
      script.src = `https://maps.googleapis.com/maps/api/js?${new URLSearchParams({
        key, loading: "async", callback: "airshedosMapReady", v: "weekly", libraries: "marker",
      })}`;
      script.onerror = fail;
      document.head.append(script);
    });
  }
  await loading;
}
