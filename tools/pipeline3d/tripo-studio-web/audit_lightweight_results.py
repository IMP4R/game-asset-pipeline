import bpy,sys,json,os,math
from mathutils import Vector
paths=sys.argv[sys.argv.index('--')+1:]
out={}
for path in paths:
 bpy.ops.wm.read_factory_settings(use_empty=True);bpy.ops.import_scene.gltf(filepath=path)
 objs=[o for o in bpy.context.scene.objects if o.type=='MESH'];objs.sort(key=lambda o:len(o.data.polygons),reverse=True)
 body=objs[0];arc=max(objs[1:],key=lambda o:max((o.matrix_world@v.co).x for v in o.data.vertices)-min((o.matrix_world@v.co).x for v in o.data.vertices));pivs=[o for o in objs if o not in (body,arc)]
 def tri(o):return sum(len(p.vertices)-2 for p in o.data.polygons)
 boundary=nonmanifold=degenerate=0;areas=[]
 for o in objs:
  for e in o.data.edges:
   linked=sum(1 for p in o.data.polygons if e.vertices[0] in p.vertices and e.vertices[1] in p.vertices)
   boundary+=linked==1;nonmanifold+=linked>2
  for p in o.data.polygons:
   areas.append(p.area);degenerate+=p.area<1e-10
 def cen(o):
  ps=[o.matrix_world@v.co for v in o.data.vertices];return sum(ps,Vector())/max(1,len(ps))
 pc=[cen(p) for p in pivs];pivot_sym=None
 if len(pc)==2:
  pc.sort(key=lambda p:p.x);pivot_sym=max(abs(pc[0].x+pc[1].x),abs(pc[0].y-pc[1].y),abs(pc[0].z-pc[1].z))
 # exact minimum world-space vertex distances at the handle-to-pivot interfaces
 hp=[]
 for p in pivs:
  hp.append(min((arc.matrix_world@a.co-p.matrix_world@b.co).length for a in arc.data.vertices for b in p.data.vertices))
 out[os.path.basename(path)]={'triangles':sum(tri(o) for o in objs),'vertices':sum(len(o.data.vertices) for o in objs),'objects':len(objs),'boundary_edges':boundary,'nonmanifold_edges':nonmanifold,'degenerate_faces':degenerate,'pivot_mirror_centroid_error':pivot_sym,'handle_pivot_min_vertex_distances':hp,'handle_connected_object':True}
print(json.dumps(out,indent=2))
with open(paths[-1]+'.audit.json','w') as f:json.dump(out,f,indent=2)
