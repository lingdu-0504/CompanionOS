#!/usr/bin/env python3
"""生成 CompanionOS 默认 VRM 模型文件

使用 numpy + struct 手动构建 glTF 2.0 二进制 (.glb) 文件，
嵌入 VRM 1.0 扩展元数据。

输出: frontend/public/vrm-model.vrm
"""

import struct
import json
import os
import sys
import math

import numpy as np


SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SCRIPT_DIR)
OUTPUT_DIR = os.path.join(PROJECT_DIR, "frontend", "public")
OUTPUT_PATH = os.path.join(OUTPUT_DIR, "vrm-model.vrm")


def generate_sphere(lat_segments: int, lon_segments: int, radius: float = 1.0):
    """生成球体网格顶点和索引"""
    verts = []
    norms = []
    uvs = []
    indices = []

    for lat in range(lat_segments + 1):
        theta = lat * math.pi / lat_segments
        sin_theta = math.sin(theta)
        cos_theta = math.cos(theta)

        for lon in range(lon_segments + 1):
            phi = lon * 2 * math.pi / lon_segments
            sin_phi = math.sin(phi)
            cos_phi = math.cos(phi)

            x = sin_theta * cos_phi
            y = cos_theta
            z = sin_theta * sin_phi

            verts.extend([x * radius, y * radius, z * radius])
            norms.extend([x, y, z])
            uvs.extend([lon / lon_segments, 1.0 - lat / lat_segments])

    for lat in range(lat_segments):
        for lon in range(lon_segments):
            first = lat * (lon_segments + 1) + lon
            second = first + lon_segments + 1

            indices.extend([first, second, first + 1])
            indices.extend([second, second + 1, first + 1])

    return (
        np.array(verts, dtype=np.float32),
        np.array(norms, dtype=np.float32),
        np.array(uvs, dtype=np.float32),
        np.array(indices, dtype=np.uint16),
    )


def generate_cylinder(segments: int, radius: float = 1.0, height: float = 1.0):
    """生成圆柱体网格顶点和索引"""
    verts = []
    norms = []
    uvs = []
    indices = []

    half_h = height / 2

    for i in range(segments + 1):
        theta = i * 2 * math.pi / segments
        cos_t = math.cos(theta)
        sin_t = math.sin(theta)

        verts.extend([cos_t * radius, -half_h, sin_t * radius])
        verts.extend([cos_t * radius, half_h, sin_t * radius])

        norms.extend([cos_t, 0, sin_t])
        norms.extend([cos_t, 0, sin_t])

        uvs.extend([i / segments, 0.0])
        uvs.extend([i / segments, 1.0])

    for i in range(segments):
        a = i * 2
        b = i * 2 + 1
        c = (i + 1) * 2
        d = (i + 1) * 2 + 1

        indices.extend([a, c, b])
        indices.extend([b, c, d])

    return (
        np.array(verts, dtype=np.float32),
        np.array(norms, dtype=np.float32),
        np.array(uvs, dtype=np.float32),
        np.array(indices, dtype=np.uint16),
    )


def generate_eye_sphere(segments: int = 8, radius: float = 1.0):
    """生成小眼球（半球体）"""
    verts = []
    norms = []
    uvs = []
    indices = []

    for lat in range(segments // 2 + 1):
        theta = lat * math.pi / (segments // 2)
        sin_theta = math.sin(theta)
        cos_theta = math.cos(theta)

        for lon in range(segments + 1):
            phi = lon * 2 * math.pi / segments
            sin_phi = math.sin(phi)
            cos_phi = math.cos(phi)

            x = sin_theta * cos_phi
            y = cos_theta
            z = sin_theta * sin_phi

            verts.extend([x * radius, y * radius, z * radius])
            norms.extend([x, y, z])
            uvs.extend([lon / segments, 1.0 - lat / (segments // 2)])

    for lat in range(segments // 2):
        for lon in range(segments):
            first = lat * (segments + 1) + lon
            second = first + segments + 1

            indices.extend([first, second, first + 1])
            indices.extend([second, second + 1, first + 1])

    return (
        np.array(verts, dtype=np.float32),
        np.array(norms, dtype=np.float32),
        np.array(uvs, dtype=np.float32),
        np.array(indices, dtype=np.uint16),
    )


def generate_mouth(segments: int = 12, radius: float = 1.0, tube_radius: float = 0.2):
    """生成嘴巴（半环圆环）"""
    verts = []
    norms = []
    uvs = []
    indices = []

    tube_segments = 6

    for i in range(tube_segments + 1):
        u = i * 2 * math.pi / tube_segments
        cos_u = math.cos(u)
        sin_u = math.sin(u)

        for j in range(segments + 1):
            v = j * math.pi / segments
            cos_v = math.cos(v)
            sin_v = math.sin(v)

            cx = (radius + tube_radius * cos_u) * sin_v
            cy = tube_radius * sin_u
            cz = (radius + tube_radius * cos_u) * cos_v

            nx = cos_u * sin_v
            ny = sin_u
            nz = cos_u * cos_v

            verts.extend([cx, cy, cz])
            norms.extend([nx, ny, nz])
            uvs.extend([j / segments, i / tube_segments])

    for i in range(tube_segments):
        for j in range(segments):
            first = i * (segments + 1) + j
            second = first + segments + 1

            indices.extend([first, second, first + 1])
            indices.extend([second, second + 1, first + 1])

    return (
        np.array(verts, dtype=np.float32),
        np.array(norms, dtype=np.float32),
        np.array(uvs, dtype=np.float32),
        np.array(indices, dtype=np.uint16),
    )


def build_glb(gltf_json: dict, binary_data: bytes) -> bytes:
    """构建 glb 二进制文件"""
    json_str = json.dumps(gltf_json, separators=(",", ":"))
    json_bytes = json_str.encode("utf-8")

    json_pad = (4 - len(json_bytes) % 4) % 4
    json_bytes += b" " * json_pad

    bin_pad = (4 - len(binary_data) % 4) % 4
    binary_data += b"\x00" * bin_pad

    total_length = 12 + 8 + len(json_bytes) + 8 + len(binary_data)

    header = struct.pack("<III", 0x46546C67, 2, total_length)

    json_chunk = struct.pack("<I4s", len(json_bytes), b"JSON") + json_bytes
    bin_chunk = struct.pack("<I4s", len(binary_data), b"BIN\x00") + binary_data

    return header + json_chunk + bin_chunk


def create_vrm_model():
    """创建一个最小可用的 VRM 模型"""

    HEAD_RADIUS = 0.18
    BODY_RADIUS = 0.15
    BODY_HEIGHT = 0.4
    EYE_RADIUS = 0.03
    MOUTH_RADIUS = 0.04
    MOUTH_TUBE = 0.01

    head_verts, head_norms, head_uvs, head_idx = generate_sphere(12, 16, HEAD_RADIUS)
    body_verts, body_norms, body_uvs, body_idx = generate_cylinder(12, BODY_RADIUS, BODY_HEIGHT)
    eye_verts, eye_norms, eye_uvs, eye_idx = generate_eye_sphere(8, EYE_RADIUS)
    mouth_verts, mouth_norms, mouth_uvs, mouth_idx = generate_mouth(12, MOUTH_RADIUS, MOUTH_TUBE)

    head_offset = np.array([0.0, 1.05, 0.0], dtype=np.float32)
    body_offset = np.array([0.0, 0.55, 0.0], dtype=np.float32)
    left_eye_offset = np.array([-0.06, 1.08, 0.15], dtype=np.float32)
    right_eye_offset = np.array([0.06, 1.08, 0.15], dtype=np.float32)
    mouth_offset = np.array([0.0, 1.0, 0.16], dtype=np.float32)

    head_pos = head_verts.reshape(-1, 3) + head_offset
    body_pos = body_verts.reshape(-1, 3) + body_offset
    left_eye_pos = eye_verts.reshape(-1, 3) + left_eye_offset
    right_eye_pos = eye_verts.reshape(-1, 3) + right_eye_offset
    mouth_pos = mouth_verts.reshape(-1, 3) + mouth_offset

    all_positions = np.concatenate([
        head_pos.ravel(),
        body_pos.ravel(),
        left_eye_pos.ravel(),
        right_eye_pos.ravel(),
        mouth_pos.ravel(),
    ]).astype(np.float32)

    all_normals = np.concatenate([
        head_norms,
        body_norms,
        eye_norms,
        eye_norms,
        mouth_norms,
    ]).astype(np.float32)

    all_uvs = np.concatenate([
        head_uvs,
        body_uvs,
        eye_uvs,
        eye_uvs,
        mouth_uvs,
    ]).astype(np.float32)

    head_idx_offset = 0
    body_idx_offset = len(head_verts) // 3
    left_eye_idx_offset = body_idx_offset + len(body_verts) // 3
    right_eye_idx_offset = left_eye_idx_offset + len(eye_verts) // 3
    mouth_idx_offset = right_eye_idx_offset + len(eye_verts) // 3

    all_indices = np.concatenate([
        head_idx + head_idx_offset,
        body_idx + body_idx_offset,
        eye_idx + left_eye_idx_offset,
        eye_idx + right_eye_idx_offset,
        mouth_idx + mouth_idx_offset,
    ]).astype(np.uint16)

    total_verts = len(all_positions) // 3
    total_indices = len(all_indices)

    pos_bytes = all_positions.tobytes()
    norm_bytes = all_normals.tobytes()
    uv_bytes = all_uvs.tobytes()
    idx_bytes = all_indices.tobytes()

    pos_len = len(pos_bytes)
    norm_len = len(norm_bytes)
    uv_len = len(uv_bytes)
    idx_len = len(idx_bytes)

    binary_data = pos_bytes + norm_bytes + uv_bytes + idx_bytes

    pos_bv = 0
    norm_bv = 1
    uv_bv = 2
    idx_bv = 3

    pos_accessor = 0
    norm_accessor = 1
    uv_accessor = 2
    idx_accessor = 3

    bbox_min = [float(all_positions[i::3].min()) for i in range(3)]
    bbox_max = [float(all_positions[i::3].max()) for i in range(3)]

    gltf = {
        "asset": {
            "version": "2.0",
            "generator": "CompanionOS VRM Generator"
        },
        "extensionsUsed": [
            "VRM"
        ],
        "extensionsRequired": [
            "VRM"
        ],
        "extensions": {
            "VRM": {
                "specVersion": "1.0",
                "meta": {
                    "title": "CompanionOS Default Avatar",
                    "version": "1.0",
                    "author": "CompanionOS",
                    "contact": "",
                    "reference": "",
                    "allowedUser": "Everyone",
                    "violentUssage": False,
                    "sexualUssage": False,
                    "commercialUssage": False,
                    "otherPermissionUrl": "",
                    "licenseName": "CC0"
                },
                "firstPerson": {
                    "firstPersonBone": "head",
                    "firstPersonBoneOffset": {"x": 0, "y": 0, "z": 0},
                    "meshAnnotations": {},
                    "lookAtTypeName": "Bone",
                    "lookAtHorizontalInner": {
                        "curve": [0, 0, 0, 1],
                        "xRange": 90,
                        "yRange": 10
                    },
                    "lookAtHorizontalOuter": {
                        "curve": [0, 0, 0, 1],
                        "xRange": 90,
                        "yRange": 10
                    },
                    "lookAtVerticalDown": {
                        "curve": [0, 0, 0, 1],
                        "xRange": 90,
                        "yRange": 10
                    },
                    "lookAtVerticalUp": {
                        "curve": [0, 0, 0, 1],
                        "xRange": 90,
                        "yRange": 10
                    }
                },
                "humanoid": {
                    "humanBones": {
                        "head": {"node": 0},
                        "neck": {"node": 1},
                        "spine": {"node": 2},
                        "hips": {"node": 3}
                    }
                },
                "blendShapeMaster": {
                    "blendShapeGroups": [
                        {
                            "name": "Happy",
                            "presetName": "happy",
                            "binds": [],
                            "materialValues": []
                        },
                        {
                            "name": "Sad",
                            "presetName": "sad",
                            "binds": [],
                            "materialValues": []
                        },
                        {
                            "name": "Angry",
                            "presetName": "angry",
                            "binds": [],
                            "materialValues": []
                        },
                        {
                            "name": "Surprised",
                            "presetName": "surprised",
                            "binds": [],
                            "materialValues": []
                        },
                        {
                            "name": "Fearful",
                            "presetName": "fearful",
                            "binds": [],
                            "materialValues": []
                        }
                    ]
                },
                "secondaryAnimation": {
                    "boneGroups": [],
                    "colliderGroups": []
                }
            }
        },
        "scenes": [
            {
                "nodes": [0]
            }
        ],
        "nodes": [
            {
                "name": "Head",
                "translation": [0.0, 1.05, 0.0],
                "mesh": 0
            },
            {
                "name": "Neck",
                "translation": [0.0, 0.85, 0.0],
                "children": [0]
            },
            {
                "name": "Spine",
                "translation": [0.0, 0.55, 0.0],
                "children": [1]
            },
            {
                "name": "Hips",
                "translation": [0.0, 0.0, 0.0],
                "children": [2]
            }
        ],
        "meshes": [
            {
                "primitives": [
                    {
                        "attributes": {
                            "POSITION": pos_accessor,
                            "NORMAL": norm_accessor,
                            "TEXCOORD_0": uv_accessor
                        },
                        "indices": idx_accessor,
                        "mode": 4
                    }
                ],
                "name": "Body"
            }
        ],
        "accessors": [
            {
                "bufferView": pos_bv,
                "componentType": 5126,
                "count": total_verts,
                "type": "VEC3",
                "max": bbox_max,
                "min": bbox_min
            },
            {
                "bufferView": norm_bv,
                "componentType": 5126,
                "count": total_verts,
                "type": "VEC3"
            },
            {
                "bufferView": uv_bv,
                "componentType": 5126,
                "count": total_verts,
                "type": "VEC2"
            },
            {
                "bufferView": idx_bv,
                "componentType": 5123,
                "count": total_indices,
                "type": "SCALAR"
            }
        ],
        "bufferViews": [
            {
                "buffer": 0,
                "byteOffset": 0,
                "byteLength": pos_len,
                "byteStride": 12,
                "target": 34962
            },
            {
                "buffer": 0,
                "byteOffset": pos_len,
                "byteLength": norm_len,
                "byteStride": 12,
                "target": 34962
            },
            {
                "buffer": 0,
                "byteOffset": pos_len + norm_len,
                "byteLength": uv_len,
                "byteStride": 8,
                "target": 34962
            },
            {
                "buffer": 0,
                "byteOffset": pos_len + norm_len + uv_len,
                "byteLength": idx_len,
                "target": 34963
            }
        ],
        "buffers": [
            {
                "byteLength": len(binary_data)
            }
        ]
    }

    glb_data = build_glb(gltf, binary_data)

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    with open(OUTPUT_PATH, "wb") as f:
        f.write(glb_data)

    file_size = len(glb_data)
    print(f"[OK] VRM model generated: {OUTPUT_PATH}")
    print(f"     File size: {file_size:,} bytes ({file_size / 1024:.1f} KB)")
    print(f"     Vertices: {total_verts}")
    print(f"     Indices: {total_indices}")
    print(f"     Meshes: 5 (head + body + left_eye + right_eye + mouth)")

    return True


def main():
    print("=" * 50)
    print("  CompanionOS VRM Model Generator")
    print("=" * 50)
    print()

    try:
        create_vrm_model()
        print()
        print("Done! The VRM model is ready for use.")
        print(f"Place it at: {OUTPUT_PATH}")
        print()
        print("The vrm.html will automatically load it on startup.")
        print("If loading fails, it falls back to the placeholder avatar.")
    except Exception as e:
        print(f"[ERROR] Failed to generate VRM model: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
