import bpy,sys,os,numpy as np,json
src,out=sys.argv[sys.argv.index('--')+1:]
bpy.ops.wm.read_factory_settings(use_empty=True);bpy.ops.import_scene.gltf(filepath=src)
o=next(x for x in bpy.context.scene.objects if x.type=='MESH');bpy.context.view_layer.objects.active=o;o.select_set(True)
bpy.ops.object.mode_set(mode='EDIT');bpy.ops.mesh.separate(type='LOOSE');bpy.ops.object.mode_set(mode='OBJECT')
parts=[x for x in bpy.context.selected_objects if x.type=='MESH']
parts.sort(key=lambda p:len(p.data.polygons),reverse=True)
arrays={};meta=[]
for i,p in enumerate(parts):
 v=np.array([tuple(p.matrix_world@x.co) for x in p.data.vertices],dtype=np.float32)
 arrays[f'v{i}']=v
 meta.append({'index':i,'vertices':len(v),'polygons':len(p.data.polygons),'bbox_min':v.min(0).tolist(),'bbox_max':v.max(0).tolist()})
np.savez(out,**arrays)
with open(out+'.json','w') as f:json.dump(meta,f,indent=2)
print(json.dumps(meta,indent=2))
