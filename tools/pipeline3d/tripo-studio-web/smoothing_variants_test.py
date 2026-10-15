import bpy,bmesh,sys,os,json,math,time
from mathutils import Vector
glb,out_dir=sys.argv[sys.argv.index('--')+1:];os.makedirs(out_dir,exist_ok=True)
MODES=[('flat','FULL FLAT'),('angle30','AUTO 30'),('angle45','AUTO 45')]

def load():
 bpy.ops.wm.read_factory_settings(use_empty=True);bpy.ops.import_scene.gltf(filepath=glb);return [o for o in bpy.context.scene.objects if o.type=='MESH']

def mark_base_rings(body):
 bm=bmesh.new();bm.from_mesh(body.data);n=0
 for e in bm.edges:
  if len(e.link_faces)!=2:continue
  zs=[(body.matrix_world@v.co).z for v in e.verts];rs=[math.hypot(*((body.matrix_world@v.co).xy)) for v in e.verts]
  bottom=max(zs)<.012 and min(zs)>-.012 and min(rs)>.3
  floor=min(zs)>.02 and max(zs)<.06 and min(rs)>.3
  if bottom or floor:e.use_edge_sharp=True;n+=1
 bm.to_mesh(body.data);bm.free();body.data.update();return n

def shade(mode,objs):
 for o in objs:
  bpy.ops.object.select_all(action='DESELECT');o.select_set(True);bpy.context.view_layer.objects.active=o
  if mode=='flat':
   for p in o.data.polygons:p.use_smooth=False
  elif mode=='smooth':bpy.ops.object.shade_smooth(keep_sharp_edges=False)
  elif mode=='angle30':bpy.ops.object.shade_smooth_by_angle(angle=math.radians(30),keep_sharp_edges=False)
  elif mode=='angle45':bpy.ops.object.shade_smooth_by_angle(angle=math.radians(45),keep_sharp_edges=False)
  elif mode=='rounded':
   body=[x for x in objs if 'Body' in x.name][0];mark_base_rings(body)
   bpy.ops.object.shade_smooth_by_angle(angle=math.radians(89),keep_sharp_edges=True)

def render(mode):
 objs=load();shade(mode,objs)
 def mat(n,c):m=bpy.data.materials.new(n);m.use_nodes=True;b=m.node_tree.nodes['Principled BSDF'];b.inputs['Base Color'].default_value=c;b.inputs['Roughness'].default_value=.78;b.inputs['Specular IOR Level'].default_value=.2;return m
 orange=mat('Orange',(1,.29,.012,1));black=mat('Black',(.035,.043,.057,1))
 for o in objs:o.data.materials.clear();o.data.materials.append(orange if ('Body' in o.name or 'Rim' in o.name) else black)
 sc=bpy.context.scene;sc.render.engine='BLENDER_EEVEE_NEXT';sc.render.resolution_x=600;sc.render.resolution_y=600;sc.render.resolution_percentage=100;sc.render.image_settings.file_format='PNG';sc.view_settings.view_transform='Standard';sc.view_settings.look='Medium High Contrast';sc.world=bpy.data.worlds.new('World');sc.world.use_nodes=True;sc.world.node_tree.nodes['Background'].inputs['Color'].default_value=(.018,.022,.03,1);sc.world.node_tree.nodes['Background'].inputs['Strength'].default_value=.35
 for n,l,e,s in [('Key',(-4,-5,7),700,6),('Fill',(5,-2,4),350,5),('Top',(0,2,7),420,4),('Rim',(2,5,3),240,3)]:ld=bpy.data.lights.new(n,'AREA');ld.energy=e;ld.size=s;x=bpy.data.objects.new(n,ld);sc.collection.objects.link(x);x.location=l
 cd=bpy.data.cameras.new('Camera');cam=bpy.data.objects.new('Camera',cd);sc.collection.objects.link(cam);sc.camera=cam;cd.type='ORTHO';cd.ortho_scale=1.28;focus=Vector((0,0,.41))
 def shot(v,p):cam.location=Vector(p);cam.rotation_euler=(focus-cam.location).to_track_quat('-Z','Y').to_euler();sc.render.filepath=os.path.join(out_dir,f'{mode}_{v}.png');bpy.ops.render.render(write_still=True)
 shot('front',(0,-4,.48));shot('perspective',(1.8,-2.8,1.45));shot('top',(0,0,4))
tri=None
st={}
for m,_ in MODES:
 objs=load();tri=sum(len(p.vertices)-2 for o in objs for p in o.data.polygons);st[m]=tri
 render(m)
json.dump(st,open(os.path.join(out_dir,'stats.json'),'w'),indent=2);print(json.dumps(st,indent=2))
