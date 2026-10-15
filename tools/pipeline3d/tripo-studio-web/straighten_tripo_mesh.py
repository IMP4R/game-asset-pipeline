import bpy, bmesh, math, os, sys, json, statistics
from mathutils import Vector

args=sys.argv[sys.argv.index('--')+1:]
source, output, render_dir=args[0],args[1],args[2]
os.makedirs(render_dir,exist_ok=True)
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=source)
root=next(o for o in bpy.context.scene.objects if o.type=='MESH')
bpy.context.view_layer.objects.active=root; root.select_set(True)
bpy.ops.object.mode_set(mode='EDIT'); bpy.ops.mesh.separate(type='LOOSE'); bpy.ops.object.mode_set(mode='OBJECT')
parts=[o for o in bpy.context.selected_objects if o.type=='MESH']
parts.sort(key=lambda o:len(o.data.polygons),reverse=True)
body, pivot_a, pivot_b, arc=parts[0],parts[1],parts[2],parts[3]
# Correct classification by spatial extent: arc is the non-body part widest in X.
other=parts[1:]; arc=max(other,key=lambda o:max((o.matrix_world@v.co).x for v in o.data.vertices)-min((o.matrix_world@v.co).x for v in o.data.vertices))
pivots=[o for o in other if o!=arc]; pivots.sort(key=lambda o:sum((o.matrix_world@v.co).x for v in o.data.vertices)/len(o.data.vertices))
left_pivot,right_pivot=pivots

def world_verts(o): return [o.matrix_world@v.co for v in o.data.vertices]
def centroid(o):
    vs=world_verts(o); return sum(vs,Vector())/len(vs)
def set_world(o,i,p): o.data.vertices[i].co=o.matrix_world.inverted()@p

# Center using the source body bbox; move every source component together.
bv=world_verts(body); cx=(min(v.x for v in bv)+max(v.x for v in bv))/2; cy=(min(v.y for v in bv)+max(v.y for v in bv))/2
for o in parts: o.location.x-=cx; o.location.y-=cy

# Preserve the original Tripo surface exactly on the left side, then mirror it.
# This removes asymmetry without inventing a new profile or disturbing the rim/interior.
def mirror_source_half(o, label, keep_negative=True):
    bm=bmesh.new(); bm.from_mesh(o.data)
    plane_co=o.matrix_world.inverted()@Vector((0,0,0))
    plane_no=(o.matrix_world.inverted().to_3x3().transposed()@Vector((1,0,0))).normalized()
    bmesh.ops.bisect_plane(bm,geom=list(bm.verts)+list(bm.edges)+list(bm.faces),dist=1e-6,plane_co=plane_co,plane_no=plane_no,clear_outer=keep_negative,clear_inner=not keep_negative)
    bm.to_mesh(o.data); bm.free(); o.data.update()
    mod=o.modifiers.new(label,'MIRROR'); mod.use_axis[0]=True; mod.use_clip=True; mod.use_mirror_merge=True; mod.merge_threshold=.002
    bpy.context.view_layer.objects.active=o; o.select_set(True); bpy.ops.object.modifier_apply(modifier=mod.name); o.select_set(False)

mirror_source_half(body,'Exact body symmetry',True)
body.name='Tripo_Body_SourceHalf_Mirrored'

# Align the original handle assembly rigidly: vector between pivot centroids -> world X axis.
ca,cb=centroid(left_pivot),centroid(right_pivot); mid=(ca+cb)/2; vec=(cb-ca).normalized(); target=Vector((1,0,0))
rot=vec.rotation_difference(target)
for o in [arc,left_pivot,right_pivot]:
    for i,p in enumerate(world_verts(o)): set_world(o,i,mid+rot@(p-mid))

# Use the original left half of the source arc and mirror it exactly at X=0.
mirror_source_half(arc,'Exact handle symmetry',True)
arc.name='Tripo_Handle_Arc_SourceHalf_Mirrored'

# Keep the original left pivot; replace only the skewed counterpart with its exact mirror.
bpy.data.objects.remove(right_pivot,do_unlink=True)
right=left_pivot.copy(); right.data=left_pivot.data.copy(); bpy.context.collection.objects.link(right); right.name='Tripo_Pivot_R_Mirrored'
for i,p in enumerate(world_verts(right)): set_world(right,i,Vector((-p.x,p.y,p.z)))
left_pivot.name='Tripo_Pivot_L_Source'

# Preserve source materials, smooth existing surfaces, export.
final=[body,arc,left_pivot,right]
for o in final:
    for p in o.data.polygons:p.use_smooth=True
    o.select_set(True)
bpy.ops.export_scene.gltf(filepath=output,export_format='GLB',use_selection=True,export_materials='EXPORT')

# Numeric audit.
lc,rc=centroid(left_pivot),centroid(right)
axis_error=max(abs(lc.y-rc.y),abs(lc.z-rc.z),abs(lc.x+rc.x))
# Arc mirror bbox audit.
av=world_verts(arc); bbox_mirror_error=abs(min(v.x for v in av)+max(v.x for v in av))
stats={'source':source,'output':output,'objects':len(final),'vertices':sum(len(o.data.vertices) for o in final),'polygons':sum(len(o.data.polygons) for o in final),'triangles':sum(len(p.vertices)-2 for o in final for p in o.data.polygons),'pivot_axis_error':axis_error,'arc_bbox_mirror_error':bbox_mirror_error,'body_center':[0,0],'method':'original Tripo body and handle halves mirrored; rigid handle-axis alignment; no procedural replacement or decimation'}

# Render verification.
scene=bpy.context.scene; scene.render.engine='BLENDER_EEVEE_NEXT'; scene.render.resolution_x=640;scene.render.resolution_y=640;scene.render.resolution_percentage=100;scene.render.image_settings.file_format='PNG';scene.view_settings.view_transform='Standard';scene.view_settings.look='Medium High Contrast'
scene.world=bpy.data.worlds.new('World');scene.world.use_nodes=True;scene.world.node_tree.nodes['Background'].inputs['Color'].default_value=(.018,.022,.03,1);scene.world.node_tree.nodes['Background'].inputs['Strength'].default_value=.28
for name,loc,en,sz in [('Key',(4,-5,7),900,5),('Fill',(-4,-2,4),450,4),('Rim',(2,5,5),650,3)]:
 ld=bpy.data.lights.new(name,'AREA');ld.energy=en;ld.size=sz;o=bpy.data.objects.new(name,ld);scene.collection.objects.link(o);o.location=loc
camd=bpy.data.cameras.new('Camera');cam=bpy.data.objects.new('Camera',camd);scene.collection.objects.link(cam);scene.camera=cam;camd.type='ORTHO';camd.ortho_scale=1.28
center=Vector((0,0,.41))
def shot(name,pos):
 cam.location=Vector(pos);cam.rotation_euler=(center-cam.location).to_track_quat('-Z','Y').to_euler();scene.render.filepath=os.path.join(render_dir,f'aligned_{name}.png');bpy.ops.render.render(write_still=True)
shot('front',(0,-4,.48));shot('side',(4,0,.48));shot('back',(0,4,.48));shot('top',(0,0,4))
with open(os.path.join(render_dir,'aligned_stats.json'),'w') as f:json.dump(stats,f,indent=2)
print(json.dumps(stats,indent=2))
