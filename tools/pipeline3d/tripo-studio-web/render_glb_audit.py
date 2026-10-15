import bpy, math, os, sys, json
from mathutils import Vector

argv = sys.argv[sys.argv.index('--') + 1:]
source, out_dir = argv[0], argv[1]
os.makedirs(out_dir, exist_ok=True)

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=source)
meshes = [o for o in bpy.context.scene.objects if o.type == 'MESH']
if not meshes:
    raise RuntimeError('No meshes imported')

# Keep source geometry untouched; assign one neutral audit material only for rendering.
mat = bpy.data.materials.new('AuditClay')
mat.diffuse_color = (0.32, 0.36, 0.42, 1.0)
mat.use_nodes = True
bsdf = mat.node_tree.nodes.get('Principled BSDF')
bsdf.inputs['Base Color'].default_value = (0.16, 0.20, 0.26, 1.0)
bsdf.inputs['Roughness'].default_value = 0.72
for o in meshes:
    o.data.materials.clear()
    o.data.materials.append(mat)

corners = []
for o in meshes:
    corners.extend([o.matrix_world @ Vector(c) for c in o.bound_box])
lo = Vector((min(v.x for v in corners), min(v.y for v in corners), min(v.z for v in corners)))
hi = Vector((max(v.x for v in corners), max(v.y for v in corners), max(v.z for v in corners)))
center = (lo + hi) * 0.5
size = hi - lo
for o in meshes:
    o.location -= center

scene = bpy.context.scene
scene.render.engine = 'BLENDER_EEVEE_NEXT'
scene.render.resolution_x = 640
scene.render.resolution_y = 640
scene.render.resolution_percentage = 100
scene.render.image_settings.file_format = 'PNG'
scene.render.film_transparent = False
if scene.world is None:
    scene.world = bpy.data.worlds.new('AuditWorld')
scene.world.color = (0.035, 0.035, 0.045)
scene.view_settings.view_transform = 'Standard'
scene.view_settings.look = 'Medium High Contrast'
scene.render.image_settings.color_mode = 'RGBA'

world = scene.world
world.use_nodes = True
world.node_tree.nodes['Background'].inputs['Color'].default_value = (0.025, 0.03, 0.04, 1)
world.node_tree.nodes['Background'].inputs['Strength'].default_value = 0.35

key_data = bpy.data.lights.new('Key', 'AREA'); key_data.energy = 850; key_data.shape = 'DISK'; key_data.size = 5
key = bpy.data.objects.new('Key', key_data); scene.collection.objects.link(key); key.location = (4, -5, 7)
fill_data = bpy.data.lights.new('Fill', 'AREA'); fill_data.energy = 500; fill_data.size = 4
fill = bpy.data.objects.new('Fill', fill_data); scene.collection.objects.link(fill); fill.location = (-4, -1, 4)
rim_data = bpy.data.lights.new('Rim', 'AREA'); rim_data.energy = 700; rim_data.size = 3
rim = bpy.data.objects.new('Rim', rim_data); scene.collection.objects.link(rim); rim.location = (2, 5, 5)

cam_data = bpy.data.cameras.new('AuditCamera'); cam = bpy.data.objects.new('AuditCamera', cam_data); scene.collection.objects.link(cam)
scene.camera = cam; cam.data.type = 'ORTHO'
max_dim = max(size.x, size.y, size.z)
cam.data.ortho_scale = max_dim * 1.35

def point_camera(location):
    cam.location = Vector(location)
    direction = -cam.location
    cam.rotation_euler = direction.to_track_quat('-Z', 'Y').to_euler()

views = {
    'front': (0, -max_dim * 4, max_dim * 0.08),
    'side': (max_dim * 4, 0, max_dim * 0.08),
    'back': (0, max_dim * 4, max_dim * 0.08),
    'top': (0, 0, max_dim * 4),
}
for name, pos in views.items():
    point_camera(pos)
    scene.render.filepath = os.path.join(out_dir, f'tripo_{name}.png')
    bpy.ops.render.render(write_still=True)

stats = {
    'source': source,
    'objects': len(meshes),
    'vertices': sum(len(o.data.vertices) for o in meshes),
    'polygons': sum(len(o.data.polygons) for o in meshes),
    'triangles': sum(len(p.vertices) - 2 for o in meshes for p in o.data.polygons),
    'dimensions': [size.x, size.y, size.z],
    'object_names': [o.name for o in meshes],
}
with open(os.path.join(out_dir, 'tripo_stats.json'), 'w') as f:
    json.dump(stats, f, indent=2)
print(json.dumps(stats, indent=2))
