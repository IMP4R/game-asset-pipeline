import bpy,bmesh,sys,os,json,math
from mathutils import Vector
dense_path,low_path,out_path,render_dir=sys.argv[sys.argv.index('--')+1:];os.makedirs(render_dir,exist_ok=True)
bpy.ops.wm.read_factory_settings(use_empty=True)
# Dense cleaned Tripo donor.
bpy.ops.import_scene.gltf(filepath=dense_path);dense=[o for o in bpy.context.scene.objects if o.type=='MESH'];dense.sort(key=lambda o:len(o.data.polygons),reverse=True);donor=dense[0];donor.name='Dense_Tripo_Normal_Donor'
for o in dense:o.hide_render=True;o.hide_viewport=True
# Import complete 996-triangle projected asset.
prior=set(bpy.context.scene.objects);bpy.ops.import_scene.gltf(filepath=low_path);low=[o for o in bpy.context.scene.objects if o.type=='MESH' and o not in prior];low.sort(key=lambda o:len(o.data.polygons),reverse=True);body=low[0]
# Blender-native high-to-low custom-normal transfer. No topology or vertex movement.
for p in donor.data.polygons:p.use_smooth=True
for p in body.data.polygons:p.use_smooth=True
bpy.ops.object.select_all(action='DESELECT');body.hide_viewport=False;body.select_set(True);bpy.context.view_layer.objects.active=body
mod=body.modifiers.new('Dense Tripo source normals','DATA_TRANSFER');mod.object=donor;mod.use_loop_data=True;mod.data_types_loops={'CUSTOM_NORMAL'};mod.loop_mapping='POLYINTERP_NEAREST';mod.mix_mode='REPLACE';mod.mix_factor=1.0;bpy.ops.object.modifier_apply(modifier=mod.name)
# Other source components use Blender stock auto smooth.
for o in low[1:]:
 for p in o.data.polygons:p.use_smooth=True
 bpy.ops.object.select_all(action='DESELECT');o.select_set(True);bpy.context.view_layer.objects.active=o;bpy.ops.object.shade_smooth_by_angle(angle=math.radians(45),keep_sharp_edges=False)
# Export only final low components.
bpy.ops.object.select_all(action='DESELECT')
for o in low:o.select_set(True)
bpy.ops.export_scene.gltf(filepath=out_path,export_format='GLB',use_selection=True,export_materials='EXPORT',export_normals=True)
def tri(o):return sum(len(p.vertices)-2 for p in o.data.polygons)
st={'method':'Blender Data Transfer custom normals from dense cleaned Tripo body','triangles':sum(tri(o) for o in low),'component_triangles':[tri(o) for o in low],'body_vertices':len(body.data.vertices),'geometry_changed':False,'normal_donor_triangles':tri(donor)};json.dump(st,open(os.path.join(render_dir,'stats.json'),'w'),indent=2)
# Hide donor and render with continuous matte PBR.
for o in dense:o.hide_render=True
def mat(n,c):m=bpy.data.materials.new(n);m.use_nodes=True;b=m.node_tree.nodes['Principled BSDF'];b.inputs['Base Color'].default_value=c;b.inputs['Roughness'].default_value=.78;b.inputs['Specular IOR Level'].default_value=.2;return m
orange=mat('Orange',(1,.29,.012,1));black=mat('Black',(.035,.043,.057,1))
for o in low:o.data.materials.clear();o.data.materials.append(orange if o==body else black)
sc=bpy.context.scene;sc.render.engine='BLENDER_EEVEE_NEXT';sc.render.resolution_x=700;sc.render.resolution_y=700;sc.render.resolution_percentage=100;sc.render.image_settings.file_format='PNG';sc.view_settings.view_transform='Standard';sc.view_settings.look='Medium High Contrast';sc.world=bpy.data.worlds.new('World');sc.world.use_nodes=True;sc.world.node_tree.nodes['Background'].inputs['Color'].default_value=(.018,.022,.03,1);sc.world.node_tree.nodes['Background'].inputs['Strength'].default_value=.35
for n,l,e,s in [('Key',(-4,-5,7),700,6),('Fill',(5,-2,4),350,5),('Top',(0,2,7),420,4),('Rim',(2,5,3),240,3)]:ld=bpy.data.lights.new(n,'AREA');ld.energy=e;ld.size=s;x=bpy.data.objects.new(n,ld);sc.collection.objects.link(x);x.location=l
cd=bpy.data.cameras.new('Camera');cam=bpy.data.objects.new('Camera',cd);sc.collection.objects.link(cam);sc.camera=cam;cd.type='ORTHO';cd.ortho_scale=1.28;focus=Vector((0,0,.41))
def shot(v,p):cam.location=Vector(p);cam.rotation_euler=(focus-cam.location).to_track_quat('-Z','Y').to_euler();sc.render.filepath=os.path.join(render_dir,f'transfer_{v}.png');bpy.ops.render.render(write_still=True)
shot('front',(0,-4,.48));shot('side',(4,0,.48));shot('back',(0,4,.48));shot('top',(0,0,4));shot('perspective',(1.8,-2.8,1.45));print(json.dumps(st,indent=2))
