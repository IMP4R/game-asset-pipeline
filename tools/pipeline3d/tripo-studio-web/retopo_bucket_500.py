import bpy, math, os, sys, json
from mathutils import Vector

src_clean,out_glb,render_dir=sys.argv[sys.argv.index('--')+1:]
os.makedirs(render_dir,exist_ok=True)
bpy.ops.wm.read_factory_settings(use_empty=True)
# Measurements are sampled from the geometry-aware cleaned Tripo result.
SEG=16; PATH_STEPS=10
ORANGE='#FF8E00'; BLACK='#2E2E33'
def lin(v):
 v/=255;return v/12.92 if v<=.04045 else ((v+.055)/1.055)**2.4
def mat(name,hx,rough):
 m=bpy.data.materials.new(name);m.use_nodes=True;b=m.node_tree.nodes['Principled BSDF'];b.inputs['Base Color'].default_value=(*(lin(int(hx[i:i+2],16)) for i in (1,3,5)),1);b.inputs['Roughness'].default_value=rough;return m
orange=mat('Tripo Orange',ORANGE,.5);black=mat('Tripo Handle',BLACK,.62)
# 10 measured radial rings + center. Deliberately minimal topology, but preserves hollow rim and floor.
profile=[
 (.397,.018),(.415,.000),       # bottom foot
 (.447,.555),                    # tapered outer wall
 (.478,.612),(.505,.655),(.497,.724), # neck and rounded rim outer/top
 (.452,.716),(.427,.655),        # inner rim and inner wall
 (.397,.112),(.000,.092)         # floor edge and center
]
verts=[];starts=[]
for r,z in profile:
 starts.append(len(verts))
 if r==0:verts.append((0,0,z))
 else:
  for i in range(SEG):
   a=2*math.pi*i/SEG;verts.append((r*math.cos(a),r*math.sin(a),z))
faces=[]
for j in range(len(profile)-1):
 r1,_=profile[j];r2,_=profile[j+1];s1=starts[j];s2=starts[j+1]
 if r2==0:
  for i in range(SEG):faces.append((s1+i,s1+(i+1)%SEG,s2))
 else:
  for i in range(SEG):faces.append((s1+i,s1+(i+1)%SEG,s2+(i+1)%SEG,s2+i))
me=bpy.data.meshes.new('Retopo500_Body');me.from_pydata(verts,[],faces);me.materials.append(orange);me.update();body=bpy.data.objects.new('Bucket_Body_500',me);bpy.context.collection.objects.link(body)
for p in me.polygons:p.use_smooth=True
# One connected symmetric strap. Six-sided soft rectangular section; path measured from cleaned handle.
R=.506;pz=.623;sag=.095;hw=.030;hh=.041
section=[(-hw,-hh),(hw,-hh),(hw,0),(hw,hh),(-hw,hh),(-hw,0)]
path=[]
for i in range(PATH_STEPS+1):
 t=math.pi*i/PATH_STEPS;path.append(Vector((R*math.cos(t),-R*math.sin(t),pz-sag*math.sin(t))))
hv=[]
for i,c in enumerate(path):
 tangent=(path[min(i+1,PATH_STEPS)]-path[max(0,i-1)]).normalized();rad=Vector((c.x,c.y,0)).normalized();up=tangent.cross(rad).normalized()
 if up.z<0:up=-up
 for rw,zh in section:hv.append(tuple(c+rad*rw+up*zh))
hf=[];S=len(section)
for j in range(PATH_STEPS):
 for k in range(S):hf.append((j*S+k,j*S+(k+1)%S,(j+1)*S+(k+1)%S,(j+1)*S+k))
hf += [tuple(range(S-1,-1,-1)),tuple(PATH_STEPS*S+k for k in range(S))]
hm=bpy.data.meshes.new('Retopo500_Handle');hm.from_pydata(hv,[],hf);hm.materials.append(black);hm.update();handle=bpy.data.objects.new('Handle_500_Symmetric',hm);bpy.context.collection.objects.link(handle)
for p in hm.polygons:p.use_smooth=True
# Two identical eight-sided pivots, exact shared axis X and exact handle endpoint contacts.
def pivot(name,x):
 bpy.ops.mesh.primitive_cylinder_add(vertices=8,radius=.058,depth=.055,end_fill_type='NGON',location=(x,0,pz),rotation=(0,math.pi/2,0));o=bpy.context.object;o.name=name;o.data.materials.append(black)
 for p in o.data.polygons:p.use_smooth=True
 return o
pl=pivot('Pivot_L_500',-R);pr=pivot('Pivot_R_500',R)
objs=[body,handle,pl,pr]
# Contact and count gates.
contact=max(abs(path[0].x-R),abs(path[-1].x+R),abs(path[0].z-pz),abs(path[-1].z-pz))
mirror=max(abs(path[0].x+path[-1].x),abs(path[0].y-path[-1].y),abs(path[0].z-path[-1].z))
tri=sum(len(p.vertices)-2 for o in objs for p in o.data.polygons);poly=sum(len(o.data.polygons) for o in objs);vcount=sum(len(o.data.vertices) for o in objs)
if tri>520 or contact>1e-7 or mirror>1e-7:raise RuntimeError({'triangles':tri,'contact':contact,'mirror':mirror})
for o in objs:o.select_set(True)
bpy.ops.export_scene.gltf(filepath=out_glb,export_format='GLB',use_selection=True,export_materials='EXPORT')
# Fixed audit rig matching prior comparisons.
sc=bpy.context.scene;sc.render.engine='BLENDER_EEVEE_NEXT';sc.render.resolution_x=720;sc.render.resolution_y=720;sc.render.resolution_percentage=100;sc.render.image_settings.file_format='PNG';sc.view_settings.view_transform='Standard';sc.view_settings.look='Medium High Contrast'
sc.world=bpy.data.worlds.new('World');sc.world.use_nodes=True;sc.world.node_tree.nodes['Background'].inputs['Color'].default_value=(.018,.022,.03,1);sc.world.node_tree.nodes['Background'].inputs['Strength'].default_value=.28
for n,loc,en,sz in [('Key',(4,-5,7),900,5),('Fill',(-4,-2,4),450,4),('Rim',(2,5,5),650,3)]:
 ld=bpy.data.lights.new(n,'AREA');ld.energy=en;ld.size=sz;o=bpy.data.objects.new(n,ld);sc.collection.objects.link(o);o.location=loc
cd=bpy.data.cameras.new('Camera');cam=bpy.data.objects.new('Camera',cd);sc.collection.objects.link(cam);sc.camera=cam;cd.type='ORTHO';cd.ortho_scale=1.28;focus=Vector((0,0,.41))
def shot(n,pos):cam.location=Vector(pos);cam.rotation_euler=(focus-cam.location).to_track_quat('-Z','Y').to_euler();sc.render.filepath=os.path.join(render_dir,f'retopo500_{n}.png');bpy.ops.render.render(write_still=True)
shot('front',(0,-4,.48));shot('side',(4,0,.48));shot('back',(0,4,.48));shot('top',(0,0,4));shot('perspective',(1.8,-2.8,1.45))
st={'source_surface':src_clean,'objects':len(objs),'vertices':vcount,'polygons':poly,'triangles':tri,'body_segments':SEG,'handle_path_segments':PATH_STEPS,'handle_section_vertices':S,'contact_error':contact,'mirror_error':mirror,'materials':[ORANGE,BLACK]}
with open(os.path.join(render_dir,'retopo500_stats.json'),'w') as f:json.dump(st,f,indent=2)
print(json.dumps(st,indent=2))
