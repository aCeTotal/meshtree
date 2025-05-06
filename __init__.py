bl_info = {
    "name":        "MeshTree",
    "author":      "Lars Øksendal aka. [aCe]Total",
    "version":     (1, 0),
    "blender":     (4, 4, 0),
    "location":    "View3D > Sidebar > MeshTree",
    "description": "One way to create trees in Blender"
}

import bpy, math
from mathutils import Vector, Matrix
from bpy.types import Operator, Panel

def update_tree(self, context):
    bpy.ops.curve.add_simple_tree('INVOKE_DEFAULT')

# Scene properties
S = bpy.types.Scene
S.tree_height           = bpy.props.FloatProperty("Trunk Height", default=2.0, min=0.1, max=10.0, update=update_tree)
S.trunk_diameter_bottom = bpy.props.FloatProperty("Dia Bottom", default=0.2, min=0.01, max=2.0, update=update_tree)
S.trunk_diameter_middle = bpy.props.FloatProperty("Dia Middle", default=0.1, min=0.01, max=2.0, update=update_tree)
S.trunk_diameter_top    = bpy.props.FloatProperty("Dia Top", default=0.05, min=0.01, max=2.0, update=update_tree)
S.trunk_bend            = bpy.props.FloatProperty("Bend Amount", default=0.0, min=0.0, max=1.0, update=update_tree)
S.trunk_bend_start      = bpy.props.FloatProperty("Bend Start", default=0.0, min=0.0, max=1.0, update=update_tree)

for i in range(1,7):
    setattr(S, f"branch{i}_height",
        bpy.props.FloatProperty(f"Ring {i} Height", default=0.2*i/6, min=0.0, max=1.0, update=update_tree))
    setattr(S, f"branch{i}_count",
        bpy.props.IntProperty(f"Ring {i} Count", default=0, min=0, max=50, update=update_tree))
    # rename Angle → Rotate
    setattr(S, f"branch{i}_rotate",
        bpy.props.FloatProperty(f"Ring {i} Rotate", default=0.0, min=0.0, max=360.0, update=update_tree))
    # new up/down Angle along trunk normals
    setattr(S, f"branch{i}_angle",
        bpy.props.FloatProperty(f"Ring {i} Angle", default=0.0, min=-90.0, max=90.0, update=update_tree))
    setattr(S, f"branch{i}_bend",
        bpy.props.FloatProperty(f"Ring {i} Bend", default=0.0, min=0.0, max=1.0, update=update_tree))
    setattr(S, f"branch{i}_penetration",
        bpy.props.FloatProperty(f"Ring {i} Penetration", default=0.0, min=-1.0, max=1.0, update=update_tree))
    setattr(S, f"branch{i}_length",
        bpy.props.FloatProperty(f"Ring {i} Length", default=1.0, min=0.0, max=2.0, update=update_tree))
    setattr(S, f"branch{i}_diameter",
        bpy.props.FloatProperty(f"Ring {i} Diameter", default=0.05, min=0.01, max=1.0, update=update_tree))

def make_trunk_and_branches(context):
    sc = context.scene
    H = sc.tree_height; d_bot = sc.trunk_diameter_bottom
    d_mid = sc.trunk_diameter_middle; d_top = sc.trunk_diameter_top
    bend_fac = sc.trunk_bend; bend_start = sc.trunk_bend_start

    # cleanup
    for name in ("CurveTreeCurve","CurveTreeMesh"):
        old = bpy.data.objects.get(name)
        if old: bpy.data.objects.remove(old, do_unlink=True)

    # create curve
    C = bpy.data.curves.new("CurveTreeCurve", 'CURVE'); C.dimensions='3D'
    C.fill_mode='FULL'; C.bevel_resolution=16; C.use_fill_caps=True
    obj_c = bpy.data.objects.new("CurveTreeCurve", C)
    context.collection.objects.link(obj_c)
    obj_c.location = sc.cursor.location
    max_ang = bend_fac * math.pi/2

    spl = C.splines.new('BEZIER'); spl.bezier_points.add(4)
    N = len(spl.bezier_points)
    for idx, bp in enumerate(spl.bezier_points):
        t = idx/(N-1); z = H*t
        ang = t>bend_start and max_ang*(t-bend_start)/(1-bend_start) or 0.0
        bp.co = Matrix.Rotation(ang,4,'Y') @ Vector((0,0,z))
        bp.handle_left_type=bp.handle_right_type='AUTO'
        bp.radius = (t<0.5 and ((1-t/0.5)*d_bot + (t/0.5)*d_mid)) or (((1-(t-0.5)/0.5)*d_mid + ((t-0.5)/0.5)*d_top))
    spl.use_cyclic_u=False; C.bevel_depth=d_mid

    wm = obj_c.matrix_world; wmi = wm.inverted()

    # sample ring around trunk
    sample_local = [Vector((math.cos(a), math.sin(a), 0)) for a in [i*2*math.pi/16 for i in range(16)]]

    centers = {}
    for i in range(1,7):
        t0 = getattr(sc,f"branch{i}_height")
        cnt = getattr(sc,f"branch{i}_count")
        if cnt==0: continue

        # ring position and local bend
        t_ang = t0>bend_start and max_ang*(t0-bend_start)/(1-bend_start) or 0.0
        local_p = Matrix.Rotation(t_ang,4,'Y')@Vector((0,0,H*t0))
        if t0<0.5:
            r0 = (1-t0/0.5)*d_bot + (t0/0.5)*d_mid
        else:
            r0 = (1-(t0-0.5)/0.5)*d_mid + ((t0-0.5)/0.5)*d_top
        world_p = wm@local_p

        # raycast to find true center
        hits = []
        for dir_local in sample_local:
            dir_world = wm.to_3x3()@dir_local
            hit, loc, *_ = obj_c.ray_cast(world_p + dir_world*(r0*2), -dir_world)
            if hit:
                hits.append(loc)
        centers[i] = ((sum(hits, Vector())/len(hits)) if hits else world_p, r0, t_ang)

    # create branches
    for i in range(1,7):
        cnt = getattr(sc,f"branch{i}_count")
        if cnt==0: continue
        base_rot = math.radians(getattr(sc,f"branch{i}_rotate"))
        elev_ang = math.radians(getattr(sc,f"branch{i}_angle"))
        rb = getattr(sc,f"branch{i}_bend")
        pen = getattr(sc,f"branch{i}_penetration")
        ln = getattr(sc,f"branch{i}_length")
        dia= getattr(sc,f"branch{i}_diameter")
        center_ws, r0, t_ang = centers[i]

        # trunk tangent in local space
        tangent_local = Matrix.Rotation(t_ang,4,'Y') @ Vector((0,0,1))

        for k in range(cnt):
            th = base_rot + k*(2*math.pi/cnt)
            dir_local = Vector((math.cos(th), math.sin(th), 0))
            # apply elevation around axis perpendicular to trunk
            axis = tangent_local.cross(dir_local)
            if axis.length != 0:
                axis.normalize()
                dir_local = (Matrix.Rotation(elev_ang,4,axis) @ dir_local).normalized()

            dir_world = wm.to_3x3()@dir_local
            base_ws = center_ws + dir_world*(r0*pen)
            base_ls = wmi@base_ws

            bend_branch = rb*max_ang
            Mbb = Matrix.Rotation(bend_branch,4,'Y')
            blen = H*0.2*ln
            spl2 = C.splines.new('BEZIER'); spl2.bezier_points.add(3)
            for j,bp2 in enumerate(spl2.bezier_points):
                tt=j/(len(spl2.bezier_points)-1)
                pt = base_ls + dir_local*(blen*tt)
                pt.z += H*0.05*tt
                bp2.co = Mbb@pt
                bp2.handle_left_type=bp2.handle_right_type='AUTO'
                bp2.radius = dia
            spl2.use_cyclic_u=False

    # convert to mesh
    context.view_layer.objects.active=obj_c; obj_c.select_set(True)
    bpy.ops.object.convert(target='MESH')
    mesh = context.view_layer.objects.active
    mesh.name="CurveTreeMesh"; mesh.data.name="CurveTreeMesh"
    return mesh

class CURVE_OT_add_simple_tree(Operator):
    bl_idname="curve.add_simple_tree"; bl_label="Add Trunk"; bl_options={'REGISTER','UNDO'}
    def execute(self,context):
        make_trunk_and_branches(context); return{'FINISHED'}
    def invoke(self,context,event):
        return self.execute(context)

class VIEW3D_PT_add_trunk(Panel):
    bl_label="Add Trunk"; bl_idname="VIEW3D_PT_add_trunk"
    bl_space_type='VIEW_3D'; bl_region_type='UI'; bl_category='MeshTree'
    def draw(self,context):
        self.layout.operator("curve.add_simple_tree",icon='CURVE_DATA')

class VIEW3D_PT_trunk_settings(Panel):
    bl_label="Trunk Settings"; bl_parent_id="VIEW3D_PT_add_trunk"
    bl_space_type='VIEW_3D'; bl_region_type='UI'; bl_options={'DEFAULT_CLOSED'}
    def draw(self,context):
        sc=context.scene; l=self.layout
        box=l.box(); box.label(text="Diameter")
        box.prop(sc,"trunk_diameter_bottom"); box.prop(sc,"trunk_diameter_middle"); box.prop(sc,"trunk_diameter_top")
        box2=l.box(); box2.label(text="Bend")
        box2.prop(sc,"trunk_bend_start"); box2.prop(sc,"trunk_bend")
        l.separator(); l.prop(sc,"tree_height")

class VIEW3D_PT_branch_settings(Panel):
    bl_label="Branch Settings"; bl_parent_id="VIEW3D_PT_add_trunk"
    bl_space_type='VIEW_3D'; bl_region_type='UI'; bl_options={'DEFAULT_CLOSED'}
    def draw(self,context):
        sc=context.scene; l=self.layout
        for i in range(1,7):
            b=l.box(); b.label(text=f"Branch Ring {i}")
            b.prop(sc,f"branch{i}_height"); b.prop(sc,f"branch{i}_count")
            b.prop(sc,f"branch{i}_rotate");  b.prop(sc,f"branch{i}_angle")
            b.prop(sc,f"branch{i}_bend"); b.prop(sc,f"branch{i}_penetration")
            b.prop(sc,f"branch{i}_length"); b.prop(sc,f"branch{i}_diameter")

classes = (CURVE_OT_add_simple_tree, VIEW3D_PT_add_trunk, VIEW3D_PT_trunk_settings, VIEW3D_PT_branch_settings)

def register():
    for c in classes: bpy.utils.register_class(c)
def unregister():
    for c in reversed(classes): bpy.utils.unregister_class(c)
    props = [
        "tree_height","trunk_diameter_bottom","trunk_diameter_middle","trunk_diameter_top",
        "trunk_bend","trunk_bend_start"
    ]
    for i in range(1,7):
        props += [
            f"branch{i}_height", f"branch{i}_count",
            f"branch{i}_rotate", f"branch{i}_angle",
            f"branch{i}_bend", f"branch{i}_penetration",
            f"branch{i}_length", f"branch{i}_diameter"
        ]
    for p in props: delattr(bpy.types.Scene, p)

if __name__=="__main__":
    register()

