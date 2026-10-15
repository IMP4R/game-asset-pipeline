import bpy,sys,os,json,math
import numpy as np
from mathutils import Vector
src,out_glb,render_dir=sys.argv[sys.argv.index('--')+1:];os.makedirs(render_dir,exist_ok=True)
bpy.ops.wm.read_factory_settings(use_empty=True);bpy.ops.import_scene.gltf(filepath=src)
objs=[o for o in bpy.context.scene.objects if o.type=='MESH'];objs.sort(key=lambda o:len(o.data.polygons),reverse=True);body=objs[0]
def tri(o):return sum(len(p.vertices)-2 for p in o.data.polygons)
def arr(o):return np.array([tuple(o.matrix_world@v.co) for v in o.data.vertices],float)
def residual(o):
 A=arr(o);r=np.linalg.norm(A[:,:2],axis=1);z=A[:,2];m=(z>.10)&(z<.58)&(r>.34);edges=np.linspace(z[m].min(),z[m].max(),14);res=[]
 for lo,hi in zip(edges[:-1],edges[1:]):
  q=m&(z>=lo)&(z<hi)
  if q.sum():res.extend((r[q]-np.median(r[q])).tolist())
 x=np.array(res);return float(np.sqrt(np.mean(x*x))),float(np.max(np.abs(x)))
before=residual(body)
bpy.ops.object.select_all(action='DESELECT');body.select_set(True);bpy.context.view_layer.objects.active=body
# Lifehack: Smooth Laplacian removes surface noise with minimal shape change (Blender manual, reconstruced meshes).
m=body.modifiers.new('Noise removal','LAPLACIANSMOOTH')
for a,v in [('lambda_factor',.5),('lambda_border',.5),('repeat',5),('use_volume_preserve',True),('use_preserve_volume',True),('use_normalized',True)]:
 try:setattr(m,a,v)
 except Exception:pass
bpy.ops.object.modifier_apply(modifier=m.name)
after=residual(body)
for o in objs:
 bpy.ops.object.select_all(action='DESELECT');o.select_set(True);bpy.context.view_layer.objects.active=o;bpy.ops.object.shade_smooth(keep_sharp_edges=False)
bpy.ops.object.select_all(action='DESELECT')
for o in objs:o.select_set(True)
bpy.ops.export_scene.gltf(filepath=out_glb,export_format='GLB',use_selection=True,export_materials='EXPORT')
def mat(n,c):mm=bpy.data.materials.new(n);mm.use_nodes=True;b=mm.node_tree.nodes['Principled BSDF'];b.inputs['Base Color'].default_value=c;b.inputs['Roughness'].default_value=.78;b.inputs['Specular IOR Level'].default_value=.2;return mm
orange=mat('Orange',(1,.29,.012,1));black=mat('Black',(.035,.043,.057,1))
for o in objs:o.data.materials.clear();o.data.materials.append(orange if o==body else black)
sc=bpy.context.scene;sc.render.engine='BLENDER_EEVEE_NEXT';sc.render.resolution_x=700;sc.render.resolution_y=700;sc.render.resolution_percentage=100;sc.render.image_settings.file_format='PNG';sc.view_settings.view_transform='Standard';sc.view_settings.look='Medium High Contrast';sc.world=bpy.data.worlds.new('World');sc.world.use_nodes=True;sc.world.node_tree.nodes['Background'].inputs['Color'].default_value=(.018,.022,.03,1);sc.world.node_tree.nodes['Background'].inputs['Strength'].default_value=.35
for n,l,e,s in [('Key',(-4,-5,7),700,6),('Fill',(5,-2,4),350,5),('Top',(0,2,7),420,4),('Rim',(2,5,3),240,3)]:ld=bpy.data.lights.new(n,'AREA');ld.energy=e;ld.size=s;x=bpy.data.objects.new(n,ld);sc.collection.objects.link(x);x.location=l
cd=bpy.data.cameras.new('Camera');cam=bpy.data.objects.new('Camera',cd);sc.collection.objects.link(cam);sc.camera=cam;cd.type='ORTHO';cd.ortho_scale=1.28;focus=Vector((0,0,.41))
def shot(v,p):cam.location=Vector(p);cam.rotation_euler=(focus-cam.location).to_track_quat('-Z','Y').to_euler();sc.render.filepath=os.path.join(render_dir,f'lap_{v}.png');bpy.ops.render.render(write_still=True)
shot('front',(0,-4,.48));shot('side',(4,0,.48));shot('back',(0,4,.48));shot('top',(0,0,4));shot('perspective',(1.8,-2.8,1.45))
st={'triangles':sum(tri(o) for o in objs),'body_wall_residual_rms_before':before[0],'body_wall_residual_rms_after':after[0],'body_wall_residual_max_before':before[1],'body_wall_residual_max_after':after[1],'modifier':'SMOOTH_LAPLACIAN lambda .5 border .5 repeat 5 volume preserved'};json.dump(st,open(os.path.join(render_dir,'stats.json'),'w'),indent=2);print(json.dumps(st,indent=2))
