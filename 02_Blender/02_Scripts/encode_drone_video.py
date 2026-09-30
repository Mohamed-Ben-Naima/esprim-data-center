import bpy, os, time, glob
sc=bpy.context.scene
anim=r"C:\Users\ASUS\Documents\ESPRIM\Data Center\02_Blender\04_Renders\animation"; frames=os.path.join(anim,"frames"); log=os.path.join(anim,"_render_log.txt")
def w(s):
    with open(log,"a") as f: f.write(time.strftime("%H:%M:%S ")+s+"\n")
w("ENCODE START")
# encode with the sequencer
v=bpy.data.scenes.new("Encode")
v.render.resolution_x=1920; v.render.resolution_y=1080; v.render.resolution_percentage=100
v.render.fps=30; v.frame_start=1; v.frame_end=1020
se=v.sequence_editor_create()
files=sorted(glob.glob(os.path.join(frames,"f_*.png")))
strips=se.strips if hasattr(se,"strips") else se.sequences
s=strips.new_image("frames",files[0],1,1)
for f in files[1:]: s.elements.append(os.path.basename(f))
v.view_settings.view_transform="Standard"
ims=v.render.image_settings
try: ims.media_type="VIDEO"
except Exception: pass
ims.file_format="FFMPEG"
ff=v.render.ffmpeg; ff.format="MPEG4"; ff.codec="H264"; ff.constant_rate_factor="HIGH"; ff.ffmpeg_preset="GOOD"; ff.audio_codec="NONE"
v.render.filepath=os.path.join(anim,"DC_Drone_Flythrough.mp4")
v.render.use_file_extension=False
bpy.ops.render.render(animation=True, scene=v.name)
w("ALL DONE")
