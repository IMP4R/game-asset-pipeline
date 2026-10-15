import bpy,bmesh,sys,os,json,math
import numpy as np
from mathutils import Vector
dense_path,low_path,out_path,render_dir=sys.argv[sys.argv.index('--')+1:];os.makedirs(render_dir,exist_ok=True)
def load(path):
 bpy.ops.wm.read_factory_settings(use_empty=True);bpy.ops.import_scene.gltf(filepath=path);o=[x for x in bpy.context.scene.objects if x.type=='MESH'];o.sort(key=lambda x:len(x.data.polygons),reverse=True);return o
def arr(o):return np.array([tuple(o.matrix_world@v.co) for v in o.data.vertices],float)
def setarr(o,a):
 inv=o.matrix_world.inverted()
 for v,p in zip(o.data.vertices,a):v.co=inv@Vector(p)
# Fit the exterior taper from dense cleaned source.
dobjs=load(dense_path);db=dobjs[0];D=arr(db);dr=np.linalg.norm(D[:,:2],axis=1);dz=D[:,2];nm=db.matrix_world.to_3x3().inverted().transposed();dn=np.array([tuple((nm@v.normal).normalized()) for v in db.data.vertices]);rv=np.zeros_like(D);rv[:,:2]=D[:,:2]/np.maximum(dr[:,None],1e-9);dm=(dz>.055)&(dz<.625)&(dr>.34)&((dn*rv).sum(1)>.18)
bins=np.linspace(.055,.625,30);zc=[];rc=[]
for lo,hi in zip(bins[:-1],bins[1:]):
 q=dm&(dz>=lo)&(dz<hi)
 if q.sum()>=6:zc.append(float(np.median(dz[q])));rc.append(float(np.median(dr[q])))
coef=np.polyfit(zc,rc,2)
# Reload low mesh and project its exterior wall after all QEM operations.
objs=load(low_path);body=objs[0];A=arr(body);r=np.linalg.norm(A[:,:2],axis=1);z=A[:,2];body.data.update();nm=body.matrix_world.to_3x3().inverted().transposed();N=np.array([tuple((nm@v.normal).normalized()) for v in body.data.vertices]);R=np.zeros_like(A);R[:,:2]=A[:,:2]/np.maximum(r[:,None],1e-9);outward=(N*R).sum(1);mask=(z>.055)&(z<.625)&(r>.34)&(outward>.12)
target=np.polyval(coef,z);before=r-target
# Preserve transition near rim and foot, exact projection in the visible broad mid-wall.
fade=np.clip((z-.055)/.055,0,1)*np.clip((.625-z)/.07,0,1);newr=r+(target-r)*fade;scale=newr/np.maximum(r,1e-9);A[mask,0]*=scale[mask];A[mask,1]*=scale[mask];setarr(body,A)
for o in objs:
 bm=bmesh.new();bm.from_mesh(o.data);bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bm.to_mesh(o.data);bm.free();bpy.ops.object.select_all(action='DESELECT');o.select_set(True);bpy.context.view_layer.objects.active=o;bpy.ops.object.shade_smooth_by_angle(angle=math.radians(45),keep_sharp_edges=False);o.select_set(True)
bpy.ops.object.select_all(action='DESELECT')
for o in objs:o.select_set(True)
bpy.ops.export_scene.gltf(filepath=out_path,export_format='GLB',use_selection=True,export_materials='EXPORT')
AA=arr(body);rr=np.linalg.norm(AA[:,:2],axis=1);after=rr-np.polyval(coef,AA[:,2]);st={'triangles':sum(len(p.vertices)-2 for o in objs for p in o.data.polygons),'projected_low_vertices':int(mask.sum()),'dense_profile_samples':len(zc),'dense_profile_coefficients':coef.tolist(),'before_profile_rms_selected':float(np.sqrt(np.mean(before[mask]**2))),'after_profile_rms_selected':float(np.sqrt(np.mean(after[mask]**2))),'max_vertex_shift':float(np.max(np.abs((newr-r)[mask]))),'method':'post-QEM exterior projection to quadratic profile measured from dense cleaned Tripo source'};json.dump(st,open(os.path.join(render_dir,'stats.json'),'w'),indent=2)
# audit render
body=objs[0]
def mat(n,c):m=bpy.data.materials.new(n);m.use_nodes=True;b=m.node_tree.nodes['Principled BSDF'];b.inputs['Base Color'].default_value=c;b.inputs['Roughness'].default_value=.78;b.inputs['Specular IOR Level'].default_value=.2;return m
orange=mat('Orange',(1,.29,.012,1));black=mat('Black',(.035,.043,.057,1))
for o in objs:o.data.materials.clear();o.data.materials.append(orange if o==body else black)
sc=bpy.context.scene;sc.render.engine='BLENDER_EEVEE_NEXT';sc.render.resolution_x=700;sc.render.resolution_y=700;sc.render.resolution_percentage=100;sc.render.image_settings.file_format='PNG';sc.view_settings.view_transform='Standard';sc.view_settings.look='Medium High Contrast';sc.world=bpy.data.worlds.new('World');sc.world.use_nodes=True;sc.world.node_tree.nodes['Background'].inputs['Color'].default_value=(.018,.022,.03,1);sc.world.node_tree.nodes['Background'].inputs['Strength'].default_value=.35
for n,l,e,s in [('Key',(-4,-5,7),700,6),('Fill',(5,-2,4),350,5),('Top',(0,2,7),420,4),('Rim',(2,5,3),240,3)]:ld=bpy.data.lights.new(n,'AREA');ld.energy=e;ld.size=s;x=bpy.data.objects.new(n,ld);sc.collection.objects.link(x);x.location=l
cd=bpy.data.cameras.new('Camera');cam=bpy.data.objects.new('Camera',cd);sc.collection.objects.link(cam);sc.camera=cam;cd.type='ORTHO';cd.ortho_scale=1.28;focus=Vector((0,0,.41))
def shot(v,p):cam.location=Vector(p);cam.rotation_euler=(focus-cam.location).to_track_quat('-Z','Y').to_euler();sc.render.filepath=os.path.join(render_dir,f'projected_{v}.png');bpy.ops.render.render(write_still=True)
shot('front',(0,-4,.48));shot('side',(4,0,.48));shot('back',(0,4,.48));shot('top',(0,0,4));shot('perspective',(1.8,-2.8,1.45));print(json.dumps(st,indent=2))
