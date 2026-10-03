'use strict';

// Bound the recursive upstream walkers without following AST parent/prev links.
const MAX_DEPTH = 128;
const assertSafeAst = ast => {
  const active = new Set();
  const stack = [{ node: ast, depth: 0, exit: false }];
  let visited = 0;
  while (stack.length) {
    const { node, depth, exit } = stack.pop();
    if (!node || typeof node !== 'object') continue;
    if (exit) { active.delete(node); continue; }
    if (depth > MAX_DEPTH || active.has(node) || ++visited > 100000) {
      throw new SyntaxError('Brace AST exceeds safe depth/size or contains a cycle');
    }
    active.add(node);
    stack.push({ node, depth, exit: true });
    if (Array.isArray(node.nodes)) {
      for (let i = node.nodes.length - 1; i >= 0; i--) {
        stack.push({ node: node.nodes[i], depth: depth + 1, exit: false });
      }
    }
  }
};
module.exports = { MAX_DEPTH, assertSafeAst };
