import bpy, math, os, sys, json
from mathutils import Vector

args = sys.argv[sys.argv.index('--') + 1:]
out_glb, render_dir = args[0], args[1]
os.makedirs(render_dir, exist_ok=True)
bpy.ops.wm.read_factory_settings(use_empty=True)

SEG = 24
ORANGE = '#FF8E00'
BLACK = '#2E2E33'

def linear(v):
    v /= 255.0
    return v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4

def make_mat(name, hx, rough=.5):
    rgb = tuple(linear(int(hx[i:i+2], 16)) for i in (1,3,5))
    m = bpy.data.materials.new(name); m.use_nodes = True
    b = m.node_tree.nodes['Principled BSDF']
    b.inputs['Base Color'].default_value = (*rgb, 1)
    b.inputs['Roughness'].default_value = rough
    return m
orange = make_mat('Bucket Orange', ORANGE, .48)
black = make_mat('Handle Black', BLACK, .6)

# One continuous hollow bucket shell. Profile runs outside bottom->rim, then inside rim->floor.
# Ratios derived from the accepted Tripo silhouette and the epure; exact axial symmetry is enforced.
profile = [
    (.385, .025), (.400, .000), (.420, .035),
    (.455, .545), (.462, .590),
    (.485, .604), (.505, .628), (.508, .670), (.500, .706), (.480, .724),
    (.451, .713), (.438, .680), (.430, .635),
    (.405, .145), (.390, .105), (.370, .090),
    (.000, .090),
]
verts=[]
for r,z in profile:
    if r == 0:
        verts.append((0,0,z))
    else:
        for i in range(SEG):
            a=2*math.pi*i/SEG; verts.append((r*math.cos(a), r*math.sin(a), z))
faces=[]
ring_starts=[]; cursor=0
for r,z in profile:
    ring_starts.append(cursor); cursor += 1 if r==0 else SEG
for j in range(len(profile)-1):
    r1,_=profile[j]; r2,_=profile[j+1]; s1=ring_starts[j]; s2=ring_starts[j+1]
    if r2 == 0:
        for i in range(SEG): faces.append((s1+i, s1+(i+1)%SEG, s2))
    elif r1 == 0:
        for i in range(SEG): faces.append((s1, s2+(i+1)%SEG, s2+i))
    else:
        for i in range(SEG): faces.append((s1+i, s1+(i+1)%SEG, s2+(i+1)%SEG, s2+i))
mesh=bpy.data.meshes.new('BucketBodyMesh'); mesh.from_pydata(verts,[],faces); mesh.materials.append(orange); mesh.update()
body=bpy.data.objects.new('Bucket_Body_Symmetric_LowPoly',mesh); bpy.context.collection.objects.link(body)
for p in mesh.polygons: p.use_smooth=True

# Symmetric folded handle: one connected half-arc from left pivot to right pivot around the front.
# Front is -Y. Endpoints are anchored at the two pivot center planes.
R=.515; pivot_z=.625; sag=.105; path_steps=16
half_w=.034   # radial strap half-thickness
half_h=.044   # vertical strap half-height
# Rounded-rectangle cross-section in the local radial/vertical plane (8 points).
section=[(-half_w,-half_h),(.0,-half_h),(half_w,-half_h),(half_w,0),(half_w,half_h),(0,half_h),(-half_w,half_h),(-half_w,0)]
path=[]
for i in range(path_steps+1):
    t=math.pi*i/path_steps
    path.append(Vector((R*math.cos(t), -R*math.sin(t), pivot_z-sag*math.sin(t))))
hv=[]
for i,c in enumerate(path):
    prev=path[max(0,i-1)]; nxt=path[min(path_steps,i+1)]
    tangent=(nxt-prev).normalized()
    radial=Vector((c.x,c.y,0)).normalized()
    vertical=tangent.cross(radial).normalized()
    if vertical.z < 0: vertical=-vertical
    for rw,vh in section: hv.append(tuple(c + radial*rw + vertical*vh))
hf=[]; S=len(section)
for j in range(path_steps):
    for k in range(S): hf.append((j*S+k,j*S+(k+1)%S,(j+1)*S+(k+1)%S,(j+1)*S+k))
hf.append(tuple(range(S-1,-1,-1))); hf.append(tuple(path_steps*S+k for k in range(S)))
hmesh=bpy.data.meshes.new('HandleArcMesh'); hmesh.from_pydata(hv,[],hf); hmesh.materials.append(black); hmesh.update()
handle=bpy.data.objects.new('Handle_One_Symmetric_Arc',hmesh); bpy.context.collection.objects.link(handle)
for p in hmesh.polygons: p.use_smooth=True

# Two identical pivot assemblies, mirrored exactly across X=0. Cylinder axis is X.
def cylinder(name, x, radius, depth, material, segments=12):
    bpy.ops.mesh.primitive_cylinder_add(vertices=segments, radius=radius, depth=depth, location=(x,0,pivot_z), rotation=(0,math.pi/2,0))
    o=bpy.context.object; o.name=name; o.data.materials.append(material)
    for p in o.data.polygons: p.use_smooth=True
    return o
left_base=cylinder('Pivot_Base_L',-R,.061,.045,black)
right_base=cylinder('Pivot_Base_R',R,.061,.045,black)
left_cap=cylinder('Pivot_Cap_L',-R-.026,.043,.018,black)
right_cap=cylinder('Pivot_Cap_R',R+.026,.043,.018,black)

# Contact audit: handle endpoints must overlap their pivot cylinders, and mirrored bounds must agree.
end_l=path[-1]  # x=-R
end_r=path[0]   # x=+R
contact_error=max(abs(end_l.x+R),abs(end_r.x-R),abs(end_l.z-pivot_z),abs(end_r.z-pivot_z))
mirror_error=max(abs(end_l.x+end_r.x),abs(end_l.y-end_r.y),abs(end_l.z-end_r.z))
if contact_error > 1e-6 or mirror_error > 1e-6: raise RuntimeError((contact_error,mirror_error))

# Flat-ish game shading: smooth curved rings, auto smooth by angle through geometry normals.
for o in [body,handle,left_base,right_base,left_cap,right_cap]:
    o.select_set(True)

bpy.ops.export_scene.gltf(filepath=out_glb, export_format='GLB', use_selection=True, export_materials='EXPORT')

# Render orthographic verification views.
scene=bpy.context.scene; scene.render.engine='BLENDER_EEVEE_NEXT'; scene.render.resolution_x=640; scene.render.resolution_y=640; scene.render.resolution_percentage=100
scene.render.image_settings.file_format='PNG'; scene.view_settings.view_transform='Standard'; scene.view_settings.look='Medium High Contrast'
scene.world=bpy.data.worlds.new('World'); scene.world.use_nodes=True
scene.world.node_tree.nodes['Background'].inputs['Color'].default_value=(.018,.022,.03,1); scene.world.node_tree.nodes['Background'].inputs['Strength'].default_value=.28
for name,loc,energy,size in [('Key',(4,-5,7),900,5),('Fill',(-4,-2,4),450,4),('Rim',(2,5,5),650,3)]:
    ld=bpy.data.lights.new(name,'AREA'); ld.energy=energy; ld.size=size
    o=bpy.data.objects.new(name,ld); scene.collection.objects.link(o); o.location=loc
camd=bpy.data.cameras.new('Camera'); cam=bpy.data.objects.new('Camera',camd); scene.collection.objects.link(cam); scene.camera=cam; camd.type='ORTHO'; camd.ortho_scale=1.42
center=Vector((0,0,.36))
def shot(name,pos):
    cam.location=Vector(pos); cam.rotation_euler=(center-cam.location).to_track_quat('-Z','Y').to_euler(); scene.render.filepath=os.path.join(render_dir,f'clean_{name}.png'); bpy.ops.render.render(write_still=True)
shot('front',(0,-4,.45)); shot('side',(4,0,.45)); shot('back',(0,4,.45)); shot('top',(0,0,4))

stats={
  'objects':6,
  'vertices':sum(len(o.data.vertices) for o in [body,handle,left_base,right_base,left_cap,right_cap]),
  'polygons':sum(len(o.data.polygons) for o in [body,handle,left_base,right_base,left_cap,right_cap]),
  'triangles':sum(len(p.vertices)-2 for o in [body,handle,left_base,right_base,left_cap,right_cap] for p in o.data.polygons),
  'body_segments':SEG,'handle_path_segments':path_steps,'handle_section_vertices':S,
  'contact_error':contact_error,'mirror_error':mirror_error,
  'materials':[ORANGE,BLACK]
}
with open(os.path.join(render_dir,'clean_stats.json'),'w') as f: json.dump(stats,f,indent=2)
print(json.dumps(stats,indent=2))
