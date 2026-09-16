import type { Page } from "@playwright/test";

/** Mock only the Google SDK boundary; production map and selection code runs unchanged. */
export async function mockMaps(page: Page) {
  await page.route(/https:\/\/([^/]+\.)?(googleapis|gstatic|google)\.com\/.*(maps|khms|vt)/, (r) => r.abort());
  await page.addInitScript(() => {
    class MapMock {
      element: HTMLElement;
      constructor(element: HTMLElement) { this.element = element; element.dataset.mockMap = "true"; }
      addListener(_event: string, callback: () => void) { const id = setTimeout(callback, 10); return { remove: () => clearTimeout(id) }; }
      fitBounds(bounds: { points: unknown[] }) { this.element.dataset.boundsCount = String(bounds.points.length); }
      setCenter(point: unknown) { this.element.dataset.center = JSON.stringify(point); }
      setZoom(zoom: number) { this.element.dataset.zoom = String(zoom); }
    }
    class MarkerMock {
      element = document.createElement("button");
      constructor(options: { map: MapMock; title: string }) {
        this.element.setAttribute("aria-label", options.title);
        this.element.dataset.mockMarker = "true";
        options.map.element.append(this.element);
      }
      set map(value: unknown) { if (!value) this.element.remove(); }
      append(child: HTMLElement) { this.element.append(child); }
      addEventListener(_name: string, callback: EventListener) { this.element.addEventListener("click", callback); }
      setAttribute(name: string, value: string) { this.element.setAttribute(name, value); }
      remove() { this.element.remove(); }
    }
    class BoundsMock { points: unknown[] = []; extend(point: unknown) { this.points.push(point); } }
    const maps = { Map: MapMock, LatLngBounds: BoundsMock, marker: { AdvancedMarkerElement: MarkerMock }, importLibrary: async () => { if ((window as Window & { mockMapsFailure?: boolean }).mockMapsFailure) throw new Error("Synthetic SDK failure"); return maps; } };
    Object.assign(window, { google: { maps } });
  });
}
