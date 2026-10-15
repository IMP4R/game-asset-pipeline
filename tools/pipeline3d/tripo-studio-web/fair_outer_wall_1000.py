import bpy,bmesh,sys,os,json,math
import numpy as np
from mathutils import Vector
src,out_glb,render_dir=sys.argv[sys.argv.index('--')+1:];os.makedirs(render_dir,exist_ok=True)
bpy.ops.wm.read_factory_settings(use_empty=True);bpy.ops.import_scene.gltf(filepath=src)
objs=[o for o in bpy.context.scene.objects if o.type=='MESH'];objs.sort(key=lambda o:len(o.data.polygons),reverse=True);body=objs[0]

def world(o):return np.array([tuple(o.matrix_world@v.co) for v in o.data.vertices],dtype=np.float64)
def setworld(o,a):
 inv=o.matrix_world.inverted()
 for v,p in zip(o.data.vertices,a):v.co=inv@Vector(p)
def radial_stats(a,mask):
 r=np.linalg.norm(a[:,:2],axis=1);z=a[:,2];edges=np.linspace(z[mask].min(),z[mask].max(),16);res=[]
 for lo,hi in zip(edges[:-1],edges[1:]):
  q=mask&(z>=lo)&(z<hi)
  if q.sum():res.extend((r[q]-np.median(r[q])).tolist())
 x=np.array(res);return {'rms':float(np.sqrt(np.mean(x*x))),'max':float(np.max(np.abs(x)))}
# World-space normals classify the exterior; this prevents mixing outer wall with cavity/floor layers.
body.data.update();a=world(body);r=np.linalg.norm(a[:,:2],axis=1);z=a[:,2]
N=np.array([tuple((body.matrix_world.to_3x3().inverted().transposed()@v.normal).normalized()) for v in body.data.vertices])
rad=np.zeros_like(a);rad[:,:2]=a[:,:2]/np.maximum(r[:,None],1e-9);outward=(N*rad).sum(1)
# Deliberately narrow safe band: no bottom foot, shoulder, rim underside, cavity, or handle contacts.
mask=(z>.105)&(z<.565)&(r>.35)&(outward>.20)
before=radial_stats(a,mask);old=a.copy()
# Robust median radius samples per height; cubic profile follows the source taper, not a primitive cylinder.
edges=np.linspace(z[mask].min(),z[mask].max(),20);zc=[];rc=[]
for lo,hi in zip(edges[:-1],edges[1:]):
 q=mask&(z>=lo)&(z<hi)
 if q.sum()>=3:zc.append(float(np.median(z[q])));rc.append(float(np.median(r[q])))
coef=np.polyfit(zc,rc,min(3,len(zc)-1));target=np.polyval(coef,z)
# Soft boundary fade + bounded correction. Preserve some local Tripo character while eliminating broad bands.
fade=np.clip((z-.105)/.07,0,1)*np.clip((.565-z)/.07,0,1);delta=np.clip(target-r,-.016,.016)*.90*fade
scale=(r+delta)/np.maximum(r,1e-9);a[mask,0]*=scale[mask];a[mask,1]*=scale[mask]
setworld(body,a);body.data.update()
# Correct topology normals and use only Blender's built-in smoothing.
for o in objs:
 bm=bmesh.new();bm.from_mesh(o.data);bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bm.to_mesh(o.data);bm.free();o.data.update()
 bpy.ops.object.select_all(action='DESELECT');o.select_set(True);bpy.context.view_layer.objects.active=o;bpy.ops.object.shade_smooth_by_angle(angle=math.radians(45),keep_sharp_edges=False)
for o in objs:o.select_set(True)
bpy.ops.export_scene.gltf(filepath=out_glb,export_format='GLB',use_selection=True,export_materials='EXPORT')
after_a=world(body);after=radial_stats(after_a,mask);shift=np.linalg.norm(after_a-old,axis=1)
# Symmetry check for unchanged synchronized handle and body center behavior.
handle=max(objs[1:],key=lambda o:len(o.data.polygons));hv=[handle.matrix_world@v.co for v in handle.data.vertices];mirror=max(min((Vector((-p.x,p.y,p.z))-q).length for q in hv) for p in hv)
st={'method':'bounded source-derived radial wall fairing + recalc normals + Blender Auto Smooth 45','triangles':sum(len(p.vertices)-2 for o in objs for p in o.data.polygons),'wall_vertices_adjusted':int(mask.sum()),'before_radial_residual':before,'after_radial_residual':after,'mean_adjusted_shift':float(shift[mask].mean()),'max_adjusted_shift':float(shift[mask].max()),'handle_mirror_max_vertex_error':mirror,'profile_degree':len(coef)-1,'protected_regions':['bottom foot','upper shoulder','rim underside','rim','inner cavity','handle','pivots']}
json.dump(st,open(os.path.join(render_dir,'stats.json'),'w'),indent=2)
# Ordinary continuous PBR audit lighting, identical to smoothing diagnosis.
def mat(n,c):m=bpy.data.materials.new(n);m.use_nodes=True;b=m.node_tree.nodes['Principled BSDF'];b.inputs['Base Color'].default_value=c;b.inputs['Roughness'].default_value=.78;b.inputs['Specular IOR Level'].default_value=.2;return m
orange=mat('Orange PBR',(1,.29,.012,1));black=mat('Black PBR',(.035,.043,.057,1))
for o in objs:o.data.materials.clear();o.data.materials.append(orange if o==body else black)
sc=bpy.context.scene;sc.render.engine='BLENDER_EEVEE_NEXT';sc.render.resolution_x=700;sc.render.resolution_y=700;sc.render.resolution_percentage=100;sc.render.image_settings.file_format='PNG';sc.view_settings.view_transform='Standard';sc.view_settings.look='Medium High Contrast';sc.world=bpy.data.worlds.new('World');sc.world.use_nodes=True;sc.world.node_tree.nodes['Background'].inputs['Color'].default_value=(.018,.022,.03,1);sc.world.node_tree.nodes['Background'].inputs['Strength'].default_value=.35
for n,loc,en,sz in [('Key',(-4,-5,7),700,6),('Fill',(5,-2,4),350,5),('Top',(0,2,7),420,4),('Rim',(2,5,3),240,3)]:ld=bpy.data.lights.new(n,'AREA');ld.energy=en;ld.size=sz;x=bpy.data.objects.new(n,ld);sc.collection.objects.link(x);x.location=loc
cd=bpy.data.cameras.new('Camera');cam=bpy.data.objects.new('Camera',cd);sc.collection.objects.link(cam);sc.camera=cam;cd.type='ORTHO';cd.ortho_scale=1.28;focus=Vector((0,0,.41))
def shot(v,p):cam.location=Vector(p);cam.rotation_euler=(focus-cam.location).to_track_quat('-Z','Y').to_euler();sc.render.filepath=os.path.join(render_dir,f'fair_{v}.png');bpy.ops.render.render(write_still=True)
shot('front',(0,-4,.48));shot('side',(4,0,.48));shot('back',(0,4,.48));shot('top',(0,0,4));shot('perspective',(1.8,-2.8,1.45));print(json.dumps(st,indent=2))
