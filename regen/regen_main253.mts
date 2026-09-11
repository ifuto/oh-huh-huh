import * as THREE from 'three';
import { GLTFExporter } from 'three/addons/exporters/GLTFExporter.js';
import * as fs from 'fs';
import { createIsland } from './island_500';

(globalThis as any).FileReader = class {
  readAsArrayBuffer(blob: Blob) { blob.arrayBuffer().then(buf => { (this as any).result = buf; (this as any).onloadend?.({ target: { result: buf } }); }); }
};

const target = 253; // main path 1.9u * (253/96) ≈ 5.0 blocks wide
const island = createIsland();
const clone = island.root.clone(true);
clone.traverse(o => { o.visible = true; });
const bounds = new THREE.Box3().setFromObject(clone);
const size = bounds.getSize(new THREE.Vector3());
const center = bounds.getCenter(new THREE.Vector3());
clone.scale.set(target / size.x, target / size.x, target / size.z);
clone.position.set(-center.x * clone.scale.x, -bounds.min.y * clone.scale.y, -center.z * clone.scale.z);
clone.userData = { ...clone.userData, dimensions: `${target} x ${target} blocks`, scaleNote: 'paths ≈ 5 blocks' };
clone.updateMatrixWorld(true);
const scene = new THREE.Scene(); scene.name = 'Suifu_Island_main'; scene.add(clone);
const data = await new GLTFExporter().parseAsync(scene, { binary: true, onlyVisible: false });
fs.writeFileSync('../suifu-island_main253.glb', Buffer.from(data as ArrayBuffer));
console.log('written', (data as ArrayBuffer).byteLength, 'bytes');
