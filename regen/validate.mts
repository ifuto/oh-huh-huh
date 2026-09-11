import * as THREE from 'three';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import * as fs from 'fs';

const buf = fs.readFileSync('../suifu-island_1000x1000.glb');
const ab = buf.buffer.slice(buf.byteOffset, buf.byteOffset + buf.byteLength);
const loader = new GLTFLoader();
loader.parse(ab as unknown as ArrayBuffer, '', (gltf) => {
  let meshes = 0, verts = 0, mats = new Set<string>();
  gltf.scene.traverse((o: any) => {
    if (o.isMesh) { meshes++; verts += o.geometry.getAttribute('position').count; if (o.material?.name) mats.add(o.material.name); }
  });
  console.log(`GLTFLoader parse OK: scene="${gltf.scene.name}" meshes=${meshes} vertices=${verts} materials=${mats.size}`);
  console.log('root children:', gltf.scene.children.map((c: any) => c.name).join(', '));
}, (err) => { console.error('GLTFLoader parse FAILED:', err); process.exit(1); });
