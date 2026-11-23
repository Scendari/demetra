// Extrait les données du prototype (sources/catalogue/catalogue-runs-data.js) en JSON.
// Usage : node scripts/dump_catalogue.mjs sources/catalogue/catalogue-runs-data.js core/demo/catalogue_lancelot.json
import fs from "node:fs";

const source = fs.readFileSync(process.argv[2], "utf8");
const runCatalog = new Function(source + "; return runCatalog;")();
fs.writeFileSync(process.argv[3], JSON.stringify(runCatalog));
console.log(`${runCatalog.cases.length} cas, version ${runCatalog.version}`);
