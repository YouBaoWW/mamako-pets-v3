#!/usr/bin/env python3
"""Export lossless, untrimmed RGBA frames from animation-map.json.

Requires Python 3.8+ and Pillow. The map and source images are resolved beside
this script. No account, network access, or Agent-specific runtime is needed.
"""

import argparse
import hashlib
import io
import json
import math
import re
import sys
from pathlib import Path, PureWindowsPath


SLUG = re.compile(r"[a-z0-9][a-z0-9_-]*\Z")
SHA256 = re.compile(r"[0-9a-fA-F]{64}\Z")
WINDOWS_RESERVED = {"con", "prn", "aux", "nul"} | {
    prefix + str(number) for prefix in ("com", "lpt") for number in range(1, 10)
}


class ExportError(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise ExportError(message)


def positive_int(value, field):
    require(type(value) is int and value > 0, field + " must be a positive integer")
    return value


def nonnegative_int(value, field):
    require(type(value) is int and value >= 0, field + " must be a nonnegative integer")
    return value


def object_value(value, field):
    require(isinstance(value, dict), field + " must be an object")
    return value


def slug(value, field):
    require(isinstance(value, str) and SLUG.fullmatch(value),
            field + " must contain lowercase letters, digits, hyphens, or underscores")
    require(value not in WINDOWS_RESERVED, field + " is a reserved Windows filename")
    return value


def source_path(root, value):
    require(isinstance(value, str) and value, "spritesheet must be a relative path")
    require("\\" not in value and ":" not in value and "\x00" not in value,
            "spritesheet must use a relative POSIX path")
    relative = Path(value)
    require(not relative.is_absolute() and not PureWindowsPath(value).drive,
            "absolute spritesheet paths are not allowed")
    require(all(part not in ("", ".", "..") for part in value.split("/")),
            "spritesheet path traversal is not allowed")
    resolved = (root / relative).resolve(strict=True)
    try:
        resolved.relative_to(root)
    except ValueError:
        raise ExportError("spritesheet resolves outside the repository")
    require(resolved.is_file(), "spritesheet is not a file: " + value)
    return resolved


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, "duplicate JSON key: " + key)
        result[key] = value
    return result


def validate_map(data, root):
    object_value(data, "animation map")
    require(type(data.get("schema_version")) is int and data["schema_version"] == 1,
            "unsupported schema_version; expected 1")
    atlas = object_value(data.get("atlas"), "atlas")
    for field in ("width", "height", "cell_width", "cell_height", "columns", "rows"):
        positive_int(atlas.get(field), "atlas." + field)
    require(atlas["width"] == atlas["columns"] * atlas["cell_width"] and
            atlas["height"] == atlas["rows"] * atlas["cell_height"],
            "atlas dimensions must equal the complete cell grid")

    animations = object_value(data.get("animations"), "animations")
    require(animations, "animations must not be empty")
    occupied = set()
    for state, animation in animations.items():
        slug(state, "animation state")
        require(state != "look", "look is reserved for static direction frames")
        object_value(animation, "animation " + state)
        row = nonnegative_int(animation.get("row"), state + ".row")
        count = positive_int(animation.get("frame_count"), state + ".frame_count")
        require(row < atlas["rows"] and count <= atlas["columns"],
                state + " extends outside the atlas")
        durations = animation.get("durations_ms")
        require(isinstance(durations, list) and len(durations) == count,
                state + ".durations_ms must contain one duration per frame")
        for duration in durations:
            positive_int(duration, state + ".duration_ms")
        require(animation.get("playback") in ("loop", "once"),
                state + ".playback must be loop or once")
        require(isinstance(animation.get("label_zh"), str),
                state + ".label_zh must be a string")
        for column in range(count):
            require((row, column) not in occupied, "animation cells overlap")
            occupied.add((row, column))

    look = object_value(data.get("look"), "look")
    start = nonnegative_int(look.get("start_row"), "look.start_row")
    count = positive_int(look.get("count"), "look.count")
    step = look.get("angle_step_degrees")
    require(type(step) in (int, float) and math.isfinite(step) and step > 0,
            "look.angle_step_degrees must be positive and finite")
    require(math.isclose(count * step, 360, rel_tol=0, abs_tol=1e-8),
            "look directions must cover one complete 360-degree turn")
    require(type(look.get("clockwise")) is bool, "look.clockwise must be boolean")
    require(look.get("zero_direction") in ("up", "right", "down", "left"),
            "look.zero_direction must name a cardinal direction")
    for index in range(count):
        row, column = start + index // atlas["columns"], index % atlas["columns"]
        require(row < atlas["rows"], "look frames extend outside the atlas")
        require((row, column) not in occupied, "look and animation cells overlap")
        occupied.add((row, column))

    characters = data.get("characters")
    require(isinstance(characters, list) and characters, "characters must be a nonempty list")
    ids = set()
    for character in characters:
        object_value(character, "character")
        character_id = slug(character.get("id"), "character.id")
        require(character_id not in ids, "duplicate character ID: " + character_id)
        ids.add(character_id)
        require(isinstance(character.get("name"), str) and character["name"],
                "character.name must be a nonempty string")
        checksum = character.get("sha256")
        require(isinstance(checksum, str) and SHA256.fullmatch(checksum),
                character_id + ".sha256 must contain 64 hexadecimal digits")
        source_path(root, character.get("spritesheet"))
    return atlas, occupied


def prepare_sources(data, root, selected, atlas, occupied, image_module):
    prepared = []
    for character in data["characters"]:
        if selected and character["id"] not in selected:
            continue
        raw = source_path(root, character["spritesheet"]).read_bytes()
        actual_hash = hashlib.sha256(raw).hexdigest()
        require(actual_hash == character["sha256"].lower(),
                character["id"] + ": source SHA-256 does not match animation-map.json")
        with image_module.open(io.BytesIO(raw)) as source:
            require(source.format == "PNG", character["id"] + ": source must be PNG")
            require(source.size == (atlas["width"], atlas["height"]),
                    character["id"] + ": source dimensions do not match the map")
            require("A" in source.getbands() or "transparency" in source.info,
                    character["id"] + ": source has no alpha/transparency channel")
            rgba = source.convert("RGBA")
            rgba.load()
        alpha = rgba.getchannel("A")
        for row, column in occupied:
            x, y = column * atlas["cell_width"], row * atlas["cell_height"]
            cell_alpha = alpha.crop(
                (x, y, x + atlas["cell_width"], y + atlas["cell_height"]))
            require(cell_alpha.getbbox() is not None,
                    "{}: mapped cell ({}, {}) is fully transparent".format(
                        character["id"], row, column))
        prepared.append((character, actual_hash, rgba))
    return prepared


def write_frame(image, atlas, output, relative, row, column, index, duration):
    width, height = atlas["cell_width"], atlas["cell_height"]
    x, y = column * width, row * height
    frame = image.crop((x, y, x + width, y + height))
    frame.info.clear()
    encoded = io.BytesIO()
    # Save only cell pixels: no resizing, trimming, palette conversion, or metadata copying.
    frame.save(encoded, format="PNG")
    png = encoded.getvalue()
    destination = output / relative
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("xb") as stream:
        stream.write(png)
    return {
        "file": relative.as_posix(), "index": index,
        "atlas_rect": {"x": x, "y": y, "width": width, "height": height},
        "duration_ms": duration, "sha256": hashlib.sha256(png).hexdigest(),
        "pixel_sha256_rgba8": hashlib.sha256(frame.tobytes()).hexdigest(),
    }


def angle_name(angle):
    return ("{:03d}".format(int(angle)) if float(angle).is_integer()
            else ("{:07.3f}".format(angle).rstrip("0").rstrip(".")))


def export(data, prepared, output, atlas, map_hash):
    manifest = {
        "schema_version": 1, "format": "untrimmed-rgba-png-frames",
        "map_sha256": map_hash, "coordinate_origin": "top-left",
        "cell_size": {"width": atlas["cell_width"], "height": atlas["cell_height"]},
        "characters": [],
    }
    frame_total = 0
    for character, checksum, image in prepared:
        item = {
            "id": character["id"], "name": character["name"],
            "source": {"file": character["spritesheet"], "sha256": checksum},
            "animations": {},
        }
        for state, animation in data["animations"].items():
            frames = []
            for index, duration in enumerate(animation["durations_ms"]):
                relative = Path(character["id"]) / state / "{:02d}.png".format(index)
                frames.append(write_frame(image, atlas, output, relative,
                                          animation["row"], index, index, duration))
            item["animations"][state] = {
                "label_zh": animation["label_zh"], "playback": animation["playback"],
                "duration_ms": sum(animation["durations_ms"]), "frames": frames,
            }
            frame_total += len(frames)
        look = data["look"]
        directions = []
        for index in range(look["count"]):
            angle = index * look["angle_step_degrees"]
            relative = Path(character["id"]) / "look" / (angle_name(angle) + ".png")
            frame = write_frame(image, atlas, output, relative,
                                look["start_row"] + index // atlas["columns"],
                                index % atlas["columns"], index, None)
            frame["angle_degrees"] = angle
            directions.append(frame)
        item["look"] = {
            "kind": "static-direction-frames", "clockwise": look["clockwise"],
            "zero_direction": look["zero_direction"], "frames": directions,
        }
        frame_total += len(directions)
        manifest["characters"].append(item)
    with (output / "portable-manifest.json").open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(manifest, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write("\n")
    return frame_total


def main():
    root = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=root / "portable-frames",
                        help="new or empty output directory (default: beside this script)")
    parser.add_argument("--character", action="append", metavar="ID",
                        help="export only this character; repeat for more IDs (default: all)")
    args = parser.parse_args()
    try:
        try:
            from PIL import Image
        except ImportError:
            raise ExportError("Pillow is required. Install it with: python -m pip install Pillow")
        map_bytes = (root / "animation-map.json").read_bytes()
        data = json.loads(map_bytes.decode("utf-8-sig"), object_pairs_hook=unique_object)
        atlas, occupied = validate_map(data, root)
        selected = set(args.character or [])
        known = {character["id"] for character in data["characters"]}
        require(not selected - known,
                "unknown character ID(s): " + ", ".join(sorted(selected - known)) +
                "; available: " + ", ".join(sorted(known)))
        require(not args.output.is_symlink(), "output directory must not be a symbolic link")
        output = args.output.resolve()
        require(not output.exists() or (output.is_dir() and not any(output.iterdir())),
                "output directory must be new or empty; existing files will not be overwritten")
        prepared = prepare_sources(data, root, selected, atlas, occupied, Image)
        # Check again after validation, before the first write.
        require(not output.exists() or (output.is_dir() and not any(output.iterdir())),
                "output directory is no longer empty")
        output.mkdir(parents=True, exist_ok=True)
        total = export(data, prepared, output, atlas, hashlib.sha256(map_bytes).hexdigest())
        print("Exported {} RGBA PNG frames for {} character(s).".format(total, len(prepared)))
        print("Output: " + str(output))
        print("Frame paths, durations, source hashes, and pixel hashes: portable-manifest.json")
        return 0
    except (ExportError, OSError, UnicodeError, json.JSONDecodeError) as error:
        print("Export failed: " + str(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
