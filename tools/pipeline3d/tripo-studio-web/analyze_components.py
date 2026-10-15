import bpy, sys, json
from collections import defaultdict, deque
from mathutils import Vector

source = sys.argv[sys.argv.index('--') + 1]
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=source)
for obj in [o for o in bpy.context.scene.objects if o.type == 'MESH']:
    mesh = obj.data
    vert_faces = defaultdict(list)
    for p in mesh.polygons:
        for v in p.vertices:
            vert_faces[v].append(p.index)
    unseen = set(range(len(mesh.polygons)))
    components=[]
    while unseen:
        seed=unseen.pop(); q=[seed]; faces=[seed]
        while q:
            f=q.pop()
            for v in mesh.polygons[f].vertices:
                for nf in vert_faces[v]:
                    if nf in unseen:
                        unseen.remove(nf); q.append(nf); faces.append(nf)
        verts={v for f in faces for v in mesh.polygons[f].vertices}
        coords=[obj.matrix_world @ mesh.vertices[v].co for v in verts]
        lo=[min(c[i] for c in coords) for i in range(3)]
        hi=[max(c[i] for c in coords) for i in range(3)]
        components.append({'faces':len(faces),'verts':len(verts),'lo':lo,'hi':hi,'size':[hi[i]-lo[i] for i in range(3)],'face_indices':faces[:10]})
    components.sort(key=lambda x:x['faces'], reverse=True)
    print(json.dumps({'object':obj.name,'total_faces':len(mesh.polygons),'components':components}, indent=2))
