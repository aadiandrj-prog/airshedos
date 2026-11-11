import test from "node:test";
import assert from "node:assert/strict";
import { DEFAULT_PLUME as base, gaussianGround, offsetPoint, plumeColor, scenarioAt, scenarioIssue, windFrame } from "../src/lib/plume";
const near = (actual: number, expected: number, tolerance = 1e-9) => assert(Math.abs(actual - expected) < tolerance, `${actual} != ${expected}`);
test("ground reflection and g/s to microgram units match an independent closed-form example", () => {
  // At x=1000m, σy=120m, σz=80m and H=40m. Ground reflection doubles the vertical term.
  const expected = 1e6 / (Math.PI * 3 * 120 * 80) * Math.exp(-(40 ** 2) / (2 * 80 ** 2));
  near(gaussianGround(base, 1000, 0)!, expected);
});
test("linear emission, inverse wind, Gaussian symmetry and one-sigma crosswind ratio", () => {
  const centre = gaussianGround(base, 1000, 0)!;
  near(gaussianGround({...base, emissionGps:2},1000,0)!,centre*2);
  near(gaussianGround({...base, windMps:6},1000,0)!,centre/2);
  near(gaussianGround(base,1000,120)!/centre, Math.exp(-0.5));
  near(gaussianGround(base,1000,-120)!,gaussianGround(base,1000,120)!);
  assert.equal(gaussianGround({...base, emissionGps:0},1000,0),0);
});
test("meteorological wind comes FROM: west moves east and north moves south", () => {
  const west={...base,sourceEastM:0,sourceNorthM:0,windFromDeg:270};
  near(windFrame(west,1000,0).downwindM,1000);
  near(scenarioAt(west,1000,0)!,gaussianGround(base,1000,0)!);
  assert.equal(scenarioAt(west,-1000,0),0);
  near(windFrame({...west,windFromDeg:0},0,-1000).downwindM,1000);
  near(windFrame({...west,windFromDeg:90},-1000,0).downwindM,1000);
});
test("calm, non-finite, unsupported and excluded near-field states never fabricate concentrations", () => {
  assert.match(scenarioIssue({...base,windMps:0})!,/unavailable/);
  for (const s of [{...base,windMps:0},{...base,emissionGps:-1},{...base,heightM:NaN}]) assert.equal(gaussianGround(s,1000,0),null);
  assert.equal(gaussianGround(base,25,0),null);
  assert.equal(gaussianGround(base,0,0),null);
  assert.equal(gaussianGround(base,-100,0),0);
  assert.equal(gaussianGround(base,NaN,0),null);
  assert.deepEqual(plumeColor(null),[0,0,0,0]);
  assert(plumeColor(1)[3] < plumeColor(10)[3] && plumeColor(10)[3] < plumeColor(100)[3]);
});
test("local geographic offsets preserve north/east sense and wrap the date line", () => {
  const p=offsetPoint(28.46,77.025,1000,0); assert(p.lng>77.025); near(p.lat,28.46,0.001);
  assert(offsetPoint(28.46,77.025,0,1000).lat>28.46);
  assert(offsetPoint(0,179.999,1000,0).lng<0);
});
