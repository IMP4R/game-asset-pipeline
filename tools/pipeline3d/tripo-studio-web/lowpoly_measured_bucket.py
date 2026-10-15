import bpy,bmesh,sys,os,json,math,time
import numpy as np
from mathutils import Vector,Matrix
src,out_path,render_dir=sys.argv[sys.argv.index('--')+1:];os.makedirs(render_dir,exist_ok=True)
start=time.perf_counter();bpy.ops.wm.read_factory_settings(use_empty=True)
# ---- measured from dense cleaned+smoothed Tripo source (see probes) ----
SIDES=16
P_W0=(0.388,0.002);P_W1=(0.414,0.35);P_W2=(0.44,0.70)      # outer wall: foot -> mid -> under-rim
P_IN=(0.385,0.70);P_IN2=(0.385,0.05)                        # inner lip under rim -> inner wall low
Z_BOT=0.002;Z_FLOOR=0.043                                   # outer bottom / cavity floor
RIM_R=0.44;RIM_A=0.05;RIM_B=0.0665;RIM_Z=0.7665                # bead: inner 0.39, outer 0.49, bottom 0.70, top 0.833
PIV_X=0.482;PIV_Y=-0.0334;PIV_Z=0.6293;PIV_RAD=0.073;PIV_DEP=0.095
HAN_R=0.05;HAN_SIDES=6;HAN_SECT=13
ARC=[(-PIV_X,PIV_Y,PIV_Z),(-0.42,-0.17,0.612),(0.0,-0.474,0.545),(0.42,-0.17,0.612),(PIV_X,PIV_Y,PIV_Z)]

def catmull(pts,t):
 # uniform Catmull-Rom over control polyline; t in [0,1]
 n=len(pts)-1;f=t*n;i=min(int(f),n-1);u=f-i
 p=[pts[max(0,i-1)],pts[i],pts[i+1],pts[min(n,i+2)]]
 out=[]
 for k in range(3):
  a,b,c,d=(q[k] for q in p);out.append(0.5*((2*b)+(-a+c)*u+(2*a-5*b+4*c-d)*u*u+(-a+3*b-3*c+d)*u*u*u))
 return Vector(out)
# ---- body: closed lathe profile, even quads, exact poles ----
prof=[(0.0,Z_BOT),P_W0,P_W1,P_W2,P_IN,P_IN2,(0.0,Z_FLOOR)]
bm=bmesh.new();rings=[]
for r,z in prof:
 if r<1e-6:rings.append(('pole',bm.verts.new((0,0,z))))
 else:rings.append(('ring',[bm.verts.new((r*math.cos(a),r*math.sin(a),z)) for a in [i*2*math.pi/SIDES for i in range(SIDES)]]))
for (ka,ga),(kb,gb) in zip(rings[:-1],rings[1:]):
 if ka=='pole' and kb=='ring':
  for i in range(SIDES):bm.faces.new((ga,gb[i],gb[(i+1)%SIDES]))
 elif ka=='ring' and kb=='ring':
  for i in range(SIDES):bm.faces.new((ga[i],ga[(i+1)%SIDES],gb[(i+1)%SIDES],gb[i]))
 elif ka=='ring' and kb=='pole':
  for i in range(SIDES):bm.faces.new((ga[i],ga[(i+1)%SIDES],gb))
bmesh.ops.recalc_face_normals(bm,faces=bm.faces)
body=bpy.data.objects.new('Bucket_Body_Lathe',bpy.data.meshes.new('Bucket_Body_Lathe'));bm.to_mesh(body.data);bm.free();bpy.context.collection.objects.link(body)
# ---- rim: low-segment torus ----
bm=bmesh.new();maj=RIM_R;grid=[]
CORNER=[(RIM_A,RIM_B),(-RIM_A,RIM_B),(-RIM_A,-RIM_B),(RIM_A,-RIM_B)]
for i in range(SIDES):
 a=i*2*math.pi/SIDES;ca,sa=math.cos(a),math.sin(a);col=[]
 for k in range(4):
  dr,dz=CORNER[k]
  col.append(bm.verts.new(((maj+dr)*ca,(maj+dr)*sa,dz+RIM_Z)))
 grid.append(col)
for i in range(SIDES):
 j=(i+1)%SIDES
 for k in range(4):l=(k+1)%4;bm.faces.new((grid[i][k],grid[j][k],grid[j][l],grid[i][l]))
bmesh.ops.recalc_face_normals(bm,faces=bm.faces)
rim=bpy.data.objects.new('Bucket_Rim_Torus',bpy.data.meshes.new('Bucket_Rim_Torus'));bm.to_mesh(rim.data);bm.free();bpy.context.collection.objects.link(rim)
# ---- handle: Catmull arc, 6-sided rings, bridged ----
bm=bmesh.new();ts=[i/(HAN_SECT-1) for i in range(HAN_SECT)];pts=[catmull(ARC,t) for t in ts];ringsH=[]
for idx,c in enumerate(pts):
 tangent=(pts[min(idx+1,HAN_SECT-1)]-pts[max(idx-1,0)]).normalized()
 up=Vector((0,0,1)) if abs(tangent.z)<.9 else Vector((0,1,0));x1=tangent.cross(up).normalized();y1=tangent.cross(x1).normalized()
 ringsH.append([bm.verts.new(c+x1*HAN_R*math.cos(a*2*math.pi/HAN_SIDES)+y1*HAN_R*math.sin(a*2*math.pi/HAN_SIDES)) for a in range(HAN_SIDES)])
for ra,rb in zip(ringsH[:-1],ringsH[1:]):
 for i in range(HAN_SIDES):bm.faces.new((ra[i],ra[(i+1)%HAN_SIDES],rb[(i+1)%HAN_SIDES],rb[i]))
for ring in (ringsH[0],ringsH[-1]):bm.faces.new(ring)
bm.normal_update()
handle=bpy.data.objects.new('Bucket_Handle_Tube',bpy.data.meshes.new('Bucket_Handle_Tube'));bm.to_mesh(handle.data);bm.free();bpy.context.collection.objects.link(handle)
# ---- pivots: 6-sided cylinders, inner caps removed ----
def pivot(sx):
 bm=bmesh.new();ringA=[];ringB=[];xa=sx*(PIV_X-PIV_DEP/2);xb=sx*(PIV_X+PIV_DEP/2)
 for i in range(6):
  a=i*math.pi/3;ringA.append(bm.verts.new((xa,PIV_Y+PIV_RAD*math.cos(a),PIV_Z+PIV_RAD*math.sin(a))));ringB.append(bm.verts.new((xb,PIV_Y+PIV_RAD*math.cos(a),PIV_Z+PIV_RAD*math.sin(a))))
 for i in range(6):
  j=(i+1)%6;f=bm.faces.new((ringA[i],ringA[j],ringB[j],ringB[i]))
 cap=bm.faces.new(ringB if sx>0 else ringA)
 bmesh.ops.recalc_face_normals(bm,faces=bm.faces)
 o=bpy.data.objects.new(f'Bucket_Pivot_{"R" if sx>0 else "L"}',bpy.data.meshes.new('pivot'));bm.to_mesh(o.data);bm.free();bpy.context.collection.objects.link(o);return o
pivL=pivot(-1);pivR=pivot(1)
# ---- shading: deterministic. All faces smooth; creases marked by dihedral angle. No operator dependency. ----
for o in (body,rim,handle,pivL,pivR):
 bm=bmesh.new();bm.from_mesh(o.data)
 for f in bm.faces:f.smooth=True
 for e in bm.edges:
  e.smooth=True
  if len(e.link_faces)==2:
   if e.link_faces[0].normal.angle(e.link_faces[1].normal)>math.radians(40):e.smooth=False
 bm.to_mesh(o.data);bm.free();o.data.update()
# ---- export + audit ----
for o in (body,rim,handle,pivL,pivR):o.select_set(True)
bpy.ops.export_scene.gltf(filepath=out_path,export_format='GLB',use_selection=True,export_materials='EXPORT')
def tri(o):return sum(len(p.vertices)-2 for p in o.data.polygons)
hv=[v.co for v in handle.data.vertices];mirror=max(min((Vector((-p.x,p.y,p.z))-q).length for q in hv) for p in hv)
compute=time.perf_counter()-start
st={'method':'measured lathe body + low-segment torus rim + 6-sided tube handle + 6-sided pivots (community standard for 200-500 tri)','compute_seconds':compute,'triangles':sum(tri(o) for o in (body,rim,handle,pivL,pivR)),'component_triangles':[tri(o) for o in (body,rim,handle,pivL,pivR)],'sides':SIDES,'handle_mirror_error':mirror,'height':0.833,'foot_radius':P_W0[0],'shoulder_radius':P_W2[0]}
json.dump(st,open(os.path.join(render_dir,'stats.json'),'w'),indent=2)
# ---- render: same audit rig ----
def mat(n,c):m=bpy.data.materials.new(n);m.use_nodes=True;b=m.node_tree.nodes['Principled BSDF'];b.inputs['Base Color'].default_value=c;b.inputs['Roughness'].default_value=.78;b.inputs['Specular IOR Level'].default_value=.2;return m
orange=mat('Orange',(1,.29,.012,1));black=mat('Black',(.035,.043,.057,1))
for o in (body,rim):o.data.materials.append(orange)
for o in (handle,pivL,pivR):o.data.materials.append(black)
sc=bpy.context.scene;sc.render.engine='BLENDER_EEVEE_NEXT';sc.render.resolution_x=700;sc.render.resolution_y=700;sc.render.resolution_percentage=100;sc.render.image_settings.file_format='PNG';sc.view_settings.view_transform='Standard';sc.view_settings.look='Medium High Contrast';sc.world=bpy.data.worlds.new('World');sc.world.use_nodes=True;sc.world.node_tree.nodes['Background'].inputs['Color'].default_value=(.018,.022,.03,1);sc.world.node_tree.nodes['Background'].inputs['Strength'].default_value=.35
for n,l,e,s in [('Key',(-4,-5,7),700,6),('Fill',(5,-2,4),350,5),('Top',(0,2,7),420,4),('Rim',(2,5,3),240,3)]:ld=bpy.data.lights.new(n,'AREA');ld.energy=e;ld.size=s;x=bpy.data.objects.new(n,ld);sc.collection.objects.link(x);x.location=l
cd=bpy.data.cameras.new('Camera');cam=bpy.data.objects.new('Camera',cd);sc.collection.objects.link(cam);sc.camera=cam;cd.type='ORTHO';cd.ortho_scale=1.28;focus=Vector((0,0,.41))
def shot(v,p):cam.location=Vector(p);cam.rotation_euler=(focus-cam.location).to_track_quat('-Z','Y').to_euler();sc.render.filepath=os.path.join(render_dir,f'low_{v}.png');bpy.ops.render.render(write_still=True)
shot('front',(0,-4,.48));shot('side',(4,0,.48));shot('back',(0,4,.48));shot('top',(0,0,4));shot('perspective',(1.8,-2.8,1.45));print(json.dumps(st,indent=2))
