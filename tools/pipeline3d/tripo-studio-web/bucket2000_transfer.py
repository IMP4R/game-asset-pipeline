import bpy,sys,os
run='/Users/user0/godot-hybrid-casual/tools/pipeline3d/runs/2026-09-02-tripo-bucket-v1'
hi_glb=run+'/tripo_geometry_clean_smoothed.glb'
lo_glb=run+'/bucket_2000_base.glb'
out_glb=run+'/bucket_half_round.glb'
out_dir=run+'/lightweight_test/bucket_half'
os.makedirs(out_dir,exist_ok=True)
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=hi_glb)
before=set(o.name for o in bpy.context.scene.objects)
bpy.ops.import_scene.gltf(filepath=lo_glb)
lows=[o for o in bpy.context.scene.objects if o.type=='MESH' and o.name not in before]
highs=[o for o in bpy.context.scene.objects if o.type=='MESH' and o.name in before and len(o.data.vertices)>=20]
def bb(o):
 ws=[o.matrix_world@v.co for v in o.data.vertices]
 return [(min(w[i] for w in ws),max(w[i] for w in ws)) for i in range(3)]
def inter(a,b):
 A,B=bb(a),bb(b);v=1
 for i in range(3):v*=max(0,min(A[i][1],B[i][1])-max(A[i][0],B[i][0]))
 return v
pairs=[]
for lo in lows:
 best=max(highs,key=lambda hi:inter(lo,hi))
 pairs.append((lo,best))
print('pairs:',[(lo.name,hi.name) for lo,hi in pairs])
for lo,hi in pairs:
 lo.location.y+=1.2 if ('handle' in lo.name.lower() or 'pivot' in lo.name.lower()) else 0
 hi.location.y+=1.2 if ('handle' in lo.name.lower() or 'pivot' in lo.name.lower()) else 0
bpy.context.view_layer.update()
for lo,hi in pairs:
 bpy.ops.object.select_all(action='DESELECT')
 hi.select_set(True);lo.select_set(True);bpy.context.view_layer.objects.active=lo
 bpy.ops.object.data_transfer(data_type='CUSTOM_NORMAL',loop_mapping='POLYINTERP_NEAREST',use_object_transform=True,use_create=True)
 lo.select_set(False)
for lo,hi in pairs:
 d=1.2 if ('handle' in lo.name.lower() or 'pivot' in lo.name.lower()) else 0
 lo.location.y-=d;hi.location.y-=d
bpy.ops.object.select_all(action='DESELECT')
for o in highs:o.select_set(True)
bpy.ops.object.delete()
from mathutils import Vector
def mat2(n,c):
 m=bpy.data.materials.new(n);m.use_nodes=True;b=m.node_tree.nodes['Principled BSDF'];b.inputs['Base Color'].default_value=c;b.inputs['Roughness'].default_value=.78;b.inputs['Specular IOR Level'].default_value=.2;return m
orange=mat2('Orange',(1,.29,.012,1));black=mat2('Black',(.035,.043,.057,1))
for o in lows:
 o.data.materials.clear();o.data.materials.append(orange if ('Body' in o.name or 'Rim' in o.name) else black)
 o.visible_shadow=False
sc=bpy.context.scene;sc.render.engine='BLENDER_EEVEE_NEXT';sc.render.resolution_x=700;sc.render.resolution_y=700;sc.render.resolution_percentage=100;sc.render.image_settings.file_format='PNG';sc.view_settings.view_transform='Standard';sc.view_settings.look='Medium High Contrast';sc.world=bpy.data.worlds.new('World');sc.world.use_nodes=True;sc.world.node_tree.nodes['Background'].inputs['Color'].default_value=(.018,.022,.03,1);sc.world.node_tree.nodes['Background'].inputs['Strength'].default_value=.55
for n,l,e,s in [('Key',(-4,-5,7),700,6),('Fill',(5,-2,4),450,5),('Top',(0,2,7),420,4),('Rim',(2,5,3),240,3)]:ld=bpy.data.lights.new(n,'AREA');ld.energy=e;ld.size=s;x=bpy.data.objects.new(n,ld);sc.collection.objects.link(x);x.location=l
cd=bpy.data.cameras.new('Camera');cam=bpy.data.objects.new('Camera',cd);sc.collection.objects.link(cam);sc.camera=cam;cd.type='ORTHO';cd.ortho_scale=1.28;focus=Vector((0,0,.41))
def shot(v,p):cam.location=Vector(p);cam.rotation_euler=(focus-cam.location).to_track_quat('-Z','Y').to_euler();sc.render.filepath=os.path.join(out_dir,f'round_{v}.png');bpy.ops.render.render(write_still=True)
shot('front',(0,-4,.48));shot('perspective',(1.8,-2.8,1.45));shot('top',(0,0,4))
bpy.ops.object.select_all(action='DESELECT')
for o in lows:o.select_set(True)
bpy.ops.export_scene.gltf(filepath=out_glb,export_format='GLB',use_selection=True,export_materials='EXPORT')
tri=sum(len(p.vertices)-2 for o in lows for p in o.data.polygons)
print('NORMAL TRANSFER OK triangles:',tri,'glb:',out_glb)
