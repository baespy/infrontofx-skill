"""prop-forge: render smooth animated turntable / action previews (PNG frames -> GIF & MP4) for rigged prop sets.

Usage (Blender 4.2+, no add-ons needed):
  blender -b --factory-startup -P render_anim_preview.py -- --build <build dir> --out <preview dir>
                                                            [--ffmpeg <path>] [--samples 8] [--only lineup,safe,marker,loot]

Loads each prop mesh + optional `<id>_rig` armature + Action from `<build dir>/*.blend`, configures cyclic looping,
renders Eevee frame sequences, and encodes looping GIFs + a combined H.264 MP4 showcase if ffmpeg is provided.
"""

import argparse
import json
import math
import os
import shutil
import subprocess
import sys

import bmesh
import bpy
from mathutils import Vector


def clean_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)


def bbox_world(objs):
    depsgraph = bpy.context.evaluated_depsgraph_get()
    pts = []
    for ob in objs:
        if ob.type != "MESH":
            continue
        ev = ob.evaluated_get(depsgraph)
        me = ev.to_mesh()
        for v in me.vertices:
            pts.append(ob.matrix_world @ v.co)
        ev.to_mesh_clear()
    lo = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
    hi = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
    return lo, hi


def setup_studio(scene, samples, res):
    scene.render.engine = "BLENDER_EEVEE_NEXT"
    try:
        scene.eevee.taa_render_samples = samples
        scene.eevee.use_shadows = True
    except Exception:
        pass
    scene.render.resolution_x, scene.render.resolution_y = res
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.film_transparent = False
    scene.view_settings.view_transform = "Standard"
    try:
        scene.view_settings.look = "Medium High Contrast"
    except Exception:
        pass

    world = bpy.data.worlds.new("anim_world")
    world.use_nodes = True
    bg = world.node_tree.nodes.get("Background")
    bg.inputs["Color"].default_value = (0.14, 0.16, 0.22, 1.0)
    bg.inputs["Strength"].default_value = 0.85
    scene.world = world

    # Key sun
    sun_d = bpy.data.lights.new("key_sun", "SUN")
    sun_d.energy = 3.6
    sun_d.angle = math.radians(5)
    sun = bpy.data.objects.new("key_sun", sun_d)
    sun.rotation_euler = (math.radians(46), math.radians(10), math.radians(-32))
    scene.collection.objects.link(sun)

    # Cool rim / fill area
    fill_d = bpy.data.lights.new("fill_area", "AREA")
    fill_d.energy = 520
    fill_d.size = 7.0
    fill = bpy.data.objects.new("fill_area", fill_d)
    fill.location = (-4.5, -6.5, 4.2)
    fill.rotation_euler = Vector((-4.5, -6.5, 4.2)).to_track_quat("Z", "Y").to_euler()
    scene.collection.objects.link(fill)

    # Warm front-right fill to illuminate interior of opened vault safe
    rim_d = bpy.data.lights.new("front_fill", "AREA")
    rim_d.energy = 260
    rim_d.size = 4.0
    rim = bpy.data.objects.new("front_fill", rim_d)
    rim.location = (3.5, -5.0, 2.5)
    rim.rotation_euler = Vector((3.5, -5.0, 2.5)).to_track_quat("Z", "Y").to_euler()
    scene.collection.objects.link(rim)

    # Sleek studio floor
    gme = bpy.data.meshes.new("studio_floor")
    bm = bmesh.new()
    bmesh.ops.create_grid(bm, x_segments=1, y_segments=1, size=50)
    bm.to_mesh(gme)
    bm.free()
    ground = bpy.data.objects.new("studio_floor", gme)
    gmat = bpy.data.materials.new("studio_floor_mat")
    gmat.use_nodes = True
    gb = gmat.node_tree.nodes.get("Principled BSDF")
    gb.inputs["Base Color"].default_value = (0.12, 0.12, 0.14, 1.0)
    gb.inputs["Roughness"].default_value = 0.65
    gme.materials.append(gmat)
    scene.collection.objects.link(ground)
    return [sun, fill, rim, ground]


def append_prop(blend_path, prop_id, loc=(0.0, 0.0, 0.0)):
    rig_name = prop_id + "_rig"
    with bpy.data.libraries.load(blend_path, link=False) as (src, dst):
        want = [prop_id]
        if rig_name in src.objects:
            want.append(rig_name)
        dst.objects = want

    mesh_ob = None
    rig_ob = None
    for ob in dst.objects:
        if ob is None:
            continue
        bpy.context.scene.collection.objects.link(ob)
        if ob.type == "ARMATURE":
            rig_ob = ob
        elif ob.type == "MESH":
            mesh_ob = ob

    holder = bpy.data.objects.new(prop_id + "_root", None)
    bpy.context.scene.collection.objects.link(holder)
    holder.location = Vector(loc)
    if mesh_ob is not None:
        mesh_ob.parent = holder
    if rig_ob is not None:
        rig_ob.parent = holder
        if rig_ob.animation_data and rig_ob.animation_data.action:
            act = rig_ob.animation_data.action
            for fc in act.fcurves:
                if not any(m.type == "CYCLES" for m in fc.modifiers):
                    fc.modifiers.new(type="CYCLES")
    return holder, mesh_ob, rig_ob


def place_camera(scene, center, radius, res, direction, fit=0.95, lens=50.0):
    cam_d = bpy.data.cameras.new("anim_cam")
    cam_d.lens = lens
    cam = bpy.data.objects.new("anim_cam", cam_d)
    scene.collection.objects.link(cam)
    aspect = res[0] / res[1]
    fov = 2.0 * math.atan(cam_d.sensor_width / 2.0 / cam_d.lens)
    if aspect < 1.0:
        fov *= aspect
    dist = radius / math.sin(fov / 2.0) * (fit if aspect >= 1.0 else 1.0)
    d = Vector(direction).normalized()
    cam.location = center + d * dist
    cam.rotation_euler = (-d).to_track_quat("-Z", "Y").to_euler()
    cam_d.clip_end = max(100.0, dist * 5.0)
    scene.camera = cam
    return cam, dist


def encode_media(ffmpeg, frame_dir, out_gif, out_mp4, fps_gif, fps_mp4, gif_width):
    pattern = os.path.join(frame_dir, "f_%04d.png")
    if out_mp4:
        cmd = [
            ffmpeg, "-y", "-framerate", str(fps_mp4), "-i", pattern,
            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "20", "-preset", "fast",
            "-vf", "pad=ceil(iw/2)*2:ceil(ih/2)*2",
            out_mp4,
        ]
        subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if out_gif:
        pal = os.path.join(frame_dir, "palette.png")
        vf_pal = "fps={},scale={}:-1:flags=lanczos,palettegen=stats_mode=diff".format(fps_gif, gif_width)
        subprocess.run([ffmpeg, "-y", "-framerate", str(fps_mp4), "-i", pattern, "-vf", vf_pal, pal],
                       check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        vf_gif = "fps={},scale={}:-1:flags=lanczos[x];[x][1:v]paletteuse=dither=bayer:bayer_scale=3".format(fps_gif, gif_width)
        subprocess.run([ffmpeg, "-y", "-framerate", str(fps_mp4), "-i", pattern, "-i", pal, "-lavfi", vf_gif, "-loop", "0", out_gif],
                       check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)


def render_sequence(scene, frame_indices, frame_dir, cam=None, orbit_center=None, orbit_dist=None, orbit_dir=None, orbit_span_deg=0.0):
    os.makedirs(frame_dir, exist_ok=True)
    base_d = Vector(orbit_dir).normalized() if orbit_dir else None
    n = len(frame_indices)
    for out_i, src_frame in enumerate(frame_indices):
        scene.frame_set(src_frame)
        bpy.context.view_layer.update()
        if cam is not None and orbit_span_deg != 0.0 and base_d is not None:
            u = out_i / max(1, n)
            az = math.radians(orbit_span_deg) * math.sin(u * math.tau)
            ca, sa = math.cos(az), math.sin(az)
            d = Vector((base_d.x * ca - base_d.y * sa, base_d.x * sa + base_d.y * ca, base_d.z)).normalized()
            cam.location = orbit_center + d * orbit_dist
            cam.rotation_euler = (-d).to_track_quat("-Z", "Y").to_euler()
        scene.render.filepath = os.path.join(frame_dir, "f_{:04d}.png".format(out_i + 1))
        bpy.ops.render.render(write_still=True)


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    ap = argparse.ArgumentParser()
    ap.add_argument("--build", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--ffmpeg", default="")
    ap.add_argument("--samples", type=int, default=8)
    ap.add_argument("--only", default="garage,pound,parking,airdrop,powerbox,safe,marker,loot,lineup")
    ap.add_argument("--keep-frames", action="store_true")
    args = ap.parse_args(argv)

    build_dir = os.path.abspath(args.build)
    out_dir = os.path.abspath(args.out)
    os.makedirs(out_dir, exist_ok=True)
    only = {s.strip() for s in args.only.split(",") if s.strip()}

    with open(os.path.join(build_dir, "report.json"), "r", encoding="utf-8") as fh:
        report = json.load(fh)
    by_arch = {}
    for m in report:
        by_arch.setdefault(m["archetype"], []).append(m)

    ffmpeg = args.ffmpeg or shutil.which("ffmpeg") or ""
    mp4_clips = []

    # 0a. Garage Hero Animation
    if "garage" in only:
        matches = [m for m in report if m["id"].endswith("_garage")]
        if matches:
            meta = matches[0]
            clean_scene()
            scene = bpy.context.scene
            setup_studio(scene, args.samples, (800, 600))
            _, mesh_ob, _ = append_prop(os.path.join(build_dir, meta["blend"]), meta["id"])
            scene.frame_set(1)
            lo, hi = bbox_world([mesh_ob])
            center = (lo + hi) / 2.0
            center.z += 0.05
            radius = (hi - lo).length / 2.0 * 1.06
            cam, dist = place_camera(scene, center, radius, (800, 600), direction=(0.46, -1.0, 0.22), fit=1.00)

            fdir = os.path.join(out_dir, "_frames_garage")
            n_frames = int(meta.get("anim", {}).get("frames", 121))
            frames = list(range(1, n_frames, 2))
            render_sequence(scene, frames, fdir, cam=cam, orbit_center=center, orbit_dist=dist, orbit_dir=(0.46, -1.0, 0.22), orbit_span_deg=7.0)
            if ffmpeg:
                gif_p = os.path.join(out_dir, "anim_garage.gif")
                mp4_p = os.path.join(out_dir, "anim_garage.mp4")
                encode_media(ffmpeg, fdir, gif_p, mp4_p, fps_gif=15, fps_mp4=15, gif_width=560)
                mp4_clips.append(mp4_p)
            if not args.keep_frames:
                shutil.rmtree(fdir, ignore_errors=True)
            print("ANIM_PREVIEW garage OK", flush=True)

    # 0b. Pound Hero Animation
    if "pound" in only:
        matches = [m for m in report if m["id"].endswith("_pound")]
        if matches:
            meta = matches[0]
            clean_scene()
            scene = bpy.context.scene
            setup_studio(scene, args.samples, (800, 600))
            _, mesh_ob, _ = append_prop(os.path.join(build_dir, meta["blend"]), meta["id"])
            scene.frame_set(1)
            lo, hi = bbox_world([mesh_ob])
            center = (lo + hi) / 2.0
            center.z += 0.05
            radius = (hi - lo).length / 2.0 * 1.06
            cam, dist = place_camera(scene, center, radius, (800, 600), direction=(0.42, -1.0, 0.22), fit=1.00)

            fdir = os.path.join(out_dir, "_frames_pound")
            n_frames = int(meta.get("anim", {}).get("frames", 121))
            frames = list(range(1, n_frames, 2))
            render_sequence(scene, frames, fdir, cam=cam, orbit_center=center, orbit_dist=dist, orbit_dir=(0.42, -1.0, 0.22), orbit_span_deg=7.0)
            if ffmpeg:
                gif_p = os.path.join(out_dir, "anim_pound.gif")
                mp4_p = os.path.join(out_dir, "anim_pound.mp4")
                encode_media(ffmpeg, fdir, gif_p, mp4_p, fps_gif=15, fps_mp4=15, gif_width=560)
                mp4_clips.append(mp4_p)
            if not args.keep_frames:
                shutil.rmtree(fdir, ignore_errors=True)
            print("ANIM_PREVIEW pound OK", flush=True)

    # 0c. Parking Hero Animation
    if "parking" in only:
        matches = [m for m in report if m["id"].endswith("_parking")]
        if matches:
            meta = matches[0]
            clean_scene()
            scene = bpy.context.scene
            setup_studio(scene, args.samples, (800, 600))
            _, mesh_ob, _ = append_prop(os.path.join(build_dir, meta["blend"]), meta["id"])
            scene.frame_set(1)
            lo, hi = bbox_world([mesh_ob])
            center = (lo + hi) / 2.0
            center.z += 0.06
            radius = (hi - lo).length / 2.0 * 1.06
            cam, dist = place_camera(scene, center, radius, (800, 600), direction=(0.36, -1.0, 0.22), fit=1.00)

            fdir = os.path.join(out_dir, "_frames_parking")
            n_frames = int(meta.get("anim", {}).get("frames", 121))
            frames = list(range(1, n_frames, 2))
            render_sequence(scene, frames, fdir, cam=cam, orbit_center=center, orbit_dist=dist, orbit_dir=(0.36, -1.0, 0.22), orbit_span_deg=6.0)
            if ffmpeg:
                gif_p = os.path.join(out_dir, "anim_parking.gif")
                mp4_p = os.path.join(out_dir, "anim_parking.mp4")
                encode_media(ffmpeg, fdir, gif_p, mp4_p, fps_gif=15, fps_mp4=15, gif_width=560)
                mp4_clips.append(mp4_p)
            if not args.keep_frames:
                shutil.rmtree(fdir, ignore_errors=True)
            print("ANIM_PREVIEW parking OK", flush=True)

    # 1. Safe Hero Animation (unlock wheel -> swing door open revealing gold/cash -> close -> lock)
    if "safe" in only and "safe" in by_arch:
        meta = by_arch["safe"][0]
        clean_scene()
        scene = bpy.context.scene
        setup_studio(scene, args.samples, (800, 600))
        _, mesh_ob, _ = append_prop(os.path.join(build_dir, meta["blend"]), meta["id"])
        scene.frame_set(1)
        lo, hi = bbox_world([mesh_ob])
        center = (lo + hi) / 2.0
        center.z += 0.05
        radius = (hi - lo).length / 2.0 * 1.15
        cam, dist = place_camera(scene, center, radius, (800, 600), direction=(0.48, -1.0, 0.28), fit=1.02)

        # Still open-vault render at frame 95
        scene.frame_set(95)
        bpy.context.view_layer.update()
        open_still = os.path.join(out_dir, meta["id"] + "_open_preview.png")
        scene.render.filepath = open_still
        bpy.ops.render.render(write_still=True)

        fdir = os.path.join(out_dir, "_frames_safe")
        frames = list(range(1, 181, 2))  # 90 frames @ 15fps = 6.0s smooth loop
        render_sequence(scene, frames, fdir, cam=cam, orbit_center=center, orbit_dist=dist, orbit_dir=(0.48, -1.0, 0.28), orbit_span_deg=8.0)
        if ffmpeg:
            gif_p = os.path.join(out_dir, "anim_safe.gif")
            mp4_p = os.path.join(out_dir, "anim_safe.mp4")
            encode_media(ffmpeg, fdir, gif_p, mp4_p, fps_gif=15, fps_mp4=15, gif_width=560)
            mp4_clips.append(mp4_p)
        if not args.keep_frames:
            shutil.rmtree(fdir, ignore_errors=True)
        print("ANIM_PREVIEW safe OK", flush=True)

    # 2. Floating Marker + Stash Crate Hero Animation
    if "marker" in only and "mascot_marker" in by_arch:
        marker_meta = by_arch["mascot_marker"][0]
        crate_meta = by_arch["crate"][0] if "crate" in by_arch else None
        clean_scene()
        scene = bpy.context.scene
        setup_studio(scene, args.samples, (800, 600))
        objs = []
        z_marker = 0.0
        if crate_meta:
            _, cm, _ = append_prop(os.path.join(build_dir, crate_meta["blend"]), crate_meta["id"], loc=(0, 0, 0))
            objs.append(cm)
            z_marker = crate_meta["size_m"][2] + 0.14
        _, mm, _ = append_prop(os.path.join(build_dir, marker_meta["blend"]), marker_meta["id"], loc=(0, 0, z_marker))
        objs.append(mm)
        scene.frame_set(1)
        lo, hi = bbox_world(objs)
        center = (lo + hi) / 2.0
        radius = (hi - lo).length / 2.0 * 1.05
        cam, dist = place_camera(scene, center, radius, (800, 600), direction=(0.35, -1.0, 0.25), fit=0.98)

        fdir = os.path.join(out_dir, "_frames_marker")
        frames = list(range(1, 121, 2))  # 60 frames @ 15fps = 4.0s smooth loop
        render_sequence(scene, frames, fdir, cam=cam, orbit_center=center, orbit_dist=dist, orbit_dir=(0.35, -1.0, 0.25), orbit_span_deg=6.0)
        if ffmpeg:
            gif_p = os.path.join(out_dir, "anim_marker.gif")
            mp4_p = os.path.join(out_dir, "anim_marker.mp4")
            encode_media(ffmpeg, fdir, gif_p, mp4_p, fps_gif=15, fps_mp4=15, gif_width=560)
            mp4_clips.append(mp4_p)
        if not args.keep_frames:
            shutil.rmtree(fdir, ignore_errors=True)
        print("ANIM_PREVIEW marker OK", flush=True)

    # 3. Loot Chest Hero Animation (hinged lid bounce + floating spinning coins)
    if "loot" in only and "chest" in by_arch:
        meta = by_arch["chest"][0]
        clean_scene()
        scene = bpy.context.scene
        setup_studio(scene, args.samples, (800, 600))
        _, mesh_ob, _ = append_prop(os.path.join(build_dir, meta["blend"]), meta["id"])
        scene.frame_set(1)
        lo, hi = bbox_world([mesh_ob])
        center = (lo + hi) / 2.0
        center.z += 0.08
        radius = (hi - lo).length / 2.0 * 1.15
        cam, dist = place_camera(scene, center, radius, (800, 600), direction=(0.45, -1.0, 0.42), fit=1.02)

        fdir = os.path.join(out_dir, "_frames_loot")
        frames = list(range(1, 121, 2))  # 60 frames @ 15fps = 4.0s smooth loop
        render_sequence(scene, frames, fdir, cam=cam, orbit_center=center, orbit_dist=dist, orbit_dir=(0.45, -1.0, 0.42), orbit_span_deg=7.0)
        if ffmpeg:
            gif_p = os.path.join(out_dir, "anim_loot.gif")
            mp4_p = os.path.join(out_dir, "anim_loot.mp4")
            encode_media(ffmpeg, fdir, gif_p, mp4_p, fps_gif=15, fps_mp4=15, gif_width=560)
            mp4_clips.append(mp4_p)
        if not args.keep_frames:
            shutil.rmtree(fdir, ignore_errors=True)
        print("ANIM_PREVIEW loot OK", flush=True)

    # 3b. Airdrop Hero Animation (spinning mascot core + counter-rotating gyro rings + crown + orbiting mini cans)
    if "airdrop" in only and "airdrop" in by_arch:
        meta = by_arch["airdrop"][0]
        clean_scene()
        scene = bpy.context.scene
        setup_studio(scene, args.samples, (800, 600))
        _, mesh_ob, _ = append_prop(os.path.join(build_dir, meta["blend"]), meta["id"])
        scene.frame_set(1)
        lo, hi = bbox_world([mesh_ob])
        center = (lo + hi) / 2.0
        center.z += 0.04
        radius = (hi - lo).length / 2.0 * 1.06
        cam, dist = place_camera(scene, center, radius, (800, 600), direction=(0.56, -1.0, 0.36), fit=1.00)

        fdir = os.path.join(out_dir, "_frames_airdrop")
        frames = list(range(1, 181, 2))  # 90 frames @ 15fps = 6.0s smooth loop
        render_sequence(scene, frames, fdir, cam=cam, orbit_center=center, orbit_dist=dist, orbit_dir=(0.56, -1.0, 0.36), orbit_span_deg=8.0)
        if ffmpeg:
            gif_p = os.path.join(out_dir, "anim_airdrop.gif")
            mp4_p = os.path.join(out_dir, "anim_airdrop.mp4")
            encode_media(ffmpeg, fdir, gif_p, mp4_p, fps_gif=15, fps_mp4=15, gif_width=560)
            mp4_clips.append(mp4_p)
        if not args.keep_frames:
            shutil.rmtree(fdir, ignore_errors=True)
        print("ANIM_PREVIEW airdrop OK", flush=True)

    # 3c. Power Box (ตู้ไฟ) Hero Animation (flipping twin breakers + counter-spinning roof sirens + crown + orbiting cans & lightning)
    if "powerbox" in only and "powerbox" in by_arch:
        meta = by_arch["powerbox"][0]
        clean_scene()
        scene = bpy.context.scene
        setup_studio(scene, args.samples, (800, 600))
        _, mesh_ob, _ = append_prop(os.path.join(build_dir, meta["blend"]), meta["id"])
        scene.frame_set(1)
        lo, hi = bbox_world([mesh_ob])
        center = (lo + hi) / 2.0
        center.z += 0.04
        radius = (hi - lo).length / 2.0 * 1.06
        cam, dist = place_camera(scene, center, radius, (800, 600), direction=(0.48, -1.0, 0.28), fit=1.00)

        fdir = os.path.join(out_dir, "_frames_powerbox")
        frames = list(range(1, 121, 2))  # 60 frames @ 15fps = 4.0s smooth loop
        render_sequence(scene, frames, fdir, cam=cam, orbit_center=center, orbit_dist=dist, orbit_dir=(0.48, -1.0, 0.28), orbit_span_deg=7.0)
        if ffmpeg:
            gif_p = os.path.join(out_dir, "anim_powerbox.gif")
            mp4_p = os.path.join(out_dir, "anim_powerbox.mp4")
            encode_media(ffmpeg, fdir, gif_p, mp4_p, fps_gif=15, fps_mp4=15, gif_width=560)
            mp4_clips.append(mp4_p)
        if not args.keep_frames:
            shutil.rmtree(fdir, ignore_errors=True)
        print("ANIM_PREVIEW powerbox OK", flush=True)

    # 4. Full Animated Lineup (all props animating simultaneously!)
    if "lineup" in only:
        clean_scene()
        scene = bpy.context.scene
        setup_studio(scene, args.samples, (1280, 560))
        meshes = []
        # Arrange in a clean semi-curved showcase row, with marker floating above stash
        x = 0.0
        stash_x = 0.0
        stash_h = 1.02
        non_markers = [m for m in report if m["archetype"] != "mascot_marker"]
        markers = [m for m in report if m["archetype"] == "mascot_marker"]
        placements = []
        for m in non_markers:
            w = m["size_m"][0]
            px = x + w / 2.0
            placements.append((m, px, 0.0))
            if m["archetype"] == "crate":
                stash_x = px
                stash_h = m["size_m"][2]
            x += w + 0.55
        shift_x = -x / 2.0
        for m, px, pz in placements:
            _, mo, _ = append_prop(os.path.join(build_dir, m["blend"]), m["id"], loc=(px + shift_x, 0.0, pz))
            meshes.append(mo)
        for m in markers:
            _, mo, _ = append_prop(os.path.join(build_dir, m["blend"]), m["id"], loc=(stash_x + shift_x, 0.0, stash_h + 0.16))
            meshes.append(mo)
        scene.frame_set(1)
        lo, hi = bbox_world(meshes)
        center = (lo + hi) / 2.0
        radius = (hi - lo).length / 2.0
        cam, dist = place_camera(scene, center, radius, (1280, 560), direction=(0.08, -1.0, 0.24), fit=1.08, lens=38.0)

        fdir = os.path.join(out_dir, "_frames_lineup")
        frames = list(range(1, 181, 2))  # 90 frames @ 15fps = 6.0s smooth showcase
        render_sequence(scene, frames, fdir, cam=cam, orbit_center=center, orbit_dist=dist, orbit_dir=(0.08, -1.0, 0.24), orbit_span_deg=4.5)
        if ffmpeg:
            gif_p = os.path.join(out_dir, "anim_lineup.gif")
            mp4_p = os.path.join(out_dir, "anim_lineup.mp4")
            encode_media(ffmpeg, fdir, gif_p, mp4_p, fps_gif=15, fps_mp4=15, gif_width=860)
            mp4_clips.insert(0, mp4_p)
        if not args.keep_frames:
            shutil.rmtree(fdir, ignore_errors=True)
        print("ANIM_PREVIEW lineup OK", flush=True)

    # Combine all available hero clips into one unified showcase MP4 (scaled cleanly to 1280x720)
    ordered_mp4s = []
    for cname in ("anim_lineup.mp4", "anim_garage.mp4", "anim_pound.mp4", "anim_parking.mp4", "anim_airdrop.mp4", "anim_powerbox.mp4", "anim_safe.mp4", "anim_marker.mp4", "anim_loot.mp4"):
        cp = os.path.join(out_dir, cname)
        if os.path.isfile(cp):
            ordered_mp4s.append(cp)
    if ffmpeg and len(ordered_mp4s) >= 2:
        norm_clips = []
        for idx, cp in enumerate(ordered_mp4s):
            nc = os.path.join(out_dir, "_norm_{}.mp4".format(idx))
            subprocess.run([
                ffmpeg, "-y", "-i", cp,
                "-vf", "scale=1280:720:force_original_aspect_ratio=decrease,pad=1280:720:(ow-iw)/2:(oh-ih)/2:color=#202430,fps=30",
                "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "19", "-preset", "fast",
                nc,
            ], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            norm_clips.append(nc)
        lst = os.path.join(out_dir, "_concat.txt")
        with open(lst, "w", encoding="utf-8") as fh:
            for nc in norm_clips:
                fh.write("file '{}'\n".format(nc.replace("\\", "/")))
        showcase_mp4 = os.path.join(out_dir, "animations_showcase.mp4")
        subprocess.run([ffmpeg, "-y", "-f", "concat", "-safe", "0", "-i", lst, "-c", "copy", showcase_mp4],
                       check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        for nc in norm_clips:
            os.remove(nc)
        os.remove(lst)
        print("SHOWCASE_MP4 " + showcase_mp4, flush=True)

    print("DONE", flush=True)


if __name__ == "__main__":
    main()
