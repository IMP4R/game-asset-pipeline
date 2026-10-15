import bpy,sys,os
run='/Users/user0/godot-hybrid-casual/tools/pipeline3d/runs/2026-09-02-tripo-bucket-v1'
hi_glb=run+'/bucket_clay_smooth.glb'
lo_glb=run+'/bucket_lowpoly_300.glb'
out_glb=run+'/bucket_lowpoly_300_round.glb'
out_dir=run+'/lightweight_test/round_bake'
os.makedirs(out_dir,exist_ok=True)

def bbox(o):
 ws=[o.matrix_world@v.co for v in o.data.vertices]
 mn=[min(w[i] for w in ws) for i in range(3)];mx=[max(w[i] for w in ws) for i in range(3)]
 return mn,mx
def inter(a,b):
 (amn,amx),(bmn,bmx)=bbox(a),bbox(b)
 v=1
 for i in range(3):v*=max(0,min(amx[i],bmx[i])-max(amn[i],bmn[i]))
 return v

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=hi_glb)
highs=[o for o in bpy.context.scene.objects if o.type=='MESH' and len(o.data.vertices)>=20]
before=set(o.name for o in bpy.context.scene.objects)
bpy.ops.import_scene.gltf(filepath=lo_glb)
lows=[o for o in bpy.context.scene.objects if o.type=='MESH' and o.name not in before]
pairs=[]
for lo in lows:
 for hi in highs:pairs.append((inter(lo,hi),lo,hi))
pairs.sort(key=lambda p:-p[0])
used_h=set();mmap={}
for v,lo,hi in pairs:
 if lo in mmap or hi in used_h:continue
 mmap[lo]=hi;used_h.add(hi)
print('pairs:',[(lo.name,hi.name) for lo,hi in mmap.items()])
# inflate high poly outward along world normals (polycount trick: prevents backface hits)
import bmesh
for hi in set(hi for hi in mmap.values()):
 M=hi.matrix_world;Mi=M.inverted()
 bm=bmesh.new();bm.from_mesh(hi.data)
 for v in bm.verts:
  n_w=(M.to_3x3()@v.normal).normalized()
  v.co+=Mi.to_3x3()@(n_w*0.004)
 bm.to_mesh(hi.data);bm.free();hi.data.update()
print('high inflated by 0.004')
# explode handle+pivots so they do not catch body normals during bake
for lo,hi in mmap.items():
 tag=lo.name.lower()
 if 'handle' in tag or 'pivot' in tag:
  lo.location.y+=1.2;hi.location.y+=1.2
bpy.context.view_layer.update()
# UV unwrap low
bpy.ops.object.select_all(action='DESELECT')
for lo in lows:lo.select_set(True)
bpy.context.view_layer.objects.active=lows[0]
bpy.ops.object.mode_set(mode='EDIT');bpy.ops.mesh.select_all(action='SELECT')
bpy.ops.uv.smart_project(angle_limit=0.52,island_margin=0.04)
bpy.ops.object.mode_set(mode='OBJECT')
# images + bake nodes
w,h=1024,1024
img_n=bpy.data.images.new('round_normal',w,h);img_a=bpy.data.images.new('round_ao',w,h)
mat=bpy.data.materials.new('RoundBake');mat.use_nodes=True
nt=mat.node_tree;bsdf=nt.nodes['Principled BSDF']
img_node=nt.nodes.new('ShaderNodeTexImage');img_node.image=img_n;nt.nodes.active=img_node
for lo in lows:lo.data.materials.clear();lo.data.materials.append(mat)
sc=bpy.context.scene;sc.render.engine='CYCLES';sc.cycles.device='CPU';sc.cycles.samples=16
for hi in highs:hi.select_set(False)
def bake(img,typ,samples):
 sc.cycles.samples=samples;img_node.image=img;nt.nodes.active=img_node
 for lo in lows:
  bpy.ops.object.select_all(action='DESELECT')
  for hi in highs:hi.select_set(True)
  lo.select_set(True);bpy.context.view_layer.objects.active=lo
  bpy.ops.object.bake(type=typ,use_selected_to_active=True,use_clear=False,max_ray_distance=0.02,cage_extrusion=0.002,normal_space='TANGENT',margin=16)
bake(img_n,'NORMAL',1)
bake(img_a,'AO',32)
img_n.save_render(out_dir+'/round_normal.png');img_n.filepath_raw=out_dir+'/round_normal.png';img_n.file_format='PNG';img_n.save()
img_a.save_render(out_dir+'/round_ao.png');img_a.filepath_raw=out_dir+'/round_ao.png';img_a.file_format='PNG';img_a.save()
# wire normal + AO into material
img_node.image=img_n;img_node.image.colorspace_settings.name='Non-Color'
nm=nt.nodes.new('ShaderNodeNormalMap')
nt.links.new(img_node.outputs['Color'],nm.inputs['Color']);nt.links.new(nm.outputs['Normal'],bsdf.inputs['Normal'])
img_a_node=nt.nodes.new('ShaderNodeTexImage');img_a_node.image=img_a;img_a_node.image.colorspace_settings.name='Non-Color'
mixao=nt.nodes.new('ShaderNodeMixRGB');mixao.blend_type='MULTIPLY';mixao.inputs['Fac'].default_value=0.85
mixao.inputs['Color1'].default_value=(1.0,0.29,0.012,1)
nt.links.new(img_a_node.outputs['Color'],mixao.inputs['Color2']);nt.links.new(mixao.outputs['Color'],bsdf.inputs['Base Color'])
bsdf.inputs['Roughness'].default_value=.78;bsdf.inputs['Specular IOR Level'].default_value=.2
# un-explode, replace render rig (shadows off for clean judging), render
for lo,hi in mmap.items():
 tag=lo.name.lower()
 if 'handle' in tag or 'pivot' in tag:lo.location.y-=1.2;hi.location.y-=1.2
bpy.ops.object.select_all(action='DESELECT')
for o in highs:o.select_set(True)
bpy.ops.object.delete()
from mathutils import Vector
def final_mat(n,base):
 m=bpy.data.materials.new(n);m.use_nodes=True;t=m.node_tree
 for nd in list(t.nodes):t.nodes.remove(nd)
 out=t.nodes.new('ShaderNodeOutputMaterial');bs=t.nodes.new('ShaderNodeBsdfPrincipled')
 bs.inputs['Roughness'].default_value=.78;bs.inputs['Specular IOR Level'].default_value=.2
 inn=t.nodes.new('ShaderNodeTexImage');inn.image=img_n;inn.image.colorspace_settings.name='Non-Color'
 nmp=t.nodes.new('ShaderNodeNormalMap');t.links.new(inn.outputs['Color'],nmp.inputs['Color']);t.links.new(nmp.outputs['Normal'],bs.inputs['Normal'])
 ia=t.nodes.new('ShaderNodeTexImage');ia.image=img_a;ia.image.colorspace_settings.name='Non-Color'
 mx=t.nodes.new('ShaderNodeMixRGB');mx.blend_type='MULTIPLY';mx.inputs['Fac'].default_value=.85;mx.inputs['Color1'].default_value=base
 t.links.new(ia.outputs['Color'],mx.inputs['Color2']);t.links.new(mx.outputs['Color'],bs.inputs['Base Color'])
 t.links.new(bs.outputs['BSDF'],out.inputs['Surface']);return m
orange=final_mat('RoundOrange',(1,.29,.012,1));black=final_mat('RoundBlack',(.035,.043,.057,1))
for o in lows:
 o.data.materials.clear();o.data.materials.append(orange if ('Body' in o.name or 'Rim' in o.name) else black)
 o.visible_shadow=False
sc.render.engine='BLENDER_EEVEE_NEXT';sc.render.resolution_x=700;sc.render.resolution_y=700;sc.render.resolution_percentage=100;sc.render.image_settings.file_format='PNG';sc.view_settings.view_transform='Standard';sc.view_settings.look='Medium High Contrast';sc.world=bpy.data.worlds.new('World');sc.world.use_nodes=True;sc.world.node_tree.nodes['Background'].inputs['Color'].default_value=(.018,.022,.03,1);sc.world.node_tree.nodes['Background'].inputs['Strength'].default_value=.55
for n,l,e,s in [('Key',(-4,-5,7),700,6),('Fill',(5,-2,4),450,5),('Top',(0,2,7),420,4),('Rim',(2,5,3),240,3)]:ld=bpy.data.lights.new(n,'AREA');ld.energy=e;ld.size=s;x=bpy.data.objects.new(n,ld);sc.collection.objects.link(x);x.location=l
cd=bpy.data.cameras.new('Camera');cam=bpy.data.objects.new('Camera',cd);sc.collection.objects.link(cam);sc.camera=cam;cd.type='ORTHO';cd.ortho_scale=1.28;focus=Vector((0,0,.41))
def shot(v,p):cam.location=Vector(p);cam.rotation_euler=(focus-cam.location).to_track_quat('-Z','Y').to_euler();sc.render.filepath=os.path.join(out_dir,f'round_{v}.png');bpy.ops.render.render(write_still=True)
shot('front',(0,-4,.48));shot('perspective',(1.8,-2.8,1.45));shot('top',(0,0,4))
bpy.ops.object.select_all(action='DESELECT')
for o in lows:o.select_set(True)
bpy.ops.export_scene.gltf(filepath=out_glb,export_format='GLB',use_selection=True,export_materials='EXPORT')
tri=sum(len(p.vertices)-2 for o in lows for p in o.data.polygons)
print('ROUND BAKE OK triangles:',tri,'glb:',out_glb)
