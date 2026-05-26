#!/usr/bin/env node
const acorn = require('./node_modules/acorn');
const fs = require('fs');
const src = fs.readFileSync('/dev/stdin', 'utf8');
const ast = acorn.parse(src, { ecmaVersion: 2020, sourceType: 'script' });
console.log(JSON.stringify(ast, null, 2));
