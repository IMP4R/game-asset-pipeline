import bpy,sys,os,json,math
from mathutils import Vector
inp,out_glb,render_dir=sys.argv[sys.argv.index('--')+1:];os.makedirs(render_dir,exist_ok=True)
bpy.ops.wm.read_factory_settings(use_empty=True);bpy.ops.wm.obj_import(filepath=inp)
objs=[o for o in bpy.context.scene.objects if o.type=='MESH']
for o in objs:o.select_set(True)
bpy.context.view_layer.objects.active=objs[0];bpy.ops.object.join();o=bpy.context.object;o.name='MeshAnything_Neural_Output'
# MeshAnything output is normalized to roughly [-.5,.5] with input preferred Y-up. Restore Z-up and cleaned-input dimensions.
o.rotation_euler[0]=-math.pi/2;bpy.ops.object.transform_apply(location=False,rotation=True,scale=False)
pts=[o.matrix_world@v.co for v in o.data.vertices];mn=Vector((min(p.x for p in pts),min(p.y for p in pts),min(p.z for p in pts)));mx=Vector((max(p.x for p in pts),max(p.y for p in pts),max(p.z for p in pts)));dims=mx-mn
target=Vector((1.02,1.02,.724));s=min(target.x/max(dims.x,1e-6),target.y/max(dims.y,1e-6),target.z/max(dims.z,1e-6));o.scale=(s,s,s);bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
pts=[o.matrix_world@v.co for v in o.data.vertices];mn=Vector((min(p.x for p in pts),min(p.y for p in pts),min(p.z for p in pts)));mx=Vector((max(p.x for p in pts),max(p.y for p in pts),max(p.z for p in pts)));o.location-=Vector(((mn.x+mx.x)/2,(mn.y+mx.y)/2,mn.z))
def lin(v):v/=255;return v/12.92 if v<=.04045 else ((v+.055)/1.055)**2.4
m=bpy.data.materials.new('MeshAnything Orange');m.use_nodes=True;b=m.node_tree.nodes['Principled BSDF'];b.inputs['Base Color'].default_value=(*(lin(int('FF8E00'[i:i+2],16)) for i in (0,2,4)),1);b.inputs['Roughness'].default_value=.52;o.data.materials.clear();o.data.materials.append(m)
for p in o.data.polygons:p.use_smooth=True
bpy.ops.export_scene.gltf(filepath=out_glb,export_format='GLB',use_selection=True,export_materials='EXPORT')
tri=sum(len(p.vertices)-2 for p in o.data.polygons)
sc=bpy.context.scene;sc.render.engine='BLENDER_EEVEE_NEXT';sc.render.resolution_x=720;sc.render.resolution_y=720;sc.render.resolution_percentage=100;sc.render.image_settings.file_format='PNG';sc.view_settings.view_transform='Standard';sc.view_settings.look='Medium High Contrast';sc.world=bpy.data.worlds.new('World');sc.world.use_nodes=True;sc.world.node_tree.nodes['Background'].inputs['Color'].default_value=(.018,.022,.03,1);sc.world.node_tree.nodes['Background'].inputs['Strength'].default_value=.28
for n,loc,en,sz in [('Key',(4,-5,7),900,5),('Fill',(-4,-2,4),450,4),('Rim',(2,5,5),650,3)]:ld=bpy.data.lights.new(n,'AREA');ld.energy=en;ld.size=sz;x=bpy.data.objects.new(n,ld);sc.collection.objects.link(x);x.location=loc
cd=bpy.data.cameras.new('Camera');cam=bpy.data.objects.new('Camera',cd);sc.collection.objects.link(cam);sc.camera=cam;cd.type='ORTHO';cd.ortho_scale=1.28;focus=Vector((0,0,.41))
def shot(n,pos):cam.location=Vector(pos);cam.rotation_euler=(focus-cam.location).to_track_quat('-Z','Y').to_euler();sc.render.filepath=os.path.join(render_dir,f'meshanything_{n}.png');bpy.ops.render.render(write_still=True)
shot('front',(0,-4,.48));shot('side',(4,0,.48));shot('top',(0,0,4));shot('perspective',(1.8,-2.8,1.45))
with open(os.path.join(render_dir,'stats.json'),'w') as f:json.dump({'method':'official MeshAnything 350m with MPS eager-attention port','vertices':len(o.data.vertices),'polygons':len(o.data.polygons),'triangles':tri},f,indent=2)
print(json.dumps({'triangles':tri,'vertices':len(o.data.vertices)},indent=2))
