import { createRequire } from 'node:module';
import { existsSync } from 'node:fs';

const require = createRequire(import.meta.url);

const assets = [
  'leaflet/dist/images/marker-icon.png',
  'leaflet/dist/images/marker-icon-2x.png',
  'leaflet/dist/images/marker-shadow.png',
];

const missing = [];

for (const asset of assets) {
  try {
    const resolved = require.resolve(asset);
    if (!existsSync(resolved)) {
      missing.push(asset);
    }
  } catch {
    missing.push(asset);
  }
}

if (missing.length > 0) {
  console.error('Missing required Leaflet marker assets:');
  for (const asset of missing) {
    console.error(`- ${asset}`);
  }
  console.error('Run `npm install` in web-interface to restore dependencies.');
  process.exit(1);
}

console.log('Leaflet marker assets verified.');
