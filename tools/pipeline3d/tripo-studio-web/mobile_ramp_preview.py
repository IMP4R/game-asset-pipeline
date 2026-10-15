import bpy,sys,os
glb,out_dir=sys.argv[sys.argv.index('--')+1:];os.makedirs(out_dir,exist_ok=True)

def ramp_rgb(name,stops):
 t=bpy.data.node_groups.new(name,'ShaderNodeTree');t.nodes.new('NodeGroupInput');t.nodes.new('NodeGroupOutput')
 return t

def make_mat(name,base):
 m=bpy.data.materials.new(name);m.use_nodes=True;nt=m.node_tree
 for n in list(nt.nodes):nt.nodes.remove(n)
 out=nt.nodes.new('ShaderNodeOutputMaterial');em=nt.nodes.new('ShaderNodeEmission')
 geo=nt.nodes.new('ShaderNodeNewGeometry')
 dot=nt.nodes.new('ShaderNodeVectorMath');dot.operation='DOT_PRODUCT'
 dot.inputs[1].default_value=(-0.4016,-0.5020,0.7028)  # normalized key direction
 mad1=nt.nodes.new('ShaderNodeMath');mad1.operation='MULTIPLY_ADD';mad1.inputs[1].default_value=0.5;mad1.inputs[2].default_value=0.5
 cr=nt.nodes.new('ShaderNodeValToRGB');cr.color_ramp.interpolation='LINEAR'
 for pos,col in [(0.0,(0.34,0.34,0.34,1)),(0.3,(0.55,0.55,0.55,1)),(0.6,(0.85,0.85,0.85,1)),(1.0,(1.0,1.0,1.0,1))]:
  e=cr.color_ramp.elements.new(pos) if pos not in (0.0,) else cr.color_ramp.elements[0]
  if pos!=0.0:e.position=pos
  e.color=col
 sep=nt.nodes.new('ShaderNodeSeparateXYZ')
 mad2=nt.nodes.new('ShaderNodeMath');mad2.operation='MULTIPLY_ADD';mad2.inputs[1].default_value=0.5;mad2.inputs[2].default_value=0.5
 crh=nt.nodes.new('ShaderNodeValToRGB');crh.color_ramp.interpolation='LINEAR'
 crh.color_ramp.elements[0].position=0.0;crh.color_ramp.elements[0].color=(0.08,0.068,0.06,1)
 crh.color_ramp.elements[1].position=1.0;crh.color_ramp.elements[1].color=(0.38,0.36,0.34,1)
 crh.color_ramp.elements.new(0.5).color=(0.20,0.185,0.175,1)
 mul_l=nt.nodes.new('ShaderNodeMixRGB');mul_l.blend_type='MULTIPLY';mul_l.inputs['Fac'].default_value=1.0
 mul_l.inputs['Color2'].default_value=(0.95,0.92,0.86,1)
 mul_h=nt.nodes.new('ShaderNodeMixRGB');mul_h.blend_type='MULTIPLY';mul_h.inputs['Fac'].default_value=1.0
 mul_h.inputs['Color2'].default_value=(0.60,0.60,0.60,1)
 add=nt.nodes.new('ShaderNodeMixRGB');add.blend_type='ADD';add.inputs['Fac'].default_value=1.0
 mul_b=nt.nodes.new('ShaderNodeMixRGB');mul_b.blend_type='MULTIPLY';mul_b.inputs['Fac'].default_value=1.0
 mul_b.inputs['Color1'].default_value=base
 vgrad=nt.nodes.new('ShaderNodeMapRange');vgrad.inputs['From Min'].default_value=-0.02;vgrad.inputs['From Max'].default_value=0.85;vgrad.inputs['To Min'].default_value=0.78;vgrad.inputs['To Max'].default_value=1.0;vgrad.clamp=True
 mul_v=nt.nodes.new('ShaderNodeMixRGB');mul_v.blend_type='MULTIPLY';mul_v.inputs['Fac'].default_value=1.0
 geo2=nt.nodes.new('ShaderNodeTexCoord')
 sep2=nt.nodes.new('ShaderNodeSeparateXYZ')
 nt.links.new(geo.outputs['Normal'],dot.inputs[0])
 nt.links.new(dot.outputs['Value'],mad1.inputs[0])
 nt.links.new(mad1.outputs['Value'],cr.inputs['Fac'])
 nt.links.new(cr.outputs['Color'],mul_l.inputs['Color1'])
 nt.links.new(geo.outputs['Normal'],sep.inputs[0])
 nt.links.new(sep.outputs['Z'],mad2.inputs[0])
 nt.links.new(mad2.outputs['Value'],crh.inputs['Fac'])
 nt.links.new(crh.outputs['Color'],mul_h.inputs['Color1'])
 nt.links.new(mul_l.outputs['Color'],add.inputs['Color1'])
 nt.links.new(mul_h.outputs['Color'],add.inputs['Color2'])
 nt.links.new(geo2.outputs['Object'],sep2.inputs[0])
 nt.links.new(sep2.outputs['Z'],vgrad.inputs['Value'])
 nt.links.new(add.outputs['Color'],mul_v.inputs['Color1'])
 nt.links.new(vgrad.outputs['Result'],mul_v.inputs['Color2'])
 nt.links.new(mul_v.outputs['Color'],mul_b.inputs['Color2'])
 nt.links.new(mul_b.outputs['Color'],em.inputs['Color'])
 nt.links.new(em.outputs['Emission'],out.inputs['Surface'])
 return m

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=glb)
objs=[o for o in bpy.context.scene.objects if o.type=='MESH']
orange=make_mat('MobileOrange',(1.0,0.29,0.012,1));black=make_mat('MobileBlack',(0.055,0.062,0.075,1))
for o in objs:o.data.materials.clear();o.data.materials.append(orange if ('Body' in o.name or 'Rim' in o.name) else black)
sc=bpy.context.scene;sc.render.engine='BLENDER_EEVEE_NEXT';sc.render.resolution_x=700;sc.render.resolution_y=700;sc.render.resolution_percentage=100;sc.render.image_settings.file_format='PNG';sc.view_settings.view_transform='Standard'
sc.world=bpy.data.worlds.new('W');sc.world.use_nodes=True;sc.world.node_tree.nodes['Background'].inputs['Color'].default_value=(.018,.022,.03,1)
cd=bpy.data.cameras.new('Camera');cam=bpy.data.objects.new('Camera',cd);sc.collection.objects.link(cam);sc.camera=cam;cd.type='ORTHO';cd.ortho_scale=1.28
from mathutils import Vector;focus=Vector((0,0,.41))
def shot(v,p):cam.location=Vector(p);cam.rotation_euler=(focus-cam.location).to_track_quat('-Z','Y').to_euler();sc.render.filepath=os.path.join(out_dir,f'mobile_{v}.png');bpy.ops.render.render(write_still=True)
shot('front',(0,-4,.48));shot('perspective',(1.8,-2.8,1.45));shot('top',(0,0,4))
print('mobile shader preview done:',out_dir)
