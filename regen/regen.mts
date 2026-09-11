// Regenerates suifu-island_1000x1000.glb headlessly, mirroring IslandViewer.exportGLB() exactly.
import * as THREE from 'three';
import { GLTFExporter } from 'three/addons/exporters/GLTFExporter.js';
import * as fs from 'fs';
import { createIsland } from './island';

// Minimal FileReader shim for Node (GLTFExporter binary path uses readAsArrayBuffer)
(globalThis as any).FileReader = class {
  readAsArrayBuffer(blob: Blob) {
    blob.arrayBuffer().then(buf => {
      (this as any).result = buf;
      (this as any).onloadend?.({ target: { result: buf } });
    });
  }
};

const island = createIsland();

const clone = island.root.clone(true);
clone.traverse(object => { object.visible = true; });

const bounds = new THREE.Box3().setFromObject(clone);
const size = bounds.getSize(new THREE.Vector3());
const center = bounds.getCenter(new THREE.Vector3());
clone.scale.set(1000 / size.x, 10, 1000 / size.z);
clone.position.set(-center.x * clone.scale.x, -bounds.min.y * 10, -center.z * clone.scale.z);
clone.userData = { ...clone.userData, unit: '1 unit = 1 block', dimensions: '1000 x 1000 blocks (X/Z)', upAxis: '+Y', origin: 'Bottom center', version: '1.0' };
clone.updateMatrixWorld(true);

const exportScene = new THREE.Scene();
exportScene.name = 'Suifu_Island_1000x1000';
exportScene.add(clone);

const data = await new GLTFExporter().parseAsync(exportScene, { binary: true, onlyVisible: false });
if (!(data instanceof ArrayBuffer)) throw new Error('GLB export failed');
fs.writeFileSync('../suifu-island_1000x1000.glb', Buffer.from(data));
console.log('written ../suifu-island_1000x1000.glb:', data.byteLength, 'bytes');
