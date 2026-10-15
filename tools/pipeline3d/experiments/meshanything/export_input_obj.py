import bpy,sys,os
src,out=sys.argv[sys.argv.index('--')+1:]
bpy.ops.wm.read_factory_settings(use_empty=True);bpy.ops.import_scene.gltf(filepath=src)
objs=[o for o in bpy.context.scene.objects if o.type=='MESH']
for o in objs:o.select_set(True)
bpy.context.view_layer.objects.active=objs[0];bpy.ops.object.convert(target='MESH');bpy.ops.object.join();o=bpy.context.object
o.rotation_euler[0]=1.5707963267948966 # source +Z to MeshAnything preferred +Y
bpy.ops.object.transform_apply(location=False,rotation=True,scale=False)
bpy.ops.wm.obj_export(filepath=out,export_selected_objects=True,export_materials=False,forward_axis='NEGATIVE_Z',up_axis='Y')
print(out,len(o.data.vertices),len(o.data.polygons))
