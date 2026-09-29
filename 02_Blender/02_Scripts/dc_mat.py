
import bpy, math
class NB:
    """tiny node builder"""
    def __init__(self, mat):
        mat.use_nodes=True
        self.nt=mat.node_tree; self.x=-1400
        for n in list(self.nt.nodes): self.nt.nodes.remove(n)
        self.out=self.n("ShaderNodeOutputMaterial"); self.out.location=(400,0)
        self.bsdf=self.n("ShaderNodeBsdfPrincipled"); self.bsdf.location=(0,0)
        self.L(self.bsdf.outputs[0], self.out.inputs["Surface"])
        co=self.n("ShaderNodeTexCoord"); self.obj=co.outputs["Object"]; self.gen=co.outputs["Generated"]; self.uv=co.outputs["UV"]
        self.oi=self.n("ShaderNodeObjectInfo")
    def n(self,t,**kw):
        nd=self.nt.nodes.new(t); nd.location=(self.x,len(self.nt.nodes)*-40); self.x+=30
        for k,v in kw.items(): setattr(nd,k,v)
        return nd
    def L(self,a,b): self.nt.links.new(a,b)
    def set(self,node,**kw):
        for k,v in kw.items():
            k=k.replace("_"," ")
            s=node.inputs[k]
            if isinstance(v,(tuple,list)) and len(v)==3: v=(*v,1)
            if hasattr(v,"bl_idname") or hasattr(v,"node"): self.L(v,s)
            else: s.default_value=v
    def P(self,**kw): self.set(self.bsdf,**kw)
    def noise(self,scale,detail=4,rough=0.55,vec=None,dim="3D"):
        t=self.n("ShaderNodeTexNoise"); t.noise_dimensions=dim
        t.inputs["Scale"].default_value=scale; t.inputs["Detail"].default_value=detail; t.inputs["Roughness"].default_value=rough
        self.L(vec or self.obj,t.inputs["Vector"]); return t
    def voronoi(self,scale,vec=None,feature="F1"):
        t=self.n("ShaderNodeTexVoronoi"); t.feature=feature; t.inputs["Scale"].default_value=scale
        self.L(vec or self.obj,t.inputs["Vector"]); return t
    def brick(self,scale,mortar=0.02,w=0.5,h=0.25,vec=None,offset=0.5):
        t=self.n("ShaderNodeTexBrick"); t.offset=offset
        t.inputs["Scale"].default_value=scale; t.inputs["Mortar Size"].default_value=mortar
        t.inputs["Brick Width"].default_value=w; t.inputs["Row Height"].default_value=h
        t.inputs["Mortar Smooth"].default_value=0.1
        t.inputs["Color1"].default_value=(1,1,1,1); t.inputs["Color2"].default_value=(0.85,0.85,0.85,1); t.inputs["Mortar"].default_value=(0,0,0,1)
        self.L(vec or self.obj,t.inputs["Vector"]); return t
    def ramp(self,inp,stops):
        r=self.n("ShaderNodeValToRGB"); e=r.color_ramp.elements
        while len(e)>len(stops): e.remove(e[-1])
        while len(e)<len(stops): e.new(0.5)
        for el,(pos,col) in zip(e,stops):
            el.position=pos; el.color=(*col,1) if len(col)==3 else col
        self.L(inp,r.inputs["Fac"]); return r
    def mix(self,fac,a,b,blend="MIX"):
        m=self.n("ShaderNodeMix"); m.data_type="RGBA"; m.blend_type=blend
        for sock,v in ((m.inputs[0],fac),(m.inputs[6],a),(m.inputs[7],b)):
            if isinstance(v,(int,float)): sock.default_value=v
            elif isinstance(v,tuple): sock.default_value=(*v,1) if len(v)==3 else v
            else: self.L(v,sock)
        return m.outputs[2]
    def math(self,op,a,b=0.0):
        m=self.n("ShaderNodeMath"); m.operation=op
        for s,v in ((m.inputs[0],a),(m.inputs[1],b)):
            if isinstance(v,(int,float)): s.default_value=v
            else: self.L(v,s)
        return m.outputs[0]
    def bump(self,h,strength=0.3,dist=0.05,normal=None):
        b=self.n("ShaderNodeBump"); b.inputs["Strength"].default_value=strength; b.inputs["Distance"].default_value=dist
        self.L(h,b.inputs["Height"])
        if normal: self.L(normal,b.inputs["Normal"])
        return b.outputs["Normal"]
    def mapping(self,scale=(1,1,1),vec=None):
        m=self.n("ShaderNodeMapping"); m.inputs["Scale"].default_value=scale; self.L(vec or self.obj,m.inputs["Vector"]); return m.outputs[0]
def M(name):
    return bpy.data.materials.get(name) or bpy.data.materials.new(name)
