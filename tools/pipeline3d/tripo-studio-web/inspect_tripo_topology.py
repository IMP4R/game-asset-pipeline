import bpy,sys,json,math
from collections import defaultdict
source=sys.argv[sys.argv.index('--')+1]
bpy.ops.wm.read_factory_settings(use_empty=True); bpy.ops.import_scene.gltf(filepath=source)
o=next(x for x in bpy.context.scene.objects if x.type=='MESH'); bpy.context.view_layer.objects.active=o; o.select_set(True)
bpy.ops.object.mode_set(mode='EDIT'); bpy.ops.mesh.separate(type='LOOSE'); bpy.ops.object.mode_set(mode='OBJECT')
parts=[x for x in bpy.context.selected_objects if x.type=='MESH']
res=[]
for p in parts:
 vs=[p.matrix_world@v.co for v in p.data.vertices]
 lo=[min(v[i] for v in vs) for i in range(3)]; hi=[max(v[i] for v in vs) for i in range(3)]
 zbins=defaultdict(list)
 for v in vs: zbins[round(v.z,4)].append(math.hypot(v.x,v.y))
 rows=sorted([(z,len(rs),min(rs),max(rs)) for z,rs in zbins.items()],key=lambda x:x[0])
 res.append({'name':p.name,'verts':len(vs),'faces':len(p.data.polygons),'lo':lo,'hi':hi,'z_rows_count':len(rows),'largest_z_rows':sorted(rows,key=lambda x:x[1],reverse=True)[:20]})
print(json.dumps(res,indent=2))
