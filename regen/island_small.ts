import * as THREE from 'three';
import { mergeGeometries } from 'three/addons/utils/BufferGeometryUtils.js';

export type LayerKey = 'terrain' | 'architecture' | 'vegetation' | 'water' | 'paths';
export const layerNames: Record<LayerKey, string> = { terrain: '浮島・地形', architecture: '木造建築', vegetation: '木々・植生', water: '湖・滝', paths: '小径・ディテール' };
let seed = 24;
const rand = () => { seed = (seed * 1664525 + 1013904223) >>> 0; return seed / 4294967296; };
export const groundHeight = (x: number, z: number) => 3.5 + 5.2 * Math.exp(-((x + 4) ** 2 / 500 + (z + 27) ** 2 / 200)) + 1.1 * Math.sin(x * .1) * Math.cos(z * .085) + .7 * Math.sin(z * .21 + x * .08);
const radius = (a: number) => 46 + 2.5 * Math.sin(a * 3 + .5) + 1.8 * Math.sin(a * 7) + .8 * Math.cos(a * 13);

export function createIsland() {
  seed = 24;
  const root = new THREE.Group();
  root.name = 'Suifu_Floating_Island';
  root.userData = { title: '翠風の浮島', author: 'ISOLA World Studio', unit: 'Preview: 10 blocks per unit. Export: 1 unit = 1 block.', buildings: 22 };
  const groups = {} as Record<LayerKey, THREE.Group>;
  (Object.keys(layerNames) as LayerKey[]).forEach(key => { const g = new THREE.Group(); g.name = key; groups[key] = g; root.add(g); });
  const materials: Record<string, THREE.MeshStandardMaterial> = {};
  const mat = (name: string, color: string, roughness = .9) => { const m = new THREE.MeshStandardMaterial({ color, roughness, flatShading: true }); materials[name] = m; return m; };
  mat('wood', '#ab7748'); mat('lightwood', '#d8ad72'); mat('timber', '#60432e'); mat('roof', '#78503a'); mat('roof2', '#976443'); mat('glass', '#638b87', .3); mat('window', '#f7d58c'); mat('stone', '#96958a'); mat('path', '#d7c59d'); mat('sand', '#b7b78c'); mat('water', '#67b8b7', .25); mat('waterlight', '#a2d4cb', .25); mat('foam', '#e2efdc'); mat('trunk', '#786046'); mat('leaf1', '#477559'); mat('leaf2', '#658859'); mat('leaf3', '#8da56a'); mat('leaf4', '#375f49'); mat('flower', '#edcaa6'); mat('pink', '#d6adab'); mat('reed', '#a9ad6c');
  const batches = new Map<string, THREE.BufferGeometry[]>();
  const put = (geo: THREE.BufferGeometry, material: string, layer: LayerKey, position = new THREE.Vector3(), rotation = new THREE.Euler(), scale = new THREE.Vector3(1, 1, 1)) => {
    let g = geo.index ? geo.toNonIndexed() : geo.clone();
    if (g.getAttribute('uv')) g.deleteAttribute('uv');
    g.applyMatrix4(new THREE.Matrix4().compose(position, new THREE.Quaternion().setFromEuler(rotation), scale));
    const key = `${layer}:${material}`; if (!batches.has(key)) batches.set(key, []); batches.get(key)!.push(g); geo.dispose();
  };
  const box = (x: number, y: number, z: number, w: number, h: number, d: number, m: string, layer: LayerKey = 'architecture', ry = 0) => put(new THREE.BoxGeometry(w, h, d), m, layer, new THREE.Vector3(x, y, z), new THREE.Euler(0, ry, 0));
  const beam = (a: THREE.Vector3, b: THREE.Vector3, width: number, material: string, layer: LayerKey = 'architecture') => { const length = a.distanceTo(b); const q = new THREE.Quaternion().setFromUnitVectors(new THREE.Vector3(0, 1, 0), b.clone().sub(a).normalize()); put(new THREE.BoxGeometry(width, length, width), material, layer, a.clone().add(b).multiplyScalar(.5), new THREE.Euler().setFromQuaternion(q)); };
  const v = (x: number, y: number, z: number) => new THREE.Vector3(x, y, z);

  // A continuous, triangulated meadow and a closed, hanging rock landmass.
  const N = 64, rings = 16;
  const terrainPositions: number[] = [], terrainColors: number[] = [];
  const grassPalette = ['#8fa875', '#8ca674', '#92ad78', '#86a16d', '#9cb37d', '#819b69'].map(c => new THREE.Color(c));
  const triangle = (arr: number[], colors: number[], a: number[], b: number[], c: number[], color: THREE.Color) => { arr.push(...a, ...b, ...c); for (let i = 0; i < 3; i++) colors.push(color.r, color.g, color.b); };
  const point = (r: number, i: number): number[] => { const a = i / N * Math.PI * 2; const dist = radius(a) * r / rings; const x = Math.cos(a) * dist, z = Math.sin(a) * dist; return [x, groundHeight(x, z), z]; };
  for (let r = 0; r < rings; r++) for (let i = 0; i < N; i++) {
    const a = point(r, i), b = point(r + 1, i), c = point(r + 1, i + 1), d = point(r, i + 1);
    const color = grassPalette[Math.floor(rand() * grassPalette.length)];
    triangle(terrainPositions, terrainColors, a, c, b, color); if (r > 0) triangle(terrainPositions, terrainColors, a, d, c, color);
  }
  const coloredMesh = (positions: number[], colors: number[], name: string) => { const geo = new THREE.BufferGeometry(); geo.setAttribute('position', new THREE.Float32BufferAttribute(positions, 3)); geo.setAttribute('color', new THREE.Float32BufferAttribute(colors, 3)); geo.computeVertexNormals(); const mesh = new THREE.Mesh(geo, new THREE.MeshStandardMaterial({ vertexColors: true, flatShading: true, roughness: 1 })); mesh.name = name; mesh.castShadow = true; mesh.receiveShadow = true; groups.terrain.add(mesh); };
  coloredMesh(terrainPositions, terrainColors, 'Meadow_surface');
  const rockPositions: number[] = [], rockColors: number[] = [];
  const rockPalette = ['#85877a', '#72776c', '#929181', '#666f65', '#999585', '#7e8071'].map(c => new THREE.Color(c));
  const rockRings: number[][][] = [];
  const scales = [1, 1.005, .94, .76, .46, .015];
  for (let r = 0; r < 6; r++) { const points: number[][] = []; for (let i = 0; i < N; i++) { const a = i / N * Math.PI * 2; const rr = radius(a) * scales[r] * (r === 0 ? 1 : .965 + rand() * .07); const x = Math.cos(a) * rr, z = Math.sin(a) * rr; const levels = [groundHeight(x, z), -.1, -7, -17, -27, -31]; points.push([x, levels[r] - (r > 0 && r < 5 ? rand() * 5 : 0), z]); } rockRings.push(points); }
  for (let r = 0; r < 5; r++) for (let i = 0; i < N; i++) { const j = (i + 1) % N; const color = rockPalette[Math.floor(rand() * rockPalette.length)].clone(); if (r === 0) color.set(['#768765', '#7e8e6a', '#89916d'][i % 3]); triangle(rockPositions, rockColors, rockRings[r][i], rockRings[r][j], rockRings[r + 1][j], color); triangle(rockPositions, rockColors, rockRings[r][i], rockRings[r + 1][j], rockRings[r + 1][i], color.clone().multiplyScalar(.95 + rand() * .08)); }
  for (let i = 0; i < N; i++) triangle(rockPositions, rockColors, rockRings[5][i], rockRings[5][(i + 1) % N], [0, -32, 0], rockPalette[3]);
  coloredMesh(rockPositions, rockColors, 'Floating_rock_base');

  // Timber chalets: open verandas, framed glazing, gables and individual roof ribs.
  function chalet(x: number, z: number, w: number, d: number, h: number, roofHeight: number, roofMaterial = 'roof', customY?: number) {
    const y = customY ?? groundHeight(x, z);
    box(x, y + .35, z, w + 1.3, .7, d + 1.3, 'stone');
    box(x, y + h / 2 + .7, z, w, h, d, 'lightwood');
    for (let floor = 0; floor <= Math.floor(h / 2.2); floor++) box(x, y + .9 + floor * 2.2, z, w + .18, .18, d + .18, 'timber');
    for (const side of [-1, 1]) {
      for (let a = -w / 2 + .25; a <= w / 2; a += Math.max(2.0, w / 4)) {
        box(x + a, y + h / 2 + .7, z + side * (d / 2 + .04), .17, h, .2, 'timber');
        for (let floor = 0; floor < Math.max(1, Math.floor(h / 2)); floor++) {
          const wy = y + 1.8 + floor * 2.05;
          box(x + a + .64, wy, z + side * (d / 2 + .065), .82, 1.18, .1, floor % 2 ? 'glass' : 'window');
          box(x + a + .64, wy, z + side * (d / 2 + .13), .06, 1.25, .08, 'timber');
          box(x + a + .64, wy, z + side * (d / 2 + .13), .87, .06, .08, 'timber');
        }
      }
      for (let a = -d / 2 + .3; a <= d / 2; a += 2.4) box(x + side * (w / 2 + .02), y + h / 2 + .7, z + a, .17, h, .17, 'timber');
    }
    const eave = y + h + .7, half = w / 2 + .7, depth = d / 2 + .7;
    const roof = new THREE.BufferGeometry();
    roof.setAttribute('position', new THREE.Float32BufferAttribute([
      x-half,eave,z-depth, x,eave+roofHeight,z-depth, x,eave+roofHeight,z+depth,
      x-half,eave,z-depth, x,eave+roofHeight,z+depth, x-half,eave,z+depth,
      x,eave+roofHeight,z-depth, x+half,eave,z-depth, x+half,eave,z+depth,
      x,eave+roofHeight,z-depth, x+half,eave,z+depth, x,eave+roofHeight,z+depth,
      x-half,eave,z-depth, x+half,eave,z-depth, x,eave+roofHeight,z-depth,
      x-half,eave,z+depth, x,eave+roofHeight,z+depth, x+half,eave,z+depth,
    ], 3)); roof.computeVertexNormals(); put(roof, roofMaterial, 'architecture'); materials[roofMaterial].side = THREE.DoubleSide;
    box(x, eave + roofHeight, z, .27, .25, d + 1.8, 'timber');
    for (let dz = -depth; dz <= depth + .1; dz += 1.15) for (const side of [-1, 1]) beam(v(x, eave + roofHeight + .07, z + dz), v(x + side * half, eave + .07, z + dz), .07, 'timber');
    for (const side of [-1, 1]) {
      beam(v(x-w/2, eave, z+side*(d/2+.72)), v(x, eave+roofHeight, z+side*(d/2+.72)), .18, 'lightwood');
      beam(v(x+w/2, eave, z+side*(d/2+.72)), v(x, eave+roofHeight, z+side*(d/2+.72)), .18, 'lightwood');
      box(x, eave + roofHeight * .32, z + side * (d/2+.74), .13, roofHeight * .64, .14, 'timber');
    }
    // Front porch and wooden balustrade.
    box(x, y + .75, z + d / 2 + 1.35, w + 1.2, .22, 2.6, 'wood');
    for (let a = -w/2; a <= w/2+.1; a += 1.7) box(x+a, y+1.4, z+d/2+2.5, .1, 1.3, .1, 'timber');
    box(x, y+2.04, z+d/2+2.5, w+.2, .12, .12, 'lightwood');
    for (let i = 0; i < 3; i++) box(x, y+.18+i*.18, z+d/2+3.15-i*.3, 1.5, .25, .7, 'wood');
    box(x+w*.28, eave+roofHeight*.5, z-d*.23, .8, roofHeight*.85, .9, 'stone');
    return y;
  }
  const mainY = groundHeight(-9, -17);
  chalet(-9, -17, 12, 10, 6.8, 5.7, 'roof', mainY);
  chalet(-19, -17, 8.3, 8.5, 4.6, 4.2, 'roof2', mainY);
  chalet(1, -17, 8.3, 8.5, 4.6, 4.2, 'roof2', mainY);
  box(-9, mainY+.45, -8.8, 31, .7, 6, 'wood');
  for (let i = 0; i < 7; i++) box(-9, mainY-.13-i*.24, -5.5+i*.5, 8+i*.32, .3, .7, 'stone');
  // Clock tower on the great hall.
  box(-9, mainY+12.8, -19, 2.5, 4, 2.6, 'lightwood');
  for (const dx of [-1.15, 1.15]) box(-9+dx, mainY+12.8, -17.65, .18, 4.1, .14, 'timber');
  put(new THREE.ConeGeometry(2.5, 4, 4), 'roof', 'architecture', v(-9, mainY+16.5, -19), new THREE.Euler(0, Math.PI/4, 0));
  put(new THREE.CylinderGeometry(.72, .72, .13, 20), 'window', 'architecture', v(-9, mainY+13.4, -17.61), new THREE.Euler(Math.PI/2,0,0));
  box(-9, mainY+13.6, -17.5, .065, .5, .08, 'timber'); box(-8.8, mainY+13.4, -17.5, .45, .065, .08, 'timber');
  chalet(21, -9, 10, 10, 5.4, 5, 'roof'); chalet(28, -7, 5.3, 7, 3.4, 3.6, 'roof2');
  chalet(-27, 9, 9.5, 7, 4, 4.5, 'roof2');
  chalet(24, 23, 8, 7.2, 4.4, 4.1, 'roof');
  const cottageSpots = [[-31,-16],[-33,-4],[-29,23],[-20,29],[-12,34],[2,32],[11,31],[33,10],[35,0],[27,-24],[17,-29],[6,-33],[-7,-34],[-20,-29],[-37,9],[31,20],[14,20],[15,5]];
  cottageSpots.forEach(([x,z], i) => chalet(x,z,3.1+rand()*1.6,3.3+rand()*1.8,2.1+rand()*.6,2.1+rand()*1.2,i%3===0?'roof2':'roof'));

  // A still turquoise lake, curving stream and a falling ribbon of water.
  const lakeY = 4.38;
  const lakeShape = new THREE.Shape();
  for (let i=0; i<=64; i++) { const a=i/64*Math.PI*2; const r=1+.1*Math.sin(a*3)+.05*Math.cos(a*7); const x=-2+Math.cos(a)*12*r, z=12+Math.sin(a)*9*r; if(i===0) lakeShape.moveTo(x,-z); else lakeShape.lineTo(x,-z); }
  const lakeGeo = new THREE.ShapeGeometry(lakeShape, 48); lakeGeo.rotateX(-Math.PI/2); put(lakeGeo,'water','water',v(0,lakeY,0));
  const stream = new THREE.CatmullRomCurve3([v(-8,lakeY,17),v(-13,4.4,23),v(-11,4.55,29),v(-15,4.1,37),v(-17,3.6,44)]);
  const pts = stream.getPoints(65), streamPos: number[]=[];
  for(let i=0;i<pts.length-1;i++) { const a=pts[i], b=pts[i+1]; const dir=b.clone().sub(a).normalize(), perpendicular=v(-dir.z,0,dir.x).multiplyScalar(1.85); const p=a.clone().add(perpendicular), q=a.clone().sub(perpendicular), r=b.clone().add(perpendicular), s=b.clone().sub(perpendicular); streamPos.push(...p.toArray(),...r.toArray(),...q.toArray(),...q.toArray(),...r.toArray(),...s.toArray()); }
  const streamGeo=new THREE.BufferGeometry(); streamGeo.setAttribute('position',new THREE.Float32BufferAttribute(streamPos,3)); streamGeo.computeVertexNormals(); put(streamGeo,'water','water'); materials.water.side=THREE.DoubleSide;
  for(let i=0;i<8;i++) { const x=-18.7+i*.48; const length=22+rand()*7; box(x,3.9-length/2,44.1+Math.sin(i)*.3,.5,length,.28,i%3===0?'waterlight':'water','water'); }
  for(let i=0;i<10;i++) put(new THREE.IcosahedronGeometry(.5+rand()*.6,0),'foam','water',v(-17+(rand()-.5)*5,-21-rand()*5,44+(rand()-.5)*3),new THREE.Euler(),v(1,.5,1));
  for(let i=0;i<16;i++) { const a=rand()*Math.PI*2; const x=-2+Math.cos(a)*12.3, z=12+Math.sin(a)*9.3; put(new THREE.IcosahedronGeometry(.35+rand()*.65,0),'stone','paths',v(x,Math.max(lakeY,groundHeight(x,z))+.15,z),new THREE.Euler(),v(1.3,.6,1)); }
  for(let i=0;i<16;i++) { const x=-9+rand()*14,z=8+rand()*8; box(x,lakeY+.035,z,.6+rand()*1.6,.015,.055,'waterlight','water'); }
  // Lake jetty.
  for(let i=0;i<17;i++) box(9-i*.36,4.85,13, .31,.18,2.5,'wood','paths');
  for(const x of [3.4,8.8]) for(const z of [11.9,14.1]) box(x,4.3,z,.18,2,.18,'timber','paths');
  box(5,5.05,14.9,2.3,.3,.68,'roof2','paths',.2);

  function path(points: [number,number][], width=1.25) { const curve=new THREE.CatmullRomCurve3(points.map(([x,z])=>v(x,groundHeight(x,z)+.12,z))); const ps=curve.getPoints(80); const positions:number[]=[]; for(let i=0;i<ps.length-1;i++){const a=ps[i],b=ps[i+1], dir=b.clone().sub(a).normalize(), perpendicular=v(-dir.z,0,dir.x).multiplyScalar(width/2); const p=a.clone().add(perpendicular),q=a.clone().sub(perpendicular),r=b.clone().add(perpendicular),s=b.clone().sub(perpendicular); p.y=groundHeight(p.x,p.z)+.16;q.y=groundHeight(q.x,q.z)+.16;r.y=groundHeight(r.x,r.z)+.16;s.y=groundHeight(s.x,s.z)+.16;positions.push(...p.toArray(),...r.toArray(),...q.toArray(),...q.toArray(),...r.toArray(),...s.toArray());} const g=new THREE.BufferGeometry();g.setAttribute('position',new THREE.Float32BufferAttribute(positions,3));g.computeVertexNormals();put(g,'path','paths'); }
  materials.path.side=THREE.DoubleSide;
  path([[-9,-5],[-4,0],[10,1],[18,-1],[23,-3]],1.9);
  path([[-4,0],[-15,3],[-22,10],[-23,20],[-17,26],[-9,27],[0,25],[12,25],[24,29]],1.6);
  path([[10,1],[15,8],[15,16],[12,25]],1.6);
  path([[-22,10],[-31,13],[-33,4],[-31,-10],[-26,-20]],1.2);
  path([[23,-3],[31,5],[31,17],[24,29]],1.2);
  // Footbridge crossing the stream.
  for(let i=0;i<22;i++){const x=-17.5+i*.35,y=5.45+Math.sin(i/21*Math.PI)*.75;box(x,y,27,.3,.18,2.4,'wood','paths');if(i%3===0)for(const side of [-1,1])box(x,y+.65,27+side*1.15,.1,1.3,.1,'timber','paths');if(i>0)for(const side of [-1,1])beam(v(x-.35,5.45+Math.sin((i-1)/21*Math.PI)*.75+1.3,27+side*1.15),v(x,y+1.3,27+side*1.15),.1,'lightwood','paths');}

  // Trees, clustered on the rim while keeping the village and lake readable.
  const noTree = (x:number,z:number) => {
    if(((x+2)/15)**2+((z-12)/12)**2<1)return true;
    if(x>-24&&x<8&&z>-25&&z<-4)return true;
    if(x>13&&x<33&&z>-17&&z<2)return true;
    if(x>-35&&x<-19&&z>2&&z<16)return true;
    if(x>17&&x<31&&z>16&&z<31)return true;
    if(cottageSpots.some(([cx,cz])=>Math.hypot(x-cx,z-cz)<4.2))return true;
    if(z>19&&z<44&&Math.abs(x-(-12-(z-25)*.2))<4)return true;
    return false;
  };
  function tree(x:number,z:number,s:number,pine:boolean) {const y=groundHeight(x,z);put(new THREE.CylinderGeometry(.13*s,.22*s,2.8*s,5),'trunk','vegetation',v(x,y+1.4*s,z));if(pine){for(let j=0;j<3;j++)put(new THREE.ConeGeometry((1.65-j*.33)*s,3*s,7),['leaf1','leaf4','leaf2'][j],'vegetation',v(x,y+(2.65+j*1.18)*s,z),new THREE.Euler(0,rand()*3,0));}else{for(let j=0;j<3;j++)put(new THREE.IcosahedronGeometry((1.5-j*.15)*s,1),['leaf2','leaf3','leaf1'][Math.floor(rand()*3)],'vegetation',v(x+(j===1?-.65:j===2?.65:0)*s,y+(3+j*.55)*s,z+(j===1?.35:0)),new THREE.Euler(rand(),rand(),rand()),v(1,1.12,1));}}
  let trees=0;
  for(let i=0;i<1300&&trees<105;i++){const x=(rand()-.5)*94,z=(rand()-.5)*94,a=Math.atan2(z,x);if(Math.hypot(x,z)>radius(a)-2||noTree(x,z))continue;if(Math.hypot(x,z)<24&&rand()<.65)continue;tree(x,z,.65+rand()*.8,rand()>.43);trees++;}
  // Rocks, meadow flowers, shrubs and hanging vines at the exposed cliff.
  for(let i=0;i<50;i++){const a=rand()*Math.PI*2,rr=radius(a)*(.7+rand()*.27),x=Math.cos(a)*rr,z=Math.sin(a)*rr;if(noTree(x,z))continue;put(new THREE.IcosahedronGeometry(.5+rand()*.8,0),i%3===0?'stone':'leaf3','vegetation',v(x,groundHeight(x,z)+.3,z),new THREE.Euler(rand(),rand(),rand()),v(1.2,.65,1));}
  for(let i=0;i<70;i++){const x=(rand()-.5)*85,z=(rand()-.5)*85;if(Math.hypot(x,z)>43||noTree(x,z))continue;put(new THREE.IcosahedronGeometry(.1+rand()*.13,0),i%4===0?'pink':'flower','vegetation',v(x,groundHeight(x,z)+.22,z));}
  for(let i=0;i<24;i++){const a=rand()*Math.PI*2,r=radius(a),x=Math.cos(a)*r,z=Math.sin(a)*r;const length=2+rand()*10;for(let j=0;j<length;j+=1.1)put(new THREE.IcosahedronGeometry(.5+rand()*.6,0),i%2?'leaf1':'leaf2','vegetation',v(x*(1-j*.006),groundHeight(x,z)-j,z*(1-j*.006)),new THREE.Euler(),v(1,1.35,.7));}
  // A small pavilion, benches and warm lanterns along the lakeside.
  const gx=-21,gz=19,gy=groundHeight(gx,gz);put(new THREE.CylinderGeometry(2.7,2.7,.3,8),'wood','paths',v(gx,gy+.3,gz));
  for(let i=0;i<8;i++){const a=i/8*Math.PI*2;box(gx+Math.cos(a)*2.3,gy+1.8,gz+Math.sin(a)*2.3,.16,3,.16,'timber','paths');}
  put(new THREE.ConeGeometry(3.4,2.2,8),'roof','paths',v(gx,gy+4.2,gz));
  [[-3,23],[12,10],[-18,8],[5,-2],[20,29]].forEach(([x,z])=>{const y=groundHeight(x,z);box(x,y+.7,z,1.8,.16,.6,'wood','paths');box(x,y+1.15,z+.3,1.8,.65,.1,'wood','paths');for(const dx of [-.65,.65])box(x+dx,y+.35,z,.12,.7,.5,'timber','paths');});
  for(let i=0;i<13;i++){const a=i/13*Math.PI*2,x=-2+Math.cos(a)*17,z=11+Math.sin(a)*15;if(x<-9&&z>22)continue;const y=groundHeight(x,z);box(x,y+1.3,z,.1,2.6,.1,'timber','paths');box(x,y+2.5,z,.35,.5,.35,'window','paths');put(new THREE.ConeGeometry(.36,.24,4),'timber','paths',v(x,y+2.9,z),new THREE.Euler(0,Math.PI/4,0));}

  batches.forEach((geometries,key)=>{const [layer,material]=key.split(':');const merged=mergeGeometries(geometries,false);if(merged){const mesh=new THREE.Mesh(merged,materials[material]);mesh.name=`${layer}_${material}`;mesh.castShadow=layer!=='water';mesh.receiveShadow=true;groups[layer as LayerKey].add(mesh);}geometries.forEach(g=>g.dispose());});
  return { root, groups, treeCount: trees, buildingCount: 22 };
}
