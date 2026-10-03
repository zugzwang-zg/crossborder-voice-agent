import assert from 'node:assert/strict';
import { createRequire } from 'node:module';
import test from 'node:test';
const require = createRequire(import.meta.url);
const braces = require('../vendor/braces');

test('bounded braces preserves ordinary glob and range behavior', () => {
  assert.deepEqual(braces('src/{a,b}.js', { expand: true }), ['src/a.js', 'src/b.js']);
  assert.deepEqual(braces.expand('{1..3}'), ['1', '2', '3']);
  assert.equal(braces.compile('src/{a,b}.js'), 'src/(a|b).js');
  const ast = braces.parse('{a,{b,c}}');
  assert.equal(braces.stringify(ast), '{a,{b,c}}');
  assert.deepEqual(braces.expand(ast), ['a', 'b', 'c']);
});

test('all string entrypoints reject deeply nested braces and parentheses', () => {
  for (const [open, close] of [['{', '}'], ['(', ')']]) {
    const input = open.repeat(10000) + 'a,b' + close.repeat(10000);
    for (const method of [braces, braces.create, braces.parse, braces.compile, braces.expand, braces.stringify]) {
      assert.throws(() => method(input), { name: 'SyntaxError' });
    }
  }
  assert.doesNotThrow(() => braces.compile('{'.repeat(32) + 'a,b' + '}'.repeat(32)));
});

test('AST entrypoints reject excessive depth and cycles, including direct library calls', () => {
  let ast = { type: 'text', value: 'a' };
  for (let i = 0; i < 10000; i++) ast = { type: 'root', nodes: [ast] };
  const cycle = { type: 'root', nodes: [] };
  cycle.nodes.push(cycle);
  for (const method of ['compile', 'expand', 'stringify']) {
    for (const fn of [braces[method], require('../vendor/braces/lib/' + method)]) {
      assert.throws(() => fn(ast), { name: 'SyntaxError' });
      assert.throws(() => fn(cycle), { name: 'SyntaxError' });
    }
  }
});
