// Summarise a JSON number array using Node's standard library only.
const fs = require('node:fs');

const { numbers } = JSON.parse(fs.readFileSync(0, 'utf8'));
const count = numbers.length;
const total = numbers.reduce((sum, number) => sum + number, 0);
console.log(JSON.stringify({
  count,
  total,
  min: count ? Math.min(...numbers) : null,
  max: count ? Math.max(...numbers) : null,
  mean: count ? total / count : null,
}));
