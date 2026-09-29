
import bpy, bmesh, math, random
from mathutils import Vector

def coll(name, parent=None):
    c = bpy.data.collections.get(name)
    if not c:
        c = bpy.data.collections.new(name)
        (parent or bpy.context.scene.collection).children.link(c)
    return c

def mat(name, color=(0.5,0.5,0.5), metal=0.0, rough=0.5, emit=None, strength=0.0, alpha=1.0, transmission=0.0):
    m = bpy.data.materials.get(name)
    if m: return m
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    for n in list(nt.nodes): nt.nodes.remove(n)
    out = nt.nodes.new("ShaderNodeOutputMaterial"); out.location=(300,0)
    b = nt.nodes.new("ShaderNodeBsdfPrincipled")
    b.inputs["Base Color"].default_value = (*color,1)
    b.inputs["Metallic"].default_value = metal
    b.inputs["Roughness"].default_value = rough
    if transmission: b.inputs["Transmission Weight"].default_value = transmission
    if emit:
        b.inputs["Emission Color"].default_value = (*emit,1)
        b.inputs["Emission Strength"].default_value = strength
    if alpha < 1:
        b.inputs["Alpha"].default_value = alpha
    nt.links.new(b.outputs[0], out.inputs[0])
    m.diffuse_color = (*(emit if emit and strength>0 else color), alpha)
    m.metallic = metal; m.roughness = rough
    return m

def _obj(name, me, c, m):
    o = bpy.data.objects.new(name, me)
    c.objects.link(o)
    if m: me.materials.append(m)
    return o

def box(name, size, loc, m=None, c=None, rot=0.0, bevel=0.0):
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    for v in bm.verts:
        v.co.x *= size[0]; v.co.y *= size[1]; v.co.z *= size[2]
    bm.to_mesh(me); bm.free()
    o = _obj(name, me, c or bpy.context.scene.collection, m)
    o.location = loc; o.rotation_euler.z = rot
    if bevel:
        md = o.modifiers.new("Bevel","BEVEL"); md.width = bevel; md.segments = 2
    return o

def cyl(name, r, h, loc, m=None, c=None, seg=24, rot=(0,0,0)):
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, segments=seg, radius1=r, radius2=r, depth=h)
    bm.to_mesh(me); bm.free()
    for p in me.polygons: p.use_smooth = True
    o = _obj(name, me, c or bpy.context.scene.collection, m)
    o.location = loc; o.rotation_euler = rot
    return o

def cone(name, r1, r2, h, loc, m=None, c=None, seg=12):
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, segments=seg, radius1=r1, radius2=r2, depth=h)
    bm.to_mesh(me); bm.free()
    o = _obj(name, me, c or bpy.context.scene.collection, m)
    o.location = loc
    return o

def sphere(name, r, loc, m=None, c=None, sub=2):
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    bmesh.ops.create_icosphere(bm, subdivisions=sub, radius=r)
    bm.to_mesh(me); bm.free()
    o = _obj(name, me, c or bpy.context.scene.collection, m)
    o.location = loc
    return o

def beam(name, p1, p2, thick, m=None, c=None):
    p1, p2 = Vector(p1), Vector(p2)
    d = p2 - p1
    o = box(name, (thick, thick, d.length), (p1+p2)/2, m, c)
    o.rotation_mode = "QUATERNION"
    o.rotation_quaternion = Vector((0,0,1)).rotation_difference(d.normalized())
    return o

def join(objs, name):
    objs = [o for o in objs if o]
    if len(objs) == 1:
        objs[0].name = name; return objs[0]
    ctx = {"active_object": objs[0], "selected_editable_objects": objs, "selected_objects": objs}
    with bpy.context.temp_override(**ctx):
        bpy.ops.object.join()
    objs[0].name = name
    return objs[0]

def text(name, body, loc, size, m=None, c=None, rot=(math.radians(90),0,0), extrude=0.05, align="CENTER"):
    cu = bpy.data.curves.new(name, "FONT")
    cu.body = body; cu.size = size; cu.extrude = extrude; cu.align_x = align; cu.align_y = "CENTER"
    o = bpy.data.objects.new(name, cu)
    (c or bpy.context.scene.collection).objects.link(o)
    if m: cu.materials.append(m)
    o.location = loc; o.rotation_euler = rot
    return o
