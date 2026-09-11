import * as THREE from 'three';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import * as fs from 'fs';

const files = ['../suifu-island_96.glb', '../suifu-island_96_lite.glb', '../suifu-island_192_lite.glb'];
for (const f of files) {
  const buf = fs.readFileSync(f);
  const ab = buf.buffer.slice(buf.byteOffset, buf.byteOffset + buf.byteLength);
  await new Promise((res, rej) => {
    new GLTFLoader().parse(ab as unknown as ArrayBuffer, '', (gltf: any) => {
      let meshes = 0, verts = 0, mn = new THREE.Vector3(1e9,1e9,1e9), mx = new THREE.Vector3(-1e9,-1e9,-1e9);
      gltf.scene.updateMatrixWorld(true);
      gltf.scene.traverse((o: any) => { if (o.isMesh) { meshes++; const c = o.geometry.getAttribute('position'); verts += c.count; const b = new THREE.Box3().setFromObject(o); b.min.toArray(mn) && 0; mn.min(b.min); mx.max(b.max); } });
      console.log(`${f.split('/').pop()}: OK meshes=${meshes} verts=${verts} bounds=[${mn.toArray().map(v=>v.toFixed(0))} -> ${mx.toArray().map(v=>v.toFixed(0))}] scene=${gltf.scene.name}`);
      res(null);
    }, (err: any) => { console.error(`${f}: PARSE FAIL`, err); rej(err); });
  });
}
