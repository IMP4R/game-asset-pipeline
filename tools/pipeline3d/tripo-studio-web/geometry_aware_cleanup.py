import bpy, sys, os, json, math, numpy as np
from mathutils import Vector

src,out_clean,out_low,render_dir=sys.argv[sys.argv.index('--')+1:]
os.makedirs(render_dir,exist_ok=True)
bpy.ops.wm.read_factory_settings(use_empty=True);bpy.ops.import_scene.gltf(filepath=src)
root=next(o for o in bpy.context.scene.objects if o.type=='MESH');bpy.context.view_layer.objects.active=root;root.select_set(True)
bpy.ops.object.mode_set(mode='EDIT');bpy.ops.mesh.separate(type='LOOSE');bpy.ops.object.mode_set(mode='OBJECT')
parts=[o for o in bpy.context.selected_objects if o.type=='MESH'];parts.sort(key=lambda o:len(o.data.polygons),reverse=True)
body=parts[0]; other=parts[1:]
def world(o):return np.array([tuple(o.matrix_world@v.co) for v in o.data.vertices],dtype=np.float64)
def setworld(o,a):
 inv=o.matrix_world.inverted()
 for v,p in zip(o.data.vertices,a):v.co=inv@Vector(p)
def centroid(o):return world(o).mean(0)
# Classify arc as widest non-body component; remaining two are pivots.
arc=max(other,key=lambda o:np.ptp(world(o)[:,0]));pivots=[o for o in other if o!=arc];pivots.sort(key=lambda o:centroid(o)[0]);left,right=pivots

# Center all original components from the body bounds.
b=world(body);center_xy=(b[:,:2].min(0)+b[:,:2].max(0))/2
for o in parts:o.location.x-=center_xy[0];o.location.y-=center_xy[1]

# 1) Exact rigid handle-axis alignment, preserving generated geometry.
ca,cb=Vector(centroid(left)),Vector(centroid(right));mid=(ca+cb)/2;rot=(cb-ca).normalized().rotation_difference(Vector((1,0,0)))
for o in [arc,left,right]:
 a=world(o);a=np.array([tuple(mid+rot@(Vector(p)-mid)) for p in a]);setworld(o,a)

# 2) Geometry-aware axisymmetry only on OUTER mid-wall.
# Vertex normals separate outer wall from inner cavity, preventing layer mixing.
body.data.update();a=world(body);r=np.linalg.norm(a[:,:2],axis=1)
normal_matrix=body.matrix_world.to_3x3().inverted().transposed()
n=np.array([tuple((normal_matrix@v.normal).normalized()) for v in body.data.vertices])
radial=np.zeros_like(a);radial[:,:2]=a[:,:2]/np.maximum(r[:,None],1e-9)
outward=(n*radial).sum(1)
mask=(a[:,2]>.075)&(a[:,2]<.695)&(r>.34)&(outward>.18)
# Robust medians over height, then a low-order fit: removes dents without changing taper semantics.
z=a[mask,2];rr=r[mask];edges=np.linspace(z.min(),z.max(),25);zc=[];rc=[]
for lo,hi in zip(edges[:-1],edges[1:]):
 q=(z>=lo)&(z<hi)
 if q.sum()>=8:zc.append(float(np.median(z[q])));rc.append(float(np.median(rr[q])))
coef=np.polyfit(zc,rc,2)
target=np.polyval(coef,a[:,2]);old=a.copy();blend=.82
scale=(r*(1-blend)+target*blend)/np.maximum(r,1e-9)
a[mask,0]*=scale[mask];a[mask,1]*=scale[mask]
# Separate upper neck cleanup: remove Tripo's hanging spikes below the rim without touching the rim itself.
r=np.linalg.norm(a[:,:2],axis=1)
neck=(a[:,2]>=.685)&(a[:,2]<=.755)&(r>.385)&(r<.475)&(outward>.05)
if neck.sum()>10:
 zn=a[neck,2];rn=r[neck];nedges=np.linspace(zn.min(),zn.max(),10);nzc=[];nrc=[]
 for lo,hi in zip(nedges[:-1],nedges[1:]):
  q=(zn>=lo)&(zn<hi)
  if q.sum()>=3:nzc.append(float(np.median(zn[q])));nrc.append(float(np.median(rn[q])))
 if len(nzc)>=2:
  nc=np.polyfit(nzc,nrc,1);nt=np.polyval(nc,a[:,2]);ns=(.15*r+.85*nt)/np.maximum(r,1e-9);a[neck,0]*=ns[neck];a[neck,1]*=ns[neck]
# Underside-rim repair: infer smooth Z(radius) from robust upper quartiles and lift only hanging outliers.
under=(a[:,2]>.64)&(a[:,2]<.785)&(r>.34)&(r<.52)&(n[:,2]<-.08)
ur=r[under];uz=a[under,2]
if under.sum()>16:
 bins=np.linspace(ur.min(),ur.max(),12);br=[];bz=[]
 for lo,hi in zip(bins[:-1],bins[1:]):
  q=(ur>=lo)&(ur<hi)
  if q.sum()>=3:br.append(float(np.median(ur[q])));bz.append(float(np.percentile(uz[q],72)))
 if len(br)>=4:
  zcoef=np.polyfit(br,bz,2);zt=np.polyval(zcoef,r);bad=under&(a[:,2]<(zt-.004));a[bad,2]=zt[bad]-.004
setworld(body,a);body.name='Tripo_Body_GeometryAware_Axisymmetric'

# 3) Pairwise handle symmetry WITHOUT cutting topology.
h=world(arc);neg=np.where(h[:,0]<0)[0];pos=np.where(h[:,0]>0)[0]
P=h[neg];Q=h[pos].copy();Q[:,0]*=-1
# Pair by normalized position; mutual nearest only, preventing unrelated cross-section vertices from matching.
d2=((P[:,None,:]-Q[None,:,:])**2).sum(2);p_to_q=d2.argmin(1);q_to_p=d2.argmin(0)
# Build a bounded correction field from reliable mutual pairs, then diffuse it over topology.
delta=np.zeros_like(h);weight=np.zeros(len(h));pairs=[]
for ip,jp in enumerate(p_to_q):
 if q_to_p[jp]!=ip:continue
 i=neg[ip];j=pos[jp];p=h[i];qm=h[j].copy();qm[0]*=-1
 avg=(p+qm)/2;delta[i]=avg-p;mir=avg.copy();mir[0]*=-1;delta[j]=mir-h[j];weight[i]=weight[j]=1;pairs.append((i,j,float(math.sqrt(d2[ip,jp]))))
# Mesh-neighbor diffusion makes the deformation C0-smooth and moves unmatched vertices coherently.
nbs=[set() for _ in arc.data.vertices]
for e in arc.data.edges:
 i,j=e.vertices;nbs[i].add(j);nbs[j].add(i)
for _ in range(18):
 nd=delta.copy();nw=weight.copy()
 for i,ns in enumerate(nbs):
  if not ns:continue
  vals=[delta[j] for j in ns];nd[i]=.32*delta[i]+.68*np.mean(vals,axis=0);nw[i]=max(weight[i]*.94,np.mean([weight[j] for j in ns])*.92)
 delta,weight=nd,nw
mag=np.linalg.norm(delta,axis=1);cap=.009;delta*=np.minimum(1,cap/np.maximum(mag,1e-9))[:,None]
updates=h+delta*np.clip(weight[:,None],0,1)
setworld(arc,updates);arc.name='Tripo_Handle_SmoothPairSymmetry'

# 4) Preserve one original generated pivot and mirror it exactly; attachment axis remains exact.
bpy.data.objects.remove(right,do_unlink=True)
right=left.copy();right.data=left.data.copy();bpy.context.collection.objects.link(right)
# Mirror the complete source pivot in world space; this preserves its attachment to the handle end.
ra=world(right);ra[:,0]*=-1;setworld(right,ra);left.name='Tripo_Pivot_L_Source';right.name='Tripo_Pivot_R_Mirrored'
final=[body,arc,left,right]
for o in final:
 for f in o.data.polygons:f.use_smooth=True
 o.select_set(True)

# Clean full-resolution source-topology export.
bpy.ops.export_scene.gltf(filepath=out_clean,export_format='GLB',use_selection=True,export_materials='EXPORT')
full_stats={'vertices':sum(len(o.data.vertices) for o in final),'polygons':sum(len(o.data.polygons) for o in final),'triangles':sum(len(f.vertices)-2 for o in final for f in o.data.polygons)}

# Duplicate clean objects and perform conservative QEM decimation for a separate low-poly result.
low=[]
for o,ratio in zip(final,[1.0,.82,.68,.68]):
 c=o.copy();c.data=o.data.copy();bpy.context.collection.objects.link(c);c.name=o.name+'_LOW';low.append(c)
 bpy.context.view_layer.objects.active=c;c.select_set(True);mod=c.modifiers.new('Conservative QEM','DECIMATE');mod.decimate_type='COLLAPSE';mod.ratio=ratio;mod.use_collapse_triangulate=True
 bpy.ops.object.modifier_apply(modifier=mod.name)
 # Return every simplified vertex to the corresponding clean full-resolution surface.
 sw=c.modifiers.new('Project to clean source','SHRINKWRAP');sw.target=o;sw.wrap_method='NEAREST_SURFACEPOINT';sw.wrap_mode='ON_SURFACE'
 bpy.ops.object.modifier_apply(modifier=sw.name);c.select_set(False)
for o in final:o.hide_render=True;o.select_set(False)
for o in low:o.select_set(True)
bpy.ops.export_scene.gltf(filepath=out_low,export_format='GLB',use_selection=True,export_materials='EXPORT')
low_stats={'vertices':sum(len(o.data.vertices) for o in low),'polygons':sum(len(o.data.polygons) for o in low),'triangles':sum(len(f.vertices)-2 for o in low for f in o.data.polygons)}

# Numeric audit.
wall_shift=np.linalg.norm(a-old,axis=1);lc=centroid(left);rcen=centroid(right)
stats={'method':'original Tripo topology; normal-classified robust radial profile; mutual pair symmetry; conservative QEM copy','outer_wall_vertices_adjusted':int(mask.sum()),'outer_wall_mean_shift':float(wall_shift[mask].mean()),'outer_wall_max_shift':float(wall_shift[mask].max()),'handle_mutual_pairs':len(pairs),'handle_pair_median_pre_error':float(np.median([x[2] for x in pairs])) if pairs else None,'pivot_axis_error':float(max(abs(lc[0]+rcen[0]),abs(lc[1]-rcen[1]),abs(lc[2]-rcen[2]))),'full':full_stats,'low':low_stats}

# Render CLEAN full resolution first with fixed audit rig; low-poly remains a separate export.
for o in low:o.hide_render=True
for o in final:o.hide_render=False
scene=bpy.context.scene;scene.render.engine='BLENDER_EEVEE_NEXT';scene.render.resolution_x=720;scene.render.resolution_y=720;scene.render.resolution_percentage=100;scene.render.image_settings.file_format='PNG';scene.view_settings.view_transform='Standard';scene.view_settings.look='Medium High Contrast'
scene.world=bpy.data.worlds.new('World');scene.world.use_nodes=True;scene.world.node_tree.nodes['Background'].inputs['Color'].default_value=(.018,.022,.03,1);scene.world.node_tree.nodes['Background'].inputs['Strength'].default_value=.28
for name,loc,en,sz in [('Key',(4,-5,7),900,5),('Fill',(-4,-2,4),450,4),('Rim',(2,5,5),650,3)]:
 ld=bpy.data.lights.new(name,'AREA');ld.energy=en;ld.size=sz;o=bpy.data.objects.new(name,ld);scene.collection.objects.link(o);o.location=loc
camd=bpy.data.cameras.new('Camera');cam=bpy.data.objects.new('Camera',camd);scene.collection.objects.link(cam);scene.camera=cam;camd.type='ORTHO';camd.ortho_scale=1.28;focus=Vector((0,0,.41))
def shot(n,pos):cam.location=Vector(pos);cam.rotation_euler=(focus-cam.location).to_track_quat('-Z','Y').to_euler();scene.render.filepath=os.path.join(render_dir,f'geo_{n}.png');bpy.ops.render.render(write_still=True)
shot('front',(0,-4,.48));shot('side',(4,0,.48));shot('back',(0,4,.48));shot('top',(0,0,4))
# Separate low-poly audit under the exact same rig.
for o in final:o.hide_render=True
for o in low:o.hide_render=False
shot('low_front',(0,-4,.48));shot('low_side',(4,0,.48))
with open(os.path.join(render_dir,'geometry_aware_stats.json'),'w') as f:json.dump(stats,f,indent=2)
print(json.dumps(stats,indent=2))
