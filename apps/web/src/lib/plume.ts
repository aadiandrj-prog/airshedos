/** Educational steady-state ground-level Gaussian point-source scenario, not a forecast. */
export type PlumeScenario = {
  emissionGps: number; windMps: number; windFromDeg: number; heightM: number;
  lateralMPerKm: number; verticalMPerKm: number; sourceEastM: number; sourceNorthM: number;
};
export const DEFAULT_PLUME: PlumeScenario = {
  emissionGps: 1, windMps: 3, windFromDeg: 270, heightM: 40,
  lateralMPerKm: 120, verticalMPerKm: 80, sourceEastM: -1000, sourceNorthM: 0,
};
export const PLUME_EXTENT_M = 3000;
export function scenarioIssue(s: PlumeScenario): string | null {
  if (![s.emissionGps,s.windMps,s.windFromDeg,s.heightM,s.lateralMPerKm,s.verticalMPerKm,s.sourceEastM,s.sourceNorthM].every(Number.isFinite)) return "Scenario inputs must be finite numbers.";
  if (s.windMps < 1) return "Calm or low wind: this steady-state scenario is unavailable below 1 m/s.";
  if (s.windMps > 15 || s.emissionGps < 0 || s.emissionGps > 10 || s.heightM < 10 || s.heightM > 150
      || s.lateralMPerKm < 30 || s.lateralMPerKm > 400 || s.verticalMPerKm < 20 || s.verticalMPerKm > 250
      || s.windFromDeg < 0 || s.windFromDeg >= 360 || Math.abs(s.sourceEastM) > 2000 || Math.abs(s.sourceNorthM) > 2000)
    return "Scenario inputs are outside the supported illustrative range.";
  return null;
}
export function windFrame(s: PlumeScenario, eastM: number, northM: number) {
  const toward = (s.windFromDeg + 180) * Math.PI / 180;
  const east = eastM - s.sourceEastM, north = northM - s.sourceNorthM;
  return { downwindM: east * Math.sin(toward) + north * Math.cos(toward), crosswindM: -east * Math.cos(toward) + north * Math.sin(toward) };
}
/** µg/m³ scenario increment at z=0, with ground reflection; σy,z are assumed linear in x. */
export function gaussianGround(s: PlumeScenario, downwindM: number, crosswindM: number): number | null {
  if (scenarioIssue(s) || !Number.isFinite(downwindM) || !Number.isFinite(crosswindM)) return null;
  if (downwindM < -1e-9) return 0; // Zero upwind is a model assumption, not observed clean air.
  if (downwindM < 50) return null; // Excluded near-source region; do not paint it as zero.
  const sy = s.lateralMPerKm * downwindM / 1000, sz = s.verticalMPerKm * downwindM / 1000;
  return 1e6 * s.emissionGps / (Math.PI * s.windMps * sy * sz)
    * Math.exp(-0.5 * ((crosswindM / sy) ** 2 + (s.heightM / sz) ** 2));
}
export function scenarioAt(s: PlumeScenario, eastM: number, northM: number) {
  const point = windFrame(s, eastM, northM);
  return gaussianGround(s, point.downwindM, point.crosswindM);
}
export function offsetPoint(latitude: number, longitude: number, eastM: number, northM: number) {
  const distance = Math.hypot(eastM, northM) / 6371008.8;
  const bearing = Math.atan2(eastM, northM), phi = latitude * Math.PI / 180, lambda = longitude * Math.PI / 180;
  const lat = Math.asin(Math.sin(phi) * Math.cos(distance) + Math.cos(phi) * Math.sin(distance) * Math.cos(bearing));
  const lng = lambda + Math.atan2(Math.sin(bearing) * Math.sin(distance) * Math.cos(phi), Math.cos(distance) - Math.sin(phi) * Math.sin(lat));
  return { lat: lat * 180 / Math.PI, lng: ((lng * 180 / Math.PI + 540) % 360) - 180 };
}
export function plumeColor(value: number | null): [number, number, number, number] {
  if (value == null || value <= 0.01) return [0, 0, 0, 0];
  const t = Math.min(1, Math.log1p(value) / Math.log1p(1000));
  return [Math.round(30 + 205 * t), Math.round(160 - 95 * t), Math.round(215 - 45 * t), Math.round(210 * Math.sqrt(t))];
}
/** Only our generated scenario pixels; never screenshots or copied Google map imagery. */
export function drawPlume(canvas: HTMLCanvasElement, s: PlumeScenario, size = 144) {
  canvas.width = size; canvas.height = size;
  const ctx = canvas.getContext("2d"); if (!ctx) return;
  ctx.clearRect(0, 0, size, size); if (scenarioIssue(s)) return;
  const pixels = ctx.createImageData(size, size);
  for (let row = 0; row < size; row++) for (let col = 0; col < size; col++) {
    const east = ((col + 0.5) / size * 2 - 1) * PLUME_EXTENT_M;
    const north = (1 - (row + 0.5) / size * 2) * PLUME_EXTENT_M;
    pixels.data.set(plumeColor(scenarioAt(s, east, north)), (row * size + col) * 4);
  }
  ctx.putImageData(pixels, 0, 0);
}
