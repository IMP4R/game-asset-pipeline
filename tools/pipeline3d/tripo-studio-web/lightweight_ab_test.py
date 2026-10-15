import bpy, sys, os, json, math, time
from mathutils import Vector
import numpy as np

src,out_glb,render_dir,method=sys.argv[sys.argv.index('--')+1:]
os.makedirs(render_dir,exist_ok=True)
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=src)
objs=[o for o in bpy.context.scene.objects if o.type=='MESH']
objs.sort(key=lambda o:len(o.data.polygons),reverse=True)
# classify without reconstructing: body largest; handle widest of remaining; two pivots
body=objs[0]; arc=max(objs[1:],key=lambda o:max((v.co.x for v in o.data.vertices),default=0)-min((v.co.x for v in o.data.vertices),default=0)); pivs=[o for o in objs if o not in (body,arc)]
parts=[body,arc]+pivs
targets={body:350,arc:110,pivs[0]:20,pivs[1]:20}

def tri(o): return sum(len(p.vertices)-2 for p in o.data.polygons)
def activate(o):
 bpy.ops.object.select_all(action='DESELECT');o.select_set(True);bpy.context.view_layer.objects.active=o

def decimate(o,target,planar=False,protect=False):
 activate(o)
 if planar:
  m=o.modifiers.new('Feature planar prepass','DECIMATE');m.decimate_type='DISSOLVE';m.angle_limit=math.radians(3.0);m.use_dissolve_boundaries=False
  bpy.ops.object.modifier_apply(modifier=m.name)
 before=tri(o)
 if before<=target:return
 if protect:
  vg=o.vertex_groups.new(name='critical_source_features')
  zs=[(o.matrix_world@v.co).z for v in o.data.vertices];z0,z1=min(zs),max(zs)
  for v,z in zip(o.data.vertices,zs):
   p=o.matrix_world@v.co;crit=(o==body and (z>z0+.78*(z1-z0) or z<z0+.14*(z1-z0))) or (o in pivs)
   if crit:vg.add([v.index],1.0,'REPLACE')
 m=o.modifiers.new('Source edge collapse','DECIMATE');m.decimate_type='COLLAPSE';m.ratio=max(.001,min(1,target/max(1,tri(o))));m.use_collapse_triangulate=True;m.use_symmetry=True;m.symmetry_axis='X'
 if protect:m.vertex_group=vg.name;m.vertex_group_factor=.02
 bpy.ops.object.modifier_apply(modifier=m.name)

def cluster_once(o,cell):
 V=np.array([tuple(v.co) for v in o.data.vertices],dtype=np.float64)
 if len(V)==0:return None
 origin=V.min(0);keys=np.floor((V-origin)/cell+.5).astype(np.int64)
 _,inv=np.unique(keys,axis=0,return_inverse=True);n=int(inv.max())+1
 sums=np.zeros((n,3));cnt=np.bincount(inv,minlength=n);np.add.at(sums,inv,V);NV=sums/cnt[:,None]
 faces=[];mats=[]
 for p in o.data.polygons:
  ids=[]
  for vi in p.vertices:
   q=int(inv[vi])
   if not ids or ids[-1]!=q:ids.append(q)
  if len(ids)>2 and ids[0]==ids[-1]:ids.pop()
  if len(set(ids))<3:continue
  # fan triangulation is derived solely from surviving source polygon corners
  for j in range(1,len(ids)-1):
   f=(ids[0],ids[j],ids[j+1])
   if len(set(f))==3:faces.append(f);mats.append(p.material_index)
 return NV,faces,mats

def cluster(o,target):
 V=np.array([tuple(v.co) for v in o.data.vertices]);diag=float(np.linalg.norm(V.max(0)-V.min(0)))
 lo,hi=diag/1000,diag/2;best=None
 for _ in range(22):
  mid=(lo+hi)/2;r=cluster_once(o,mid);nf=len(r[1])
  if best is None or abs(nf-target)<abs(len(best[1])-target):best=r
  if nf>target:lo=mid
  else:hi=mid
 NV,F,M=best;mesh=bpy.data.meshes.new(o.data.name+'_clustered');mesh.from_pydata(NV.tolist(),[],F);mesh.materials.clear()
 for mat in o.data.materials:mesh.materials.append(mat)
 for p,mi in zip(mesh.polygons,M):p.material_index=min(mi,max(0,len(mesh.materials)-1));p.use_smooth=True
 old=o.data;o.data=mesh;bpy.data.meshes.remove(old)
 # a tiny source-edge collapse only if clustering stopped above budget
 if tri(o)>target*1.08:decimate(o,target,False,False)

start=time.perf_counter()
if method=='A':
 for o in parts:decimate(o,targets[o],False,True)
 label='A guarded source-edge QEM'
elif method=='B':
 for o in parts:cluster(o,targets[o])
 label='B source vertex clustering'
elif method=='C':
 for o in parts:decimate(o,targets[o],True,False)
 label='C planar-feature prepass + source-edge QEM'
else:raise ValueError(method)
compute_seconds=time.perf_counter()-start
# exact same source materials and render setup
for o in parts:
 for p in o.data.polygons:p.use_smooth=True
 o.select_set(True)
bpy.ops.export_scene.gltf(filepath=out_glb,export_format='GLB',use_selection=True,export_materials='EXPORT')
st={'method':label,'compute_seconds':compute_seconds,'vertices':sum(len(o.data.vertices) for o in parts),'polygons':sum(len(o.data.polygons) for o in parts),'triangles':sum(tri(o) for o in parts),'component_triangles':[tri(o) for o in parts],'within_60_seconds':compute_seconds<=60}
with open(os.path.join(render_dir,'stats.json'),'w') as f:json.dump(st,f,indent=2)
sc=bpy.context.scene;sc.render.engine='BLENDER_EEVEE_NEXT';sc.render.resolution_x=600;sc.render.resolution_y=600;sc.render.resolution_percentage=100;sc.render.image_settings.file_format='PNG';sc.view_settings.view_transform='Standard';sc.view_settings.look='Medium High Contrast'
if not sc.world:sc.world=bpy.data.worlds.new('World')
sc.world.use_nodes=True;sc.world.node_tree.nodes['Background'].inputs['Color'].default_value=(.018,.022,.03,1);sc.world.node_tree.nodes['Background'].inputs['Strength'].default_value=.28
for n,loc,en,sz in [('Key',(4,-5,7),900,5),('Fill',(-4,-2,4),450,4),('Rim',(2,5,5),650,3)]:
 ld=bpy.data.lights.new(n,'AREA');ld.energy=en;ld.size=sz;x=bpy.data.objects.new(n,ld);sc.collection.objects.link(x);x.location=loc
cd=bpy.data.cameras.new('Camera');cam=bpy.data.objects.new('Camera',cd);sc.collection.objects.link(cam);sc.camera=cam;cd.type='ORTHO';cd.ortho_scale=1.28;focus=Vector((0,0,.41))
def shot(n,pos):cam.location=Vector(pos);cam.rotation_euler=(focus-cam.location).to_track_quat('-Z','Y').to_euler();sc.render.filepath=os.path.join(render_dir,f'{method}_{n}.png');bpy.ops.render.render(write_still=True)
shot('front',(0,-4,.48));shot('side',(4,0,.48));shot('top',(0,0,4));shot('perspective',(1.8,-2.8,1.45))
print(json.dumps(st,indent=2))
