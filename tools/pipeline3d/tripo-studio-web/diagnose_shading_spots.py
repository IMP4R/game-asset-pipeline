import bpy,sys,json,math,os
import numpy as np
from mathutils import Vector
src,out=sys.argv[sys.argv.index('--')+1:];os.makedirs(out,exist_ok=True)
bpy.ops.wm.read_factory_settings(use_empty=True);bpy.ops.import_scene.gltf(filepath=src)
objs=[o for o in bpy.context.scene.objects if o.type=='MESH'];objs.sort(key=lambda o:len(o.data.polygons),reverse=True);body=objs[0]
V=np.array([tuple(body.matrix_world@v.co) for v in body.data.vertices]);z=V[:,2];r=np.linalg.norm(V[:,:2],axis=1)
# Main outer wall only.
mask=(z>.10)&(z<.58)&(r>.34);zz=z[mask];rr=r[mask]
bins=np.linspace(zz.min(),zz.max(),14);res=[]
for lo,hi in zip(bins[:-1],bins[1:]):
 q=(zz>=lo)&(zz<hi)
 if q.sum():res.extend((rr[q]-np.median(rr[q])).tolist())
res=np.array(res)
# Triangle quality on wall.
aspects=[];normal_radial=[]
for p in body.data.polygons:
 c=body.matrix_world@p.center
 if not (.10<c.z<.58 and math.hypot(c.x,c.y)>.34):continue
 pts=[body.matrix_world@body.data.vertices[i].co for i in p.vertices]
 es=[(pts[i]-pts[(i+1)%len(pts)]).length for i in range(len(pts))]
 if min(es)>1e-9:aspects.append(max(es)/min(es))
 n=(body.matrix_world.to_3x3().inverted().transposed()@p.normal).normalized();rad=Vector((c.x,c.y,0)).normalized();normal_radial.append(math.degrees(n.angle(rad)))
# Normal-debug material: world normal mapped to RGB. Any bands are normals, not lighting.
m=bpy.data.materials.new('Normal Debug');m.use_nodes=True;n=m.node_tree.nodes;n.clear();outn=n.new('ShaderNodeOutputMaterial');geom=n.new('ShaderNodeNewGeometry');sep=n.new('ShaderNodeVectorMath');sep.operation='MULTIPLY_ADD';sep.inputs[1].default_value=(.5,.5,.5);sep.inputs[2].default_value=(.5,.5,.5);em=n.new('ShaderNodeEmission');m.node_tree.links.new(geom.outputs['Normal'],sep.inputs[0]);m.node_tree.links.new(sep.outputs[0],em.inputs['Color']);m.node_tree.links.new(em.outputs[0],outn.inputs[0]);body.data.materials.clear();body.data.materials.append(m)
for o in objs[1:]:o.hide_render=True
sc=bpy.context.scene;sc.render.engine='BLENDER_EEVEE_NEXT';sc.render.resolution_x=700;sc.render.resolution_y=700;sc.render.resolution_percentage=100;sc.render.image_settings.file_format='PNG';sc.world=bpy.data.worlds.new('World');cd=bpy.data.cameras.new('Camera');cam=bpy.data.objects.new('Camera',cd);sc.collection.objects.link(cam);sc.camera=cam;cd.type='ORTHO';cd.ortho_scale=1.28;focus=Vector((0,0,.41));cam.location=(1.8,-2.8,1.45);cam.rotation_euler=(focus-cam.location).to_track_quat('-Z','Y').to_euler();sc.render.filepath=os.path.join(out,'normal_debug.png');bpy.ops.render.render(write_still=True)
st={'wall_radial_residual_rms':float(np.sqrt(np.mean(res**2))),'wall_radial_residual_max':float(np.max(np.abs(res))),'wall_triangle_aspect_median':float(np.median(aspects)),'wall_triangle_aspect_p95':float(np.percentile(aspects,95)),'wall_triangle_aspect_max':float(max(aspects)),'face_normal_radial_error_median_deg':float(np.median(normal_radial)),'face_normal_radial_error_p95_deg':float(np.percentile(normal_radial,95)),'cause':'irregular QEM triangles over radially uneven source wall; smooth normals interpolate the deviations into broad bands'}
json.dump(st,open(os.path.join(out,'diagnosis.json'),'w'),indent=2);print(json.dumps(st,indent=2))
