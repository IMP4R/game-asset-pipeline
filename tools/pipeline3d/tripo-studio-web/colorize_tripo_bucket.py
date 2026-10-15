import bpy, sys, os, json
from collections import defaultdict
from mathutils import Vector

args = sys.argv[sys.argv.index('--') + 1:]
source, output, render_dir = args[0], args[1], args[2]
os.makedirs(render_dir, exist_ok=True)

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=source)
meshes = [o for o in bpy.context.scene.objects if o.type == 'MESH']
if len(meshes) != 1:
    raise RuntimeError(f'Expected one mesh, found {len(meshes)}')
obj = meshes[0]
mesh = obj.data

def srgb_channel(v):
    v /= 255.0
    return v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4

def material(name, hex_color, roughness):
    rgb = tuple(srgb_channel(int(hex_color[i:i+2], 16)) for i in (1,3,5))
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    bsdf = m.node_tree.nodes.get('Principled BSDF')
    bsdf.inputs['Base Color'].default_value = (*rgb, 1.0)
    bsdf.inputs['Roughness'].default_value = roughness
    bsdf.inputs['Metallic'].default_value = 0.0
    return m

orange = material('Bucket Orange #FF8E00', '#FF8E00', 0.48)
black = material('Handle Black #2E2E33', '#2E2E33', 0.58)
mesh.materials.clear(); mesh.materials.append(orange); mesh.materials.append(black)

# Connected components: largest is the bucket body/rim/interior; the remaining
# three are the handle arc and its two pivot caps. Geometry is not modified.
vert_faces = defaultdict(list)
for p in mesh.polygons:
    for v in p.vertices: vert_faces[v].append(p.index)
unseen = set(range(len(mesh.polygons))); components=[]
while unseen:
    seed=unseen.pop(); stack=[seed]; faces=[seed]
    while stack:
        f=stack.pop()
        for v in mesh.polygons[f].vertices:
            for nf in vert_faces[v]:
                if nf in unseen:
                    unseen.remove(nf); stack.append(nf); faces.append(nf)
    components.append(faces)
components.sort(key=len, reverse=True)
for p in mesh.polygons: p.material_index = 0
for comp in components[1:]:
    for fi in comp: mesh.polygons[fi].material_index = 1

# Export colored game asset.
bpy.context.view_layer.objects.active = obj; obj.select_set(True)
bpy.ops.export_scene.gltf(filepath=output, export_format='GLB', use_selection=True, export_materials='EXPORT')

# Presentation renders.
corners=[obj.matrix_world @ Vector(c) for c in obj.bound_box]
lo=Vector((min(v.x for v in corners),min(v.y for v in corners),min(v.z for v in corners)))
hi=Vector((max(v.x for v in corners),max(v.y for v in corners),max(v.z for v in corners)))
center=(lo+hi)*0.5; size=hi-lo; obj.location -= center
scene=bpy.context.scene; scene.render.engine='BLENDER_EEVEE_NEXT'; scene.render.resolution_x=640; scene.render.resolution_y=640; scene.render.resolution_percentage=100
scene.render.image_settings.file_format='PNG'; scene.view_settings.view_transform='Standard'; scene.view_settings.look='Medium High Contrast'
scene.world=bpy.data.worlds.new('World'); scene.world.use_nodes=True
scene.world.node_tree.nodes['Background'].inputs['Color'].default_value=(0.018,0.022,0.03,1); scene.world.node_tree.nodes['Background'].inputs['Strength'].default_value=0.28
for name, loc, energy, size_l in [('Key',(4,-5,7),950,5),('Fill',(-4,-2,4),500,4),('Rim',(2,5,5),750,3)]:
    ld=bpy.data.lights.new(name,'AREA'); ld.energy=energy; ld.size=size_l
    light=bpy.data.objects.new(name,ld); scene.collection.objects.link(light); light.location=loc
camd=bpy.data.cameras.new('Camera'); cam=bpy.data.objects.new('Camera',camd); scene.collection.objects.link(cam); scene.camera=cam; camd.type='ORTHO'
maxd=max(size); camd.ortho_scale=maxd*1.35
def render(name, pos):
    cam.location=Vector(pos); cam.rotation_euler=(-cam.location).to_track_quat('-Z','Y').to_euler(); scene.render.filepath=os.path.join(render_dir,f'painted_{name}.png'); bpy.ops.render.render(write_still=True)
render('front',(0,-maxd*4,maxd*.08)); render('side',(maxd*4,0,maxd*.08)); render('back',(0,maxd*4,maxd*.08)); render('top',(0,0,maxd*4))
with open(os.path.join(render_dir,'painted_stats.json'),'w') as f:
    json.dump({'components':[len(c) for c in components],'orange_faces':len(components[0]),'black_faces':sum(len(c) for c in components[1:]),'materials':['#FF8E00','#2E2E33'],'geometry_modified':False},f,indent=2)
print(json.dumps({'output':output,'components':[len(c) for c in components],'geometry_modified':False},indent=2))
