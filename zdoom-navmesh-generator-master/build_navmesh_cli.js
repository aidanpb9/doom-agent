// CLI wrapper to build a navmesh with zdoom-navmesh-generator.
// Usage: node build_navmesh_cli.js <MAPNAME> <WAD_PATH> [OUT_DIR] [CONFIG_DIR]

const fs = require('fs');
const path = require('path');
const strip = require('strip-comments');
const build = require('./build');
const configTemplate = require('./src/lib/ConfigTemplate');

function parseConfig() {
  try {
    return JSON.parse(strip(configTemplate));
  } catch (err) {
    throw new Error(`Failed to parse config template: ${err.message}`);
  }
}

async function main() {
  const mapName = (process.argv[2] || '').toUpperCase();
  const wadPath = process.argv[3];
  const outDir = process.argv[4] || path.resolve(process.cwd(), 'models', 'nav');
  const configDir = process.argv[5] || path.resolve(__dirname, 'configs');

  if (!mapName || !wadPath) {
    console.error('Usage: node build_navmesh_cli.js <MAPNAME> <WAD_PATH> [OUT_DIR] [CONFIG_DIR]');
    process.exit(2);
  }

  if (!fs.existsSync(wadPath)) {
    console.error(`WAD not found: ${wadPath}`);
    process.exit(3);
  }

  fs.mkdirSync(outDir, { recursive: true });
  fs.mkdirSync(configDir, { recursive: true });

  let wadDir = path.dirname(wadPath);
  const wadBase = path.parse(wadPath).name.toUpperCase();

  if (wadBase !== mapName) {
    const tempDir = path.resolve(__dirname, '.autogen_wads');
    fs.mkdirSync(tempDir, { recursive: true });
    const dest = path.join(tempDir, `${mapName}.wad`);
    let shouldCopy = true;
    if (fs.existsSync(dest)) {
      try {
        const srcStat = fs.statSync(wadPath);
        const dstStat = fs.statSync(dest);
        shouldCopy = srcStat.mtimeMs > dstStat.mtimeMs || srcStat.size !== dstStat.size;
      } catch (err) {
        shouldCopy = true;
      }
    }
    if (shouldCopy) {
      fs.copyFileSync(wadPath, dest);
    }
    wadDir = tempDir;
  }

  const config = parseConfig();
  const masterConfig = {
    wadspath: wadDir,
    configspath: configDir,
    meshpath: outDir,
  };

  await build.buildNavMesh(mapName, config, masterConfig);

  const outJson = path.join(outDir, `${mapName}.json`);
  if (!fs.existsSync(outJson)) {
    throw new Error(`Navmesh json not found at ${outJson}`);
  }

  console.log(outJson);
}

main().catch(err => {
  console.error(err && err.message ? err.message : err);
  process.exit(1);
});
