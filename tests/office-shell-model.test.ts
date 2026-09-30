import test from 'node:test';
import assert from 'node:assert/strict';
import { openModel } from './glb';

const shell = openModel('office_shell');

test('the Blender office shell has the material and object names painted by office.ts', () => {
  assert.deepEqual(shell.materials().sort(), ['Inside', 'Outside', 'Trim']);
  assert.deepEqual(
    shell.nodes.map((node) => node.name).sort(),
    ['office_shell_inside', 'office_shell_outside', 'office_shell_trim'],
  );
});

test('the Blender shell matches the office footprint and ceiling height', () => {
  const bounds = shell.bounds();
  const near = (actual: number, expected: number) => assert.ok(Math.abs(actual - expected) < 0.01, `${actual} is near ${expected}`);
  near(bounds.min.x, -18.34);
  near(bounds.max.x, 18.34);
  near(bounds.min.y, 0);
  near(bounds.max.y, 6.8);
  near(bounds.min.z, -13.34);
  near(bounds.max.z, 13.34);
  assert.ok(shell.triangles() < 9000, `${shell.triangles()} triangles`);
});