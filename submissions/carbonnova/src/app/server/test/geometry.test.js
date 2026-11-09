import { describe, test } from 'node:test';
import assert from 'node:assert/strict';
import { measureParcel } from '../lib/geometry.js';

describe('parcel geometry', () => {
  test('measures a small square in square metres, hectares and acres', () => {
    const result = measureParcel([[0, 0], [0, 0.01], [0.01, 0.01], [0.01, 0]]);
    assert.ok(result.area_m2 > 1_000_000 && result.area_m2 < 1_300_000);
    assert.ok(result.area_hectares > 100 && result.area_hectares < 130);
    assert.ok(result.area_acres > 240 && result.area_acres < 320);
  });

  test('rejects too few, invalid, duplicate and self-intersecting vertices', () => {
    assert.throws(() => measureParcel([[1, 1], [2, 2]]), /between 3 and 500/);
    assert.throws(() => measureParcel([[0, 0], [0, 1], [91, 2]]), /valid latitude\/longitude/);
    assert.throws(() => measureParcel([[0, 0], [0, 1], [0, 0]]), /3 distinct/);
    assert.throws(() => measureParcel([[0, 0], [1, 1], [0, 1], [1, 0]]), /edges cross/);
  });
});
