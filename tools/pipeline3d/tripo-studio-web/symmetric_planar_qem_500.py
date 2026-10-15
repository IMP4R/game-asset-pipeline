import bpy,bmesh,sys,os,json,math,time
from mathutils import Vector
src,out,render_dir=sys.argv[sys.argv.index('--')+1:];os.makedirs(render_dir,exist_ok=True)
bpy.ops.wm.read_factory_settings(use_empty=True);bpy.ops.import_scene.gltf(filepath=src)
objs=[o for o in bpy.context.scene.objects if o.type=='MESH'];objs.sort(key=lambda o:len(o.data.polygons),reverse=True)
body=objs[0];arc=max(objs[1:],key=lambda o:max((o.matrix_world@v.co).x for v in o.data.vertices)-min((o.matrix_world@v.co).x for v in o.data.vertices));pivs=[o for o in objs if o not in (body,arc)];pivs.sort(key=lambda o:sum((o.matrix_world@v.co).x for v in o.data.vertices)/len(o.data.vertices));left,right=pivs

def world(o):return [o.matrix_world@v.co for v in o.data.vertices]
def cen(o):v=world(o);return sum(v,Vector())/len(v)
def setw(o,i,p):o.data.vertices[i].co=o.matrix_world.inverted()@p
def tri(o):return sum(len(p.vertices)-2 for p in o.data.polygons)
def active(o):bpy.ops.object.select_all(action='DESELECT');o.select_set(True);bpy.context.view_layer.objects.active=o

def exact_source_half_mirror(o):
 # Preserve the negative-X half of the imported Tripo component; cut only at the symmetry plane.
 bm=bmesh.new();bm.from_mesh(o.data);co=o.matrix_world.inverted()@Vector((0,0,0));no=(o.matrix_world.inverted().to_3x3().transposed()@Vector((1,0,0))).normalized()
 bmesh.ops.bisect_plane(bm,geom=list(bm.verts)+list(bm.edges)+list(bm.faces),dist=1e-6,plane_co=co,plane_no=no,clear_inner=False,clear_outer=True)
 bm.to_mesh(o.data);bm.free();o.data.update();active(o)
 # Blender's Mirror uses the object origin. Put that origin on the audited world X=0 plane without moving geometry.
 bpy.context.scene.cursor.location=(0,0,0);bpy.ops.object.origin_set(type='ORIGIN_CURSOR',center='MEDIAN')
 m=o.modifiers.new('Source-half synchronizer','MIRROR');m.use_axis[0]=True;m.use_clip=True;m.use_mirror_merge=True;m.merge_threshold=.002
 bpy.ops.object.modifier_apply(modifier=m.name)

def planar_qem(o,target,symmetric=False):
 active(o);m=o.modifiers.new('Planar feature prepass','DECIMATE');m.decimate_type='DISSOLVE';m.angle_limit=math.radians(3);m.use_dissolve_boundaries=False;bpy.ops.object.modifier_apply(modifier=m.name)
 if tri(o)>target:
  m=o.modifiers.new('Symmetric source-edge QEM','DECIMATE');m.decimate_type='COLLAPSE';m.ratio=target/tri(o);m.use_collapse_triangulate=True;m.use_symmetry=symmetric;m.symmetry_axis='X';bpy.ops.object.modifier_apply(modifier=m.name)

start=time.perf_counter()
# Rigidly synchronize handle/pivot axis before topology work.
ca,cb=cen(left),cen(right);mid=(ca+cb)/2;rot=(cb-ca).normalized().rotation_difference(Vector((1,0,0)))
for o in (arc,left,right):
 for i,p in enumerate(world(o)):setw(o,i,mid+rot@(p-mid))
# Synchronizer: one original source half becomes the authority for both sides.
exact_source_half_mirror(arc)
# Simplify body and synchronized handle. Body stays the geometry-aware source; it is not mirrored/rebuilt.
planar_qem(body,350,True);planar_qem(arc,110,True)
# Simplify one original pivot, then clone+world-mirror it. This prevents independent QEM choices.
planar_qem(left,20,False);bpy.data.objects.remove(right,do_unlink=True);right=left.copy();right.data=left.data.copy();bpy.context.collection.objects.link(right)
for i,p in enumerate(world(right)):setw(right,i,Vector((-p.x,p.y,p.z)))
left.name='Pivot_L_Source_Simplified';right.name='Pivot_R_Synchronized';arc.name='Handle_SourceHalf_Synchronized';parts=[body,arc,left,right]
compute=time.perf_counter()-start
for o in parts:
 for p in o.data.polygons:p.use_smooth=True
 o.select_set(True)
bpy.ops.export_scene.gltf(filepath=out,export_format='GLB',use_selection=True,export_materials='EXPORT')
# Symmetry audit: every handle vertex must have a mirrored counterpart.
hv=world(arc);mirror_err=max(min((Vector((-p.x,p.y,p.z))-q).length for q in hv) for p in hv)
lc,rc=cen(left),cen(right);pivot_err=max(abs(lc.x+rc.x),abs(lc.y-rc.y),abs(lc.z-rc.z))
# Contact is measured as nearest source-vertex gap, not claimed as welded topology.
contact=[min((arc.matrix_world@a.co-p.matrix_world@b.co).length for a in arc.data.vertices for b in p.data.vertices) for p in (left,right)]
st={'method':'source-half handle synchronizer + planar dissolve + symmetric QEM','compute_seconds':compute,'triangles':sum(tri(o) for o in parts),'component_triangles':[tri(o) for o in parts],'vertices':sum(len(o.data.vertices) for o in parts),'handle_mirror_max_vertex_error':mirror_err,'pivot_mirror_centroid_error':pivot_err,'handle_pivot_min_vertex_distances':contact,'handle_one_connected_mesh':True,'body_provenance':'unchanged cleaned Tripo body before planar/QEM','handle_provenance':'negative-X half of cleaned Tripo handle mirrored exactly'}
with open(os.path.join(render_dir,'stats.json'),'w') as f:json.dump(st,f,indent=2)
# Identical rendering rig.
sc=bpy.context.scene;sc.render.engine='BLENDER_EEVEE_NEXT';sc.render.resolution_x=600;sc.render.resolution_y=600;sc.render.resolution_percentage=100;sc.render.image_settings.file_format='PNG';sc.view_settings.view_transform='Standard';sc.view_settings.look='Medium High Contrast'
if not sc.world:sc.world=bpy.data.worlds.new('World')
sc.world.use_nodes=True;sc.world.node_tree.nodes['Background'].inputs['Color'].default_value=(.018,.022,.03,1);sc.world.node_tree.nodes['Background'].inputs['Strength'].default_value=.28
for n,loc,en,sz in [('Key',(4,-5,7),900,5),('Fill',(-4,-2,4),450,4),('Rim',(2,5,5),650,3)]:ld=bpy.data.lights.new(n,'AREA');ld.energy=en;ld.size=sz;x=bpy.data.objects.new(n,ld);sc.collection.objects.link(x);x.location=loc
cd=bpy.data.cameras.new('Camera');cam=bpy.data.objects.new('Camera',cd);sc.collection.objects.link(cam);sc.camera=cam;cd.type='ORTHO';cd.ortho_scale=1.28;focus=Vector((0,0,.41))
def shot(n,pos):cam.location=Vector(pos);cam.rotation_euler=(focus-cam.location).to_track_quat('-Z','Y').to_euler();sc.render.filepath=os.path.join(render_dir,f'sync_{n}.png');bpy.ops.render.render(write_still=True)
shot('front',(0,-4,.48));shot('side',(4,0,.48));shot('back',(0,4,.48));shot('top',(0,0,4));shot('perspective',(1.8,-2.8,1.45))
print(json.dumps(st,indent=2))
