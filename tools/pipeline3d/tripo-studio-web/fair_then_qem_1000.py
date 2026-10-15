import bpy,bmesh,sys,os,json,math,time
import numpy as np
from mathutils import Vector
src,out,render_dir=sys.argv[sys.argv.index('--')+1:];os.makedirs(render_dir,exist_ok=True)
bpy.ops.wm.read_factory_settings(use_empty=True);bpy.ops.import_scene.gltf(filepath=src)
objs=[o for o in bpy.context.scene.objects if o.type=='MESH'];objs.sort(key=lambda o:len(o.data.polygons),reverse=True);body=objs[0];arc=max(objs[1:],key=lambda o:max((o.matrix_world@v.co).x for v in o.data.vertices)-min((o.matrix_world@v.co).x for v in o.data.vertices));pivs=[o for o in objs if o not in (body,arc)];pivs.sort(key=lambda o:sum((o.matrix_world@v.co).x for v in o.data.vertices)/len(o.data.vertices));left,right=pivs

def W(o):return np.array([tuple(o.matrix_world@v.co) for v in o.data.vertices],float)
def setW(o,a):
 inv=o.matrix_world.inverted()
 for v,p in zip(o.data.vertices,a):v.co=inv@Vector(p)
def WV(o):return [o.matrix_world@v.co for v in o.data.vertices]
def cen(o):v=WV(o);return sum(v,Vector())/len(v)
def setw(o,i,p):o.data.vertices[i].co=o.matrix_world.inverted()@p
def tri(o):return sum(len(p.vertices)-2 for p in o.data.polygons)
def active(o):bpy.ops.object.select_all(action='DESELECT');o.select_set(True);bpy.context.view_layer.objects.active=o

def mirror_half(o):
 bm=bmesh.new();bm.from_mesh(o.data);co=o.matrix_world.inverted()@Vector((0,0,0));no=(o.matrix_world.inverted().to_3x3().transposed()@Vector((1,0,0))).normalized();bmesh.ops.bisect_plane(bm,geom=list(bm.verts)+list(bm.edges)+list(bm.faces),dist=1e-6,plane_co=co,plane_no=no,clear_outer=True);bm.to_mesh(o.data);bm.free();active(o);bpy.context.scene.cursor.location=(0,0,0);bpy.ops.object.origin_set(type='ORIGIN_CURSOR');m=o.modifiers.new('Source half sync','MIRROR');m.use_clip=True;m.use_mirror_merge=True;m.merge_threshold=.002;bpy.ops.object.modifier_apply(modifier=m.name)
def collapse(o,target,sym=True,planar=False,protect_indices=None):
 active(o)
 if planar:
  m=o.modifiers.new('Planar handle cleanup','DECIMATE');m.decimate_type='DISSOLVE';m.angle_limit=math.radians(2);bpy.ops.object.modifier_apply(modifier=m.name)
 m=o.modifiers.new('Source QEM','DECIMATE');m.decimate_type='COLLAPSE';m.ratio=min(1,target/max(1,tri(o)));m.use_collapse_triangulate=True;m.use_symmetry=sym;m.symmetry_axis='X'
 if protect_indices is not None and len(protect_indices)>0:
  vg=o.vertex_groups.new(name='Preserve faired wall distribution');vg.add([int(i) for i in protect_indices],1.0,'REPLACE');m.vertex_group=vg.name;m.vertex_group_factor=.62
 bpy.ops.object.modifier_apply(modifier=m.name)
start=time.perf_counter()
# Fair dense original body before any topology collapse.
a=W(body);r=np.linalg.norm(a[:,:2],axis=1);z=a[:,2];body.data.update();nm=body.matrix_world.to_3x3().inverted().transposed();N=np.array([tuple((nm@v.normal).normalized()) for v in body.data.vertices]);R=np.zeros_like(a);R[:,:2]=a[:,:2]/np.maximum(r[:,None],1e-9);outward=(N*R).sum(1);mask=(z>.09)&(z<.59)&(r>.34)&(outward>.18)
edges=np.linspace(z[mask].min(),z[mask].max(),26);zc=[];rc=[]
for lo,hi in zip(edges[:-1],edges[1:]):
 q=mask&(z>=lo)&(z<hi)
 if q.sum()>=8:zc.append(float(np.median(z[q])));rc.append(float(np.median(r[q])))
coef=np.polyfit(zc,rc,2);target=np.polyval(coef,z);fade=np.clip((z-.09)/.06,0,1)*np.clip((.59-z)/.06,0,1);dr=np.clip(target-r,-.012,.012)*.82*fade;scale=(r+dr)/np.maximum(r,1e-9);a[mask,0]*=scale[mask];a[mask,1]*=scale[mask];setW(body,a)
# Exact synchronized handle and pivots.
ca,cb=cen(left),cen(right);mid=(ca+cb)/2;rot=(cb-ca).normalized().rotation_difference(Vector((1,0,0)))
for o in (arc,left,right):
 for i,p in enumerate(WV(o)):setw(o,i,mid+rot@(p-mid))
mirror_half(arc)
# Key change: NO planar dissolve on body, retaining distributed source wall vertices.
collapse(body,720,True,False,np.where(mask)[0]);collapse(arc,220,True,True);collapse(left,30,False,False);bpy.data.objects.remove(right,do_unlink=True);right=left.copy();right.data=left.data.copy();bpy.context.collection.objects.link(right)
for i,p in enumerate(WV(right)):setw(right,i,Vector((-p.x,p.y,p.z)))
parts=[body,arc,left,right]
for o in parts:
 bm=bmesh.new();bm.from_mesh(o.data);bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bm.to_mesh(o.data);bm.free();active(o);bpy.ops.object.shade_smooth_by_angle(angle=math.radians(45),keep_sharp_edges=False);o.select_set(True)
compute=time.perf_counter()-start;bpy.ops.export_scene.gltf(filepath=out,export_format='GLB',use_selection=True,export_materials='EXPORT')
# audit outer wall vertex distribution after collapse
A=W(body);rr=np.linalg.norm(A[:,:2],axis=1);zz=A[:,2];wall=(zz>.105)&(zz<.565)&(rr>.34);hv=WV(arc);mirror=max(min((Vector((-p.x,p.y,p.z))-q).length for q in hv) for p in hv)
st={'method':'dense-source fairing then body QEM without planar dissolve','compute_seconds':compute,'triangles':sum(tri(o) for o in parts),'component_triangles':[tri(o) for o in parts],'body_outer_midwall_vertices_after_qem':int(wall.sum()),'dense_wall_vertices_faired':int(mask.sum()),'handle_mirror_error':mirror}
json.dump(st,open(os.path.join(render_dir,'stats.json'),'w'),indent=2)
# ordinary PBR audit
def mat(n,c):m=bpy.data.materials.new(n);m.use_nodes=True;b=m.node_tree.nodes['Principled BSDF'];b.inputs['Base Color'].default_value=c;b.inputs['Roughness'].default_value=.78;b.inputs['Specular IOR Level'].default_value=.2;return m
orange=mat('Orange',(1,.29,.012,1));black=mat('Black',(.035,.043,.057,1))
for o in parts:o.data.materials.clear();o.data.materials.append(orange if o==body else black)
sc=bpy.context.scene;sc.render.engine='BLENDER_EEVEE_NEXT';sc.render.resolution_x=700;sc.render.resolution_y=700;sc.render.resolution_percentage=100;sc.render.image_settings.file_format='PNG';sc.view_settings.view_transform='Standard';sc.view_settings.look='Medium High Contrast';sc.world=bpy.data.worlds.new('World');sc.world.use_nodes=True;sc.world.node_tree.nodes['Background'].inputs['Color'].default_value=(.018,.022,.03,1);sc.world.node_tree.nodes['Background'].inputs['Strength'].default_value=.35
for n,loc,en,sz in [('Key',(-4,-5,7),700,6),('Fill',(5,-2,4),350,5),('Top',(0,2,7),420,4),('Rim',(2,5,3),240,3)]:ld=bpy.data.lights.new(n,'AREA');ld.energy=en;ld.size=sz;x=bpy.data.objects.new(n,ld);sc.collection.objects.link(x);x.location=loc
cd=bpy.data.cameras.new('Camera');cam=bpy.data.objects.new('Camera',cd);sc.collection.objects.link(cam);sc.camera=cam;cd.type='ORTHO';cd.ortho_scale=1.28;focus=Vector((0,0,.41))
def shot(v,p):cam.location=Vector(p);cam.rotation_euler=(focus-cam.location).to_track_quat('-Z','Y').to_euler();sc.render.filepath=os.path.join(render_dir,f'v2_{v}.png');bpy.ops.render.render(write_still=True)
shot('front',(0,-4,.48));shot('side',(4,0,.48));shot('back',(0,4,.48));shot('top',(0,0,4));shot('perspective',(1.8,-2.8,1.45));print(json.dumps(st,indent=2))
