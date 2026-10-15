import bpy,sys,os,json,math
from mathutils import Vector
src,out_glb,out_blend,render_dir=sys.argv[sys.argv.index('--')+1:];os.makedirs(render_dir,exist_ok=True)
bpy.ops.wm.read_factory_settings(use_empty=True);bpy.ops.import_scene.gltf(filepath=src)
objs=[o for o in bpy.context.scene.objects if o.type=='MESH'];objs.sort(key=lambda o:len(o.data.polygons),reverse=True)
body=objs[0];handle=max(objs[1:],key=lambda o:len(o.data.polygons));pivots=[o for o in objs if o not in (body,handle)]
# Angle-controlled split normals: keep curved bands smooth, but stop interpolation across structural creases.
angles={body:math.radians(38),handle:math.radians(48)}
for o in objs:
 for p in o.data.polygons:p.use_smooth=True
 if o in pivots:
  # Tiny low-poly caps read better with hard side/cap breaks.
  for p in o.data.polygons:p.use_smooth=(abs(p.normal.x)<.72)
 else:
  mod=o.modifiers.new('Angle controlled normals','NODES') if False else None
  # Blender 4.1+: operator creates sharp edges from angle; Smooth by Angle consumes them without adding geometry.
  bpy.context.view_layer.objects.active=o;o.select_set(True)
  bpy.ops.object.mode_set(mode='EDIT');bpy.ops.mesh.select_all(action='SELECT');bpy.ops.mesh.mark_sharp(clear=True);bpy.ops.object.mode_set(mode='OBJECT')
  for e in o.data.edges:
   fs=[p for p in o.data.polygons if e.vertices[0] in p.vertices and e.vertices[1] in p.vertices]
   if len(fs)==2 and fs[0].normal.angle(fs[1].normal)>angles[o]:e.use_edge_sharp=True
  o.select_set(False)
# Reusable toon nodes for Blender preview; geometry and normal splits export to GLB, shader nodes stay in .blend.
def toon(name,base,shadow,light):
 m=bpy.data.materials.new(name);m.use_nodes=True;n=m.node_tree.nodes;n.clear();out=n.new('ShaderNodeOutputMaterial');diff=n.new('ShaderNodeBsdfDiffuse');diff.inputs['Color'].default_value=base;diff.inputs['Roughness'].default_value=.82;toon=n.new('ShaderNodeShaderToRGB');ramp=n.new('ShaderNodeValToRGB');ramp.color_ramp.interpolation='CONSTANT';ramp.color_ramp.elements.remove(ramp.color_ramp.elements[1]);e0=ramp.color_ramp.elements[0];e0.position=.18;e0.color=shadow;e1=ramp.color_ramp.elements.new(.38);e1.color=base;e2=ramp.color_ramp.elements.new(.76);e2.color=light;m.node_tree.links.new(diff.outputs[0],toon.inputs[0]);m.node_tree.links.new(toon.outputs[0],ramp.inputs[0]);m.node_tree.links.new(ramp.outputs[0],out.inputs[0]);return m
orange=toon('TOON_Orange',(1.0,.48,.025,1),(.58,.105,.006,1),(1.0,.82,.22,1));black=toon('TOON_Handle',(.095,.11,.14,1),(.018,.024,.036,1),(.34,.37,.43,1))
for o in objs:
 o.data.materials.clear();o.data.materials.append(orange if o==body else black)
# Save editable toon preview first.
bpy.ops.wm.save_as_mainfile(filepath=out_blend)
# GLB cannot carry Shader-to-RGB nodes; substitute matching matte PBR base while preserving sharp-edge normals.
for mat,color in [(orange,(1.0,.32,.015,1)),(black,(.055,.062,.075,1))]:
 mat.node_tree.nodes.clear();out=mat.node_tree.nodes.new('ShaderNodeOutputMaterial');bs=mat.node_tree.nodes.new('ShaderNodeBsdfPrincipled');bs.inputs['Base Color'].default_value=color;bs.inputs['Roughness'].default_value=.86;bs.inputs['Specular IOR Level'].default_value=.18;mat.node_tree.links.new(bs.outputs[0],out.inputs[0])
for o in objs:o.select_set(True)
bpy.ops.export_scene.gltf(filepath=out_glb,export_format='GLB',use_selection=True,export_materials='EXPORT')
# Restore toon materials in memory by re-opening blend for render.
bpy.ops.wm.open_mainfile(filepath=out_blend);objs=[o for o in bpy.context.scene.objects if o.type=='MESH']
sc=bpy.context.scene;sc.render.engine='BLENDER_EEVEE_NEXT';sc.render.resolution_x=720;sc.render.resolution_y=720;sc.render.resolution_percentage=100;sc.render.image_settings.file_format='PNG';sc.view_settings.view_transform='Standard';sc.view_settings.look='Medium High Contrast';sc.render.film_transparent=False
sc.world=bpy.data.worlds.new('Toon World');sc.world.use_nodes=True;sc.world.node_tree.nodes['Background'].inputs['Color'].default_value=(.015,.019,.027,1);sc.world.node_tree.nodes['Background'].inputs['Strength'].default_value=.22
# One large key creates readable bands; weak fill prevents black crush.
for n,loc,en,sz in [('Toon Key',(-3,-4,7),1100,5.5),('Soft Fill',(4,-1,3),180,4)]:ld=bpy.data.lights.new(n,'AREA');ld.energy=en;ld.size=sz;x=bpy.data.objects.new(n,ld);sc.collection.objects.link(x);x.location=loc
cd=bpy.data.cameras.new('Camera');cam=bpy.data.objects.new('Camera',cd);sc.collection.objects.link(cam);sc.camera=cam;cd.type='ORTHO';cd.ortho_scale=1.28;focus=Vector((0,0,.41))
def shot(n,pos):cam.location=Vector(pos);cam.rotation_euler=(focus-cam.location).to_track_quat('-Z','Y').to_euler();sc.render.filepath=os.path.join(render_dir,f'toon_{n}.png');bpy.ops.render.render(write_still=True)
shot('front',(0,-4,.48));shot('side',(4,0,.48));shot('top',(0,0,4));shot('perspective',(1.8,-2.8,1.45))
print(json.dumps({'triangles':sum(len(p.vertices)-2 for o in objs for p in o.data.polygons),'body_smooth_angle_deg':38,'handle_smooth_angle_deg':48,'outputs':[out_glb,out_blend]},indent=2))
