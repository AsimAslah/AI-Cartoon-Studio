from __future__ import annotations

import argparse
import math
import sys
import traceback
from pathlib import Path

import bpy
from mathutils import Vector


def material(name, color, metallic=0.0, emission=None):
    mat = bpy.data.materials.new(name)
    mat.diffuse_color = (*color, 1)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    bsdf.inputs["Base Color"].default_value = (*color, 1)
    bsdf.inputs["Roughness"].default_value = 0.72
    bsdf.inputs["Metallic"].default_value = metallic
    if emission:
        bsdf.inputs["Emission Color"].default_value = (*emission, 1)
        bsdf.inputs["Emission Strength"].default_value = 5.0
    return mat


def add_uv(name, location, scale, mat, segments=16, rings=8, parent=None):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=segments, ring_count=rings, location=location)
    obj = bpy.context.object
    obj.name = name
    obj.scale = scale
    obj.data.materials.append(mat)
    obj.parent = parent
    bpy.ops.object.shade_smooth()
    return obj


def add_cone(name, location, radius1, radius2, depth, mat, rotation=(0, 0, 0), parent=None, vertices=12):
    bpy.ops.mesh.primitive_cone_add(vertices=vertices, radius1=radius1, radius2=radius2, depth=depth, location=location, rotation=rotation)
    obj = bpy.context.object
    obj.name = name
    obj.data.materials.append(mat)
    obj.parent = parent
    return obj


def make_fox(mats):
    root = bpy.data.objects.new("FOX_RIG_ROOT", None)
    bpy.context.collection.objects.link(root)
    body = add_uv("Fox_Body", (0, 0, 1.15), (0.72, 0.42, 0.58), mats["orange"], parent=root)
    chest = add_uv("Fox_White_Belly", (-0.15, -0.38, 1.17), (0.38, 0.09, 0.4), mats["white"], parent=root)
    head = add_uv("Fox_Head", (-0.72, 0, 1.72), (0.53, 0.47, 0.5), mats["orange"], parent=root)
    muzzle = add_uv("Fox_Muzzle", (-1.12, -0.02, 1.57), (0.34, 0.3, 0.25), mats["white"], parent=root)
    add_uv("Fox_Nose", (-1.38, -0.02, 1.61), (0.13, 0.12, 0.11), mats["black"], parent=root)
    for y in (-0.25, 0.25):
        add_uv(f"Fox_Eye_{y}", (-1.00, y, 1.88), (0.11, 0.07, 0.14), mats["white"], parent=root)
        add_uv(f"Fox_Pupil_{y}", (-1.08, y, 1.9), (0.055, 0.045, 0.075), mats["black"], parent=root)
        add_cone(f"Fox_Ear_{y}", (-0.62, y, 2.16), .24, 0, .55, mats["orange"], parent=root)
    legs = []
    for index, (x, y) in enumerate(((-.38, -.28), (-.38, .28), (.42, -.28), (.42, .28))):
        leg = add_uv(f"Fox_Leg_{index}", (x, y, .66), (.16, .16, .48), mats["orange"], parent=root)
        add_uv(f"Fox_Paw_{index}", (x - .08, y, .25), (.23, .19, .14), mats["black"], parent=leg)
        legs.append(leg)
    tail = add_uv("Fox_Bushy_Tail", (.85, .05, 1.25), (.78, .25, .28), mats["orange"], parent=root)
    tail.rotation_euler[1] = math.radians(-18)
    add_uv("Fox_Tail_Tip", (1.47, .05, 1.48), (.28, .22, .24), mats["white"], parent=root)
    backpack = add_uv("Fox_Blue_Backpack", (.22, .36, 1.45), (.42, .16, .44), mats["blue"], parent=root)

    for frame, x, z in ((1, -3.5, 0), (24, -1.7, .06), (48, 0.0, 0), (72, .65, 0)):
        root.location = (x, 0, z)
        root.keyframe_insert("location", frame=frame)
    for index, leg in enumerate(legs):
        for frame in range(1, 49, 6):
            leg.rotation_euler[1] = math.radians(22 if (frame // 6 + index) % 2 else -22)
            leg.keyframe_insert("rotation_euler", frame=frame)
        leg.rotation_euler[1] = 0
        leg.keyframe_insert("rotation_euler", frame=54)
    for frame, angle in ((1, -18), (18, 14), (36, -12), (54, 16), (72, -5)):
        tail.rotation_euler[2] = math.radians(angle)
        tail.keyframe_insert("rotation_euler", frame=frame)
    for frame, angle in ((1, 0), (48, 0), (60, -12), (72, 8)):
        head.rotation_euler[2] = math.radians(angle)
        head.keyframe_insert("rotation_euler", frame=frame)
    return root


def make_forest(mats):
    bpy.ops.mesh.primitive_plane_add(size=30, location=(1, 0, 0))
    ground = bpy.context.object
    ground.name = "Magical_Forest_Ground"
    ground.data.materials.append(mats["ground"])
    bpy.ops.mesh.primitive_cube_add(location=(0, 0, .025), scale=(8, .72, .03))
    path = bpy.context.object
    path.name = "Forest_Path"
    path.data.materials.append(mats["path"])
    tree_positions = [(-4,-2.7),(-2.2,2.4),(-.2,3.1),(2.3,2.6),(4.8,-3.1),(6,2.2)]
    for index, (x, y) in enumerate(tree_positions):
        bpy.ops.mesh.primitive_cylinder_add(vertices=10, radius=.35, depth=3.3, location=(x,y,1.65))
        trunk = bpy.context.object
        trunk.name = f"Tree_{index}_Trunk"
        trunk.data.materials.append(mats["bark"])
        for dz, radius in ((2.8,1.25),(3.55,.95),(4.15,.65)):
            add_cone(f"Tree_{index}_Canopy", (x,y,dz), radius, .1, 1.8, mats["leaves"], vertices=12)
    for index, (x, y, color) in enumerate(((-2,-1.2,"pink"),(-.7,1.1,"yellow"),(1.4,-1.3,"pink"),(3,1.1,"yellow"))):
        add_uv(f"Flower_{index}", (x,y,.18), (.12,.12,.12), mats[color], segments=10, rings=6)
    stone_location = (1.25, -1.05, .35)
    stone = add_uv("Glowing_Stone", stone_location, (.34,.3,.38), mats["glow"], segments=12, rings=6)
    for frame, scale in ((1,.8),(52,.8),(62,1.15),(72,.95)):
        stone.scale = Vector((.34,.3,.38)) * scale
        stone.keyframe_insert("scale", frame=frame)
    bpy.ops.object.light_add(type="POINT", location=(1.25,-1.05,1.2))
    glow = bpy.context.object
    glow.name = "Stone_Magic_Light"
    glow.data.color = (0.25, .45, 1)
    glow.data.energy = 0
    for frame, energy in ((1,0),(52,0),(62,900),(72,500)):
        glow.data.energy = energy
        glow.data.keyframe_insert("energy", frame=frame)


def setup_camera():
    bpy.ops.object.camera_add(location=(-8.8,-9.8,5.4))
    camera = bpy.context.object
    camera.name = "Story_Camera"
    bpy.context.scene.camera = camera
    camera.data.lens = 52
    for frame, location, target in ((1,(-8.8,-9.8,5.4),(-1.6,0,1.2)),(48,(-6.7,-8.2,4.6),(0,0,1.2)),(72,(-5.2,-7.3,4.0),(.8,0,1.15))):
        camera.location = location
        direction = Vector(target) - camera.location
        camera.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()
        camera.keyframe_insert("location", frame=frame)
        camera.keyframe_insert("rotation_euler", frame=frame)


def build(output_dir: Path, preview_only: bool):
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    mats = {
        "orange": material("Fox Orange", (1.0,.23,.035)), "white": material("Warm White", (.95,.88,.75)),
        "black": material("Soft Black", (.012,.018,.016)), "blue": material("Backpack Blue", (.03,.22,.68)),
        "ground": material("Forest Moss", (.035,.19,.075)), "path": material("Golden Path", (.38,.19,.07)),
        "bark": material("Tree Bark", (.18,.065,.025)), "leaves": material("Emerald Leaves", (.025,.34,.11)),
        "pink": material("Magic Pink", (1,.08,.38), emission=(1,.03,.18)), "yellow": material("Magic Yellow", (1,.66,.04), emission=(1,.38,.01)),
        "glow": material("Glowing Stone", (.15,.36,1), emission=(.08,.25,1)),
    }
    make_forest(mats)
    make_fox(mats)
    setup_camera()
    bpy.ops.object.light_add(type="AREA", location=(-3,-4,7))
    bpy.context.object.data.energy = 1100
    bpy.context.object.data.shape = "DISK"
    bpy.context.object.data.size = 6
    bpy.ops.object.light_add(type="SUN", location=(0,0,8))
    bpy.context.object.rotation_euler = (math.radians(25),math.radians(-20),math.radians(-25))
    bpy.context.object.data.energy = 1.2

    scene = bpy.context.scene
    scene.render.engine = "BLENDER_EEVEE"
    scene.render.resolution_x = 640
    scene.render.resolution_y = 360
    scene.render.resolution_percentage = 100
    scene.render.fps = 24
    scene.frame_start = 1
    scene.frame_end = 72
    if hasattr(scene.render.image_settings, "media_type"):
        scene.render.image_settings.media_type = "IMAGE"
    scene.render.image_settings.file_format = "PNG"
    scene.world.color = (.018,.04,.075)
    output_dir.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(output_dir / "forest_fox.blend"))
    scene.frame_set(62)
    scene.render.filepath = str(output_dir / "preview.png")
    bpy.ops.render.render(write_still=True)
    if not preview_only:
        if hasattr(scene.render.image_settings, "media_type"):
            scene.render.image_settings.media_type = "VIDEO"
        scene.render.image_settings.file_format = "FFMPEG"
        scene.render.ffmpeg.format = "MPEG4"
        scene.render.ffmpeg.codec = "H264"
        scene.render.ffmpeg.constant_rate_factor = "MEDIUM"
        scene.render.filepath = str(output_dir / "first_cartoon.mp4")
        bpy.ops.render.render(animation=True)
    print(f"OUTPUT_BLEND={output_dir / 'forest_fox.blend'}")
    print(f"OUTPUT_PNG={output_dir / 'preview.png'}")
    if not preview_only:
        print(f"OUTPUT_MP4={output_dir / 'first_cartoon.mp4'}")
    print("AI_CARTOON_RENDER_COMPLETE=1")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--preview-only", action="store_true")
    args = parser.parse_args(sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else [])
    build(Path(args.output_dir).resolve(), args.preview_only)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        traceback.print_exc()
        sys.stdout.flush()
        sys.stderr.flush()
        raise SystemExit(1)
