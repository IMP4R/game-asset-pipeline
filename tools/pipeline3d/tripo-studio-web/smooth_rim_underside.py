import bpy,sys,os,json,math
from mathutils import Vector
src,out_glb,render_dir=sys.argv[sys.argv.index('--')+1:];os.makedirs(render_dir,exist_ok=True)
bpy.ops.wm.read_factory_settings(use_empty=True);bpy.ops.import_scene.gltf(filepath=src)
objs=sorted([o for o in bpy.context.scene.objects if o.type=='MESH'],key=lambda o:len(o.data.polygons),reverse=True);body=objs[0]
vg=body.vertex_groups.new(name='Rim underside noise band');selected=[]
for v in body.data.vertices:
 p=body.matrix_world@v.co;r=math.hypot(p.x,p.y)
 # Narrow underside band; fades to zero before top crown and lower shoulder.
 wz=max(0.0,1.0-abs(p.z-.721)/.030);wr=max(0.0,min(1.0,(r-.395)/.035));w=wz*wr
 if w>.01:vg.add([v.index],w,'REPLACE');selected.append((v.index,w))
bpy.ops.object.select_all(action='DESELECT');body.select_set(True);bpy.context.view_layer.objects.active=body
m=body.modifiers.new('Selective rim underside cleanup','LAPLACIANSMOOTH');m.vertex_group=vg.name;m.lambda_factor=.32;m.lambda_border=.12;m.iterations=3
for a,v in [('use_volume_preserve',True),('use_normalized',True)]:
 try:setattr(m,a,v)
 except:pass
bpy.ops.object.modifier_apply(modifier=m.name)
for o in objs:
 bpy.ops.object.select_all(action='DESELECT');o.select_set(True);bpy.context.view_layer.objects.active=o;bpy.ops.object.shade_smooth(keep_sharp_edges=False)
bpy.ops.object.select_all(action='DESELECT')
for o in objs:o.select_set(True)
bpy.ops.export_scene.gltf(filepath=out_glb,export_format='GLB',use_selection=True,export_materials='EXPORT')
def tri(o):return sum(len(p.vertices)-2 for p in o.data.polygons)
st={'triangles':sum(tri(o) for o in objs),'rim_underside_vertices_weighted':len(selected),'max_weight':max(w for _,w in selected),'operation':'selective Smooth Laplacian lambda .32 repeat 3 on Z .691-.751 exterior rim underside'};json.dump(st,open(os.path.join(render_dir,'stats.json'),'w'),indent=2)
def mat(n,c):mm=bpy.data.materials.new(n);mm.use_nodes=True;b=mm.node_tree.nodes['Principled BSDF'];b.inputs['Base Color'].default_value=c;b.inputs['Roughness'].default_value=.78;b.inputs['Specular IOR Level'].default_value=.2;return mm
orange=mat('Orange',(1,.29,.012,1));black=mat('Black',(.035,.043,.057,1))
for o in objs:o.data.materials.clear();o.data.materials.append(orange if o==body else black)
sc=bpy.context.scene;sc.render.engine='BLENDER_EEVEE_NEXT';sc.render.resolution_x=700;sc.render.resolution_y=700;sc.render.resolution_percentage=100;sc.render.image_settings.file_format='PNG';sc.view_settings.view_transform='Standard';sc.view_settings.look='Medium High Contrast';sc.world=bpy.data.worlds.new('World');sc.world.use_nodes=True;sc.world.node_tree.nodes['Background'].inputs['Color'].default_value=(.018,.022,.03,1);sc.world.node_tree.nodes['Background'].inputs['Strength'].default_value=.35
for n,l,e,s in [('Key',(-4,-5,7),700,6),('Fill',(5,-2,4),350,5),('Top',(0,2,7),420,4),('Rim',(2,5,3),240,3)]:ld=bpy.data.lights.new(n,'AREA');ld.energy=e;ld.size=s;x=bpy.data.objects.new(n,ld);sc.collection.objects.link(x);x.location=l
cd=bpy.data.cameras.new('Camera');cam=bpy.data.objects.new('Camera',cd);sc.collection.objects.link(cam);sc.camera=cam;cd.type='ORTHO';cd.ortho_scale=1.28;focus=Vector((0,0,.41))
def shot(v,p):cam.location=Vector(p);cam.rotation_euler=(focus-cam.location).to_track_quat('-Z','Y').to_euler();sc.render.filepath=os.path.join(render_dir,f'rim_{v}.png');bpy.ops.render.render(write_still=True)
shot('front',(0,-4,.48));shot('side',(4,0,.48));shot('back',(0,4,.48));shot('top',(0,0,4));shot('perspective',(1.8,-2.8,1.45));print(json.dumps(st,indent=2))
