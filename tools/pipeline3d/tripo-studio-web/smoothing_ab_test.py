import bpy,sys,os,math,json
from mathutils import Vector
src,out_dir=sys.argv[sys.argv.index('--')+1:];os.makedirs(out_dir,exist_ok=True)
MODES=[('flat',0,False),('angle30',30,False),('angle50',50,False),('weighted50',50,True)]

def setup(mode,deg,weighted):
 bpy.ops.wm.read_factory_settings(use_empty=True);bpy.ops.import_scene.gltf(filepath=src)
 objs=[o for o in bpy.context.scene.objects if o.type=='MESH'];objs.sort(key=lambda o:len(o.data.polygons),reverse=True);body=objs[0];handle=max(objs[1:],key=lambda o:len(o.data.polygons))
 for o in objs:
  # clear any imported custom normals and sharp flags so every branch starts identically
  for e in o.data.edges:e.use_edge_sharp=False
  for p in o.data.polygons:p.use_smooth=(mode!='flat')
  if mode!='flat':
   # Structural split by actual dihedral angle. No geometry changes.
   limit=math.radians(deg)
   for e in o.data.edges:
    fs=[p for p in o.data.polygons if e.vertices[0] in p.vertices and e.vertices[1] in p.vertices]
    if len(fs)==2 and fs[0].normal.angle(fs[1].normal)>limit:e.use_edge_sharp=True
  if weighted:
   bpy.context.view_layer.objects.active=o;o.select_set(True)
   try:
    m=o.modifiers.new('Weighted corner normals','WEIGHTED_NORMAL');m.keep_sharp=True;m.weight=50;m.thresh=.01;bpy.ops.object.modifier_apply(modifier=m.name)
   except Exception:pass
   o.select_set(False)
 # ordinary matte PBR, no Shader-to-RGB and no quantization
 def pbr(name,color):
  m=bpy.data.materials.new(name);m.use_nodes=True;b=m.node_tree.nodes.get('Principled BSDF');b.inputs['Base Color'].default_value=color;b.inputs['Roughness'].default_value=.78;b.inputs['Specular IOR Level'].default_value=.2;return m
 orange=pbr('Orange PBR',(1.0,.29,.012,1));black=pbr('Black PBR rez',(.035,.043,.057,1))
 for o in objs:o.data.materials.clear();o.data.materials.append(orange if o==body else black)
 sc=bpy.context.scene;sc.render.engine='BLENDER_EEVEE_NEXT';sc.render.resolution_x=560;sc.render.resolution_y=560;sc.render.resolution_percentage=100;sc.render.image_settings.file_format='PNG';sc.view_settings.view_transform='Standard';sc.view_settings.look='Medium High Contrast';sc.world=bpy.data.worlds.new('World');sc.world.use_nodes=True;sc.world.node_tree.nodes['Background'].inputs['Color'].default_value=(.018,.022,.03,1);sc.world.node_tree.nodes['Background'].inputs['Strength'].default_value=.35
 # Broad multi-light rig produces continuous gradients and exposes normal discontinuities.
 for n,loc,en,sz in [('Key',(-4,-5,7),700,6),('Fill',(5,-2,4),350,5),('Top',(0,2,7),420,4),('Rim',(2,5,3),240,3)]:ld=bpy.data.lights.new(n,'AREA');ld.energy=en;ld.size=sz;x=bpy.data.objects.new(n,ld);sc.collection.objects.link(x);x.location=loc
 cd=bpy.data.cameras.new('Camera');cam=bpy.data.objects.new('Camera',cd);sc.collection.objects.link(cam);sc.camera=cam;cd.type='ORTHO';cd.ortho_scale=1.28;focus=Vector((0,0,.41))
 def shot(view,pos):cam.location=Vector(pos);cam.rotation_euler=(focus-cam.location).to_track_quat('-Z','Y').to_euler();sc.render.filepath=os.path.join(out_dir,f'{mode}_{view}.png');bpy.ops.render.render(write_still=True)
 shot('front',(0,-4,.48));shot('side',(4,0,.48));shot('top',(0,0,4));shot('perspective',(1.8,-2.8,1.45))
 return {'mode':mode,'angle':deg,'weighted':weighted,'triangles':sum(len(p.vertices)-2 for o in objs for p in o.data.polygons)}
st=[setup(*x) for x in MODES]
with open(os.path.join(out_dir,'stats.json'),'w') as f:json.dump(st,f,indent=2)
print(json.dumps(st,indent=2))
