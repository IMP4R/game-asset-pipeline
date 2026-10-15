import bpy,sys,os,math,json
from mathutils import Vector
src,out_dir=sys.argv[sys.argv.index('--')+1:];os.makedirs(out_dir,exist_ok=True)
MODES=[('smooth',None),('auto30',30),('auto45',45),('auto60',60)]

def run(name,angle):
 bpy.ops.wm.read_factory_settings(use_empty=True);bpy.ops.import_scene.gltf(filepath=src)
 objs=[o for o in bpy.context.scene.objects if o.type=='MESH'];objs.sort(key=lambda o:len(o.data.polygons),reverse=True);body=objs[0]
 for o in objs:
  bpy.ops.object.select_all(action='DESELECT');o.select_set(True);bpy.context.view_layer.objects.active=o
  # Use Blender 4.5's stock Object shading commands only.
  if angle is None:bpy.ops.object.shade_smooth(keep_sharp_edges=False)
  else:bpy.ops.object.shade_smooth_by_angle(angle=math.radians(angle),keep_sharp_edges=False)
 def mat(n,c):
  m=bpy.data.materials.new(n);m.use_nodes=True;b=m.node_tree.nodes['Principled BSDF'];b.inputs['Base Color'].default_value=c;b.inputs['Roughness'].default_value=.78;b.inputs['Specular IOR Level'].default_value=.2;return m
 orange=mat('Orange PBR',(1,.29,.012,1));black=mat('Black PBR',(.035,.043,.057,1))
 for o in objs:o.data.materials.clear();o.data.materials.append(orange if o==body else black)
 sc=bpy.context.scene;sc.render.engine='BLENDER_EEVEE_NEXT';sc.render.resolution_x=560;sc.render.resolution_y=560;sc.render.resolution_percentage=100;sc.render.image_settings.file_format='PNG';sc.view_settings.view_transform='Standard';sc.view_settings.look='Medium High Contrast';sc.world=bpy.data.worlds.new('World');sc.world.use_nodes=True;sc.world.node_tree.nodes['Background'].inputs['Color'].default_value=(.018,.022,.03,1);sc.world.node_tree.nodes['Background'].inputs['Strength'].default_value=.35
 for n,loc,en,sz in [('Key',(-4,-5,7),700,6),('Fill',(5,-2,4),350,5),('Top',(0,2,7),420,4),('Rim',(2,5,3),240,3)]:ld=bpy.data.lights.new(n,'AREA');ld.energy=en;ld.size=sz;x=bpy.data.objects.new(n,ld);sc.collection.objects.link(x);x.location=loc
 cd=bpy.data.cameras.new('Camera');cam=bpy.data.objects.new('Camera',cd);sc.collection.objects.link(cam);sc.camera=cam;cd.type='ORTHO';cd.ortho_scale=1.28;focus=Vector((0,0,.41))
 def shot(v,p):cam.location=Vector(p);cam.rotation_euler=(focus-cam.location).to_track_quat('-Z','Y').to_euler();sc.render.filepath=os.path.join(out_dir,f'{name}_{v}.png');bpy.ops.render.render(write_still=True)
 shot('front',(0,-4,.48));shot('perspective',(1.8,-2.8,1.45));shot('top',(0,0,4))
 return {'mode':name,'angle':angle,'triangles':sum(len(p.vertices)-2 for o in objs for p in o.data.polygons)}
st=[run(*m) for m in MODES];json.dump(st,open(os.path.join(out_dir,'stats.json'),'w'),indent=2);print(json.dumps(st,indent=2))
