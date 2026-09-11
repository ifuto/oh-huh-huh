// Builds scaled / lite GLB variants of the island, mirroring IslandViewer.exportGLB().
import * as THREE from 'three';
import { GLTFExporter } from 'three/addons/exporters/GLTFExporter.js';
import * as fs from 'fs';
import { createIsland as createFull } from './island';
import { createIsland as createSmall } from './island_small';

(globalThis as any).FileReader = class {
  readAsArrayBuffer(blob: Blob) {
    blob.arrayBuffer().then(buf => { (this as any).result = buf; (this as any).onloadend?.({ target: { result: buf } }); });
  }
};

async function build(name: string, create: () => ReturnType<typeof createFull>, target: number, out: string) {
  const island = create();
  const clone = island.root.clone(true);
  clone.traverse(object => { object.visible = true; });
  const bounds = new THREE.Box3().setFromObject(clone);
  const size = bounds.getSize(new THREE.Vector3());
  const center = bounds.getCenter(new THREE.Vector3());
  clone.scale.set(target / size.x, target / size.x, target / size.z); // proportional Y
  clone.position.set(-center.x * clone.scale.x, -bounds.min.y * clone.scale.y, -center.z * clone.scale.z);
  clone.userData = { ...clone.userData, unit: '1 unit = 1 block', dimensions: `${target} x ${target} blocks (X/Z)`, upAxis: '+Y', origin: 'Bottom center', version: '1.1-variant-' + name };
  clone.updateMatrixWorld(true);
  const scene = new THREE.Scene();
  scene.name = 'Suifu_Island_' + target + 'x' + target;
  scene.add(clone);
  const data = await new GLTFExporter().parseAsync(scene, { binary: true, onlyVisible: false });
  if (!(data instanceof ArrayBuffer)) throw new Error('export failed');
  fs.writeFileSync('../' + out, Buffer.from(data));
  let tris = 0;
  clone.traverse((o: any) => { if (o.isMesh) tris += o.geometry.getAttribute('position').count / 3; });
  console.log(`${out}: ${(data.byteLength/1024/1024).toFixed(2)} MB, ~${Math.round(tris)} tris`);
}

await build('full-96', () => createFull(), 96, 'suifu-island_96.glb');
await build('lite-96', () => createSmall(), 96, 'suifu-island_96_lite.glb');
await build('lite-192', () => createSmall(), 192, 'suifu-island_192_lite.glb');
