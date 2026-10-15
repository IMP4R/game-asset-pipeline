import bpy,sys,os,json,numpy as np,math
from mathutils import Vector
src,npz_path,out,render_dir=sys.argv[sys.argv.index('--')+1:]
os.makedirs(render_dir,exist_ok=True)
bpy.ops.wm.read_factory_settings(use_empty=True);bpy.ops.import_scene.gltf(filepath=src)
root=next(x for x in bpy.context.scene.objects if x.type=='MESH');bpy.context.view_layer.objects.active=root;root.select_set(True)
bpy.ops.object.mode_set(mode='EDIT');bpy.ops.mesh.separate(type='LOOSE');bpy.ops.object.mode_set(mode='OBJECT')
parts=[x for x in bpy.context.selected_objects if x.type=='MESH'];parts.sort(key=lambda p:len(p.data.polygons),reverse=True)
data=np.load(npz_path)
# The exported component order is deterministic: descending polygon count.
for i,o in enumerate(parts):
 arr=data[f'v{i}']
 if len(arr)!=len(o.data.vertices):raise RuntimeError((i,len(arr),len(o.data.vertices)))
 original=np.array([tuple(o.matrix_world@v.co) for v in o.data.vertices],dtype=np.float32)
 delta=arr-original
 # Smooth the network residual over mesh connectivity. This prevents isolated teeth.
 nbs=[set() for _ in o.data.vertices]
 for e in o.data.edges:
  a,b=e.vertices;nbs[a].add(b);nbs[b].add(a)
 for _ in range(5 if i==0 else 3):
  nxt=delta.copy()
  for j,ns in enumerate(nbs):
   if ns:nxt[j]=.35*delta[j]+.65*np.mean(delta[list(ns)],axis=0)
  delta=nxt
 if i==0:
  # Neural correction only on the smooth exterior mid-wall. Rim, cavity and bottom stay exact.
  r=np.linalg.norm(original[:,:2],axis=1)
  mask=(original[:,2]>.12)&(original[:,2]<.61)&(r>.39)
  delta[~mask]=0; delta*=.42
 elif i in (1,2):
  # Pivots are contact-critical: align rigidly later, but do not neural-deform them.
  delta[:]=0
 else:
  delta*=.45
 corrected=original+delta
 inv=o.matrix_world.inverted()
 for j,p in enumerate(corrected):o.data.vertices[j].co=inv@Vector(p)
 o.name=['Bucket_Neural_Denoised','Pivot_L_Locked','Pivot_R_Locked','Handle_Neural'][i]
 for f in o.data.polygons:f.use_smooth=True
# Rigidly align handle assembly by pivot centroids, but do not cut or remesh anything.
def cent(o):return sum((o.matrix_world@v.co for v in o.data.vertices),Vector())/len(o.data.vertices)
pa,pb=parts[1],parts[2];ca,cb=cent(pa),cent(pb);mid=(ca+cb)/2;rot=(cb-ca).normalized().rotation_difference(Vector((1,0,0)))
for o in parts[1:]:
 inv=o.matrix_world.inverted()
 for v in o.data.vertices:
  p=o.matrix_world@v.co;v.co=inv@(mid+rot@(p-mid))
# Center whole asset using body bbox.
bv=[parts[0].matrix_world@v.co for v in parts[0].data.vertices];cx=(min(v.x for v in bv)+max(v.x for v in bv))/2;cy=(min(v.y for v in bv)+max(v.y for v in bv))/2
for o in parts:o.location.x-=cx;o.location.y-=cy
for o in parts:o.select_set(True)
bpy.ops.export_scene.gltf(filepath=out,export_format='GLB',use_selection=True,export_materials='EXPORT')
# Audit and renders.
stats={'source':src,'neural_checkpoint_parameters':189604,'objects':4,'vertices':sum(len(o.data.vertices) for o in parts),'polygons':sum(len(o.data.polygons) for o in parts),'triangles':sum(len(f.vertices)-2 for o in parts for f in o.data.polygons),'geometry':'original topology, vertex residuals only','handle_axis_error':max(abs(cent(pa).y-cent(pb).y),abs(cent(pa).z-cent(pb).z))}
scene=bpy.context.scene;scene.render.engine='BLENDER_EEVEE_NEXT';scene.render.resolution_x=720;scene.render.resolution_y=720;scene.render.resolution_percentage=100;scene.render.image_settings.file_format='PNG';scene.view_settings.view_transform='Standard';scene.view_settings.look='Medium High Contrast'
scene.world=bpy.data.worlds.new('World');scene.world.use_nodes=True;scene.world.node_tree.nodes['Background'].inputs['Color'].default_value=(.018,.022,.03,1);scene.world.node_tree.nodes['Background'].inputs['Strength'].default_value=.28
for name,loc,en,sz in [('Key',(4,-5,7),900,5),('Fill',(-4,-2,4),450,4),('Rim',(2,5,5),650,3)]:
 ld=bpy.data.lights.new(name,'AREA');ld.energy=en;ld.size=sz;o=bpy.data.objects.new(name,ld);scene.collection.objects.link(o);o.location=loc
camd=bpy.data.cameras.new('Camera');cam=bpy.data.objects.new('Camera',camd);scene.collection.objects.link(cam);scene.camera=cam;camd.type='ORTHO';camd.ortho_scale=1.28;center=Vector((0,0,.41))
def shot(n,pos):cam.location=Vector(pos);cam.rotation_euler=(center-cam.location).to_track_quat('-Z','Y').to_euler();scene.render.filepath=os.path.join(render_dir,f'neural_{n}.png');bpy.ops.render.render(write_still=True)
shot('front',(0,-4,.48));shot('side',(4,0,.48));shot('top',(0,0,4))
with open(os.path.join(render_dir,'neural_stats.json'),'w') as f:json.dump(stats,f,indent=2)
print(json.dumps(stats,indent=2))
