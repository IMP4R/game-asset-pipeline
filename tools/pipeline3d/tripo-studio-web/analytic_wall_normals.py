import bpy,bmesh,sys,os,json,math
import numpy as np
from mathutils import Vector
src,out_path,render_dir=sys.argv[sys.argv.index('--')+1:];os.makedirs(render_dir,exist_ok=True)
bpy.ops.wm.read_factory_settings(use_empty=True);bpy.ops.import_scene.gltf(filepath=src)
objs=[o for o in bpy.context.scene.objects if o.type=='MESH'];objs.sort(key=lambda o:len(o.data.polygons),reverse=True);body=objs[0]
# Recalculate topology normals, then enable stock smooth shading everywhere.
for o in objs:
 bm=bmesh.new();bm.from_mesh(o.data);bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bm.to_mesh(o.data);bm.free();o.data.update()
 for p in o.data.polygons:p.use_smooth=True
# The wall has already been projected to r(z). Refit that exact low-mesh profile.
V=np.array([tuple(body.matrix_world@v.co) for v in body.data.vertices],float);r=np.linalg.norm(V[:,:2],axis=1);z=V[:,2]
# Fit the already source-projected exterior profile from vertices across the wall band.
fitmask=(z>.07)&(z<.62)&(r>.34)
coef=np.polyfit(z[fitmask],r[fitmask],min(2,max(0,int(fitmask.sum())-1)))
# Replace complete exterior-wall face corners. Partial per-vertex replacement leaves triangular wedges.
body.data.calc_loop_triangles();body.data.update();base=[Vector(l.vector) for l in body.data.corner_normals]
world3=body.matrix_world.to_3x3();invn=world3.transposed()
changed=0;wall_faces=0;wall_verts=set()
for poly in body.data.polygons:
 c=body.matrix_world@poly.center;cr=math.hypot(c.x,c.y)
 wn_face=(body.matrix_world.to_3x3().inverted().transposed()@poly.normal).normalized()
 radial=Vector((c.x,c.y,0)).normalized() if cr>1e-9 else Vector((0,0,0))
 # Exterior side faces only; reject floor, cavity, rim top and underside.
 if not (.055<c.z<.625 and cr>.34 and wn_face.dot(radial)>.15):continue
 wall_faces+=1
 for li in poly.loop_indices:
  vi=body.data.loops[li].vertex_index;p=V[vi];rv=math.hypot(p[0],p[1])
  if rv<1e-9:continue
  slope=float(2*coef[0]*p[2]+coef[1]) if len(coef)==3 else (float(coef[0]) if len(coef)==2 else 0.0)
  wn=Vector((p[0]/rv,p[1]/rv,-slope)).normalized()
  base[li]=(invn@wn).normalized();changed+=1;wall_verts.add(vi)
body.data.normals_split_custom_set(base);body.data.update()
for o in objs:o.select_set(True)
bpy.ops.export_scene.gltf(filepath=out_path,export_format='GLB',use_selection=True,export_materials='EXPORT',export_normals=True)
st={'triangles':sum(len(p.vertices)-2 for o in objs for p in o.data.polygons),'wall_vertices_with_analytic_normals':len(wall_verts),'wall_faces_with_analytic_normals':wall_faces,'wall_corners_replaced':changed,'profile_coefficients':coef.tolist(),'method':'analytic exterior normals from post-QEM source-derived radial profile; geometry unchanged'};json.dump(st,open(os.path.join(render_dir,'stats.json'),'w'),indent=2)
# Continuous matte PBR diagnostic render.
def mat(n,c):m=bpy.data.materials.new(n);m.use_nodes=True;b=m.node_tree.nodes['Principled BSDF'];b.inputs['Base Color'].default_value=c;b.inputs['Roughness'].default_value=.78;b.inputs['Specular IOR Level'].default_value=.2;return m
orange=mat('Orange',(1,.29,.012,1));black=mat('Black',(.035,.043,.057,1))
for o in objs:o.data.materials.clear();o.data.materials.append(orange if o==body else black)
sc=bpy.context.scene;sc.render.engine='BLENDER_EEVEE_NEXT';sc.render.resolution_x=600;sc.render.resolution_y=600;sc.render.resolution_percentage=100;sc.render.image_settings.color_mode='RGB';sc.render.engine='BLENDER_EEVEE_NEXT';sc.render.image_settings.file_format='PNG';sc.render.film_transparent=False;sc.render.image_settings.file_format='PNG';sc.view_settings.view_transform='Standard';sc.view_settings.look='Medium High Contrast';sc.world=bpy.data.worlds.new('World');sc.world.use_nodes=True;sc.world.node_tree.nodes['Background'].inputs['Color'].default_value=(.018,.022,.03,1);sc.world.node_tree.nodes['Background'].inputs['Strength'].default_value=.35
for n,l,e,s in [('Key',(-4,-5,7),700,6),('Fill',(5,-2,4),350,5),('Top',(0,2,7),420,4),('Rim',(2,5,3),240,3)]:ld=bpy.data.lights.new(n,'AREA');ld.energy=e;ld.size=s;x=bpy.data.objects.new(n,ld);sc.collection.objects.link(x);x.location=l
cd=bpy.data.cameras.new('Camera');cam=bpy.data.objects.new('Camera',cd);sc.collection.objects.link(cam);sc.camera=cam;cd.type='ORTHO';cd.ortho_scale=1.28;focus=Vector((0,0,.41))
def shot(v,p):cam.location=Vector(p);cam.rotation_euler=(focus-cam.location).to_track_quat('-Z','Y').to_euler();sc.render.filepath=os.path.join(render_dir,f'analytic_{v}.png');bpy.ops.render.render(write_still=True)
shot('side',(4,0,.48));shot('back',(0,4,.48));shot('perspective',(1.8,-2.8,1.45));print(json.dumps(st,indent=2))
