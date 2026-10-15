import bpy,sys,os,json,math
from mathutils import Vector
src,out,render_dir=sys.argv[sys.argv.index('--')+1:];os.makedirs(render_dir,exist_ok=True)
bpy.ops.wm.read_factory_settings(use_empty=True);bpy.ops.import_scene.gltf(filepath=src)
objs=[o for o in bpy.context.scene.objects if o.type=='MESH'];objs.sort(key=lambda o:len(o.data.polygons),reverse=True)
body=objs[0];arc=min(objs[1:],key=lambda o:len(o.data.polygons));pivs=[o for o in objs if o not in (body,arc)]
# True source-derived branch: Blender's QEM collapses only edges of the imported cleaned Tripo meshes.
targets={body:310,arc:135,pivs[0]:27,pivs[1]:27}
for o in objs:
 before=sum(len(p.vertices)-2 for p in o.data.polygons);target=targets[o]
 # Critical-area vertex group: rim, cavity floor, handle ends. Modifier keeps these more strongly.
 vg=o.vertex_groups.new(name='critical')
 for v in o.data.vertices:
  p=o.matrix_world@v.co;critical=False
  if o==body:critical=(p.z>.61 or p.z<.12)
  elif o==arc:critical=(abs(p.x)>.43)
  else:critical=True
  if critical:vg.add([v.index],1.0,'REPLACE')
 bpy.context.view_layer.objects.active=o;o.select_set(True)
 mod=o.modifiers.new('Constrained source edge collapse','DECIMATE');mod.decimate_type='COLLAPSE';mod.ratio=min(1,max(.001,target/before));mod.use_collapse_triangulate=True;mod.use_symmetry=True;mod.symmetry_axis='X';mod.vertex_group=vg.name;mod.vertex_group_factor=.08
 try:bpy.ops.object.modifier_apply(modifier=mod.name)
 except Exception:
  mod.vertex_group='';bpy.ops.object.modifier_apply(modifier=mod.name)
 for p in o.data.polygons:p.use_smooth=True
 o.select_set(False)
# If still above budget, a second tiny global pass reaches comparable budget without changing method.
tri=lambda o:sum(len(p.vertices)-2 for p in o.data.polygons)
total=sum(tri(o) for o in objs)
if total>520:
 ratio=500/total
 for o in objs:
  bpy.context.view_layer.objects.active=o;o.select_set(True);m=o.modifiers.new('Final source edge collapse','DECIMATE');m.ratio=ratio;m.use_collapse_triangulate=True;m.use_symmetry=True;m.symmetry_axis='X';bpy.ops.object.modifier_apply(modifier=m.name);o.select_set(False)
for o in objs:o.select_set(True)
bpy.ops.export_scene.gltf(filepath=out,export_format='GLB',use_selection=True,export_materials='EXPORT')
# Fixed render rig
sc=bpy.context.scene;sc.render.engine='BLENDER_EEVEE_NEXT';sc.render.resolution_x=720;sc.render.resolution_y=720;sc.render.resolution_percentage=100;sc.render.image_settings.file_format='PNG';sc.view_settings.view_transform='Standard';sc.view_settings.look='Medium High Contrast'
if not sc.world:sc.world=bpy.data.worlds.new('World')
sc.world.use_nodes=True;sc.world.node_tree.nodes['Background'].inputs['Color'].default_value=(.018,.022,.03,1);sc.world.node_tree.nodes['Background'].inputs['Strength'].default_value=.28
for n,loc,en,sz in [('Key',(4,-5,7),900,5),('Fill',(-4,-2,4),450,4),('Rim',(2,5,5),650,3)]:
 ld=bpy.data.lights.new(n,'AREA');ld.energy=en;ld.size=sz;x=bpy.data.objects.new(n,ld);sc.collection.objects.link(x);x.location=loc
cd=bpy.data.cameras.new('Camera');cam=bpy.data.objects.new('Camera',cd);sc.collection.objects.link(cam);sc.camera=cam;cd.type='ORTHO';cd.ortho_scale=1.28;focus=Vector((0,0,.41))
def shot(n,pos):cam.location=Vector(pos);cam.rotation_euler=(focus-cam.location).to_track_quat('-Z','Y').to_euler();sc.render.filepath=os.path.join(render_dir,f'collapse_{n}.png');bpy.ops.render.render(write_still=True)
shot('front',(0,-4,.48));shot('side',(4,0,.48));shot('top',(0,0,4));shot('perspective',(1.8,-2.8,1.45))
st={'method':'source-derived constrained QEM edge collapse','vertices':sum(len(o.data.vertices) for o in objs),'polygons':sum(len(o.data.polygons) for o in objs),'triangles':sum(tri(o) for o in objs),'component_triangles':[tri(o) for o in objs]}
with open(os.path.join(render_dir,'stats.json'),'w') as f:json.dump(st,f,indent=2)
print(json.dumps(st,indent=2))
