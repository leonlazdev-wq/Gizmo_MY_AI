import struct
from pathlib import Path
from enum import IntEnum


class GGUFValueType(IntEnum):
    UINT8 = 0
    INT8 = 1
    UINT16 = 2
    INT16 = 3
    UINT32 = 4
    INT32 = 5
    FLOAT32 = 6
    BOOL = 7
    STRING = 8
    ARRAY = 9
    UINT64 = 10
    INT64 = 11
    FLOAT64 = 12


_simple_value_packing = {
    GGUFValueType.UINT8: "<B",
    GGUFValueType.INT8: "<b",
    GGUFValueType.UINT16: "<H",
    GGUFValueType.INT16: "<h",
    GGUFValueType.UINT32: "<I",
    GGUFValueType.INT32: "<i",
    GGUFValueType.FLOAT32: "<f",
    GGUFValueType.UINT64: "<Q",
    GGUFValueType.INT64: "<q",
    GGUFValueType.FLOAT64: "<d",
    GGUFValueType.BOOL: "?",
}

value_type_info = {
    GGUFValueType.UINT8: 1,
    GGUFValueType.INT8: 1,
    GGUFValueType.UINT16: 2,
    GGUFValueType.INT16: 2,
    GGUFValueType.UINT32: 4,
    GGUFValueType.INT32: 4,
    GGUFValueType.FLOAT32: 4,
    GGUFValueType.UINT64: 8,
    GGUFValueType.INT64: 8,
    GGUFValueType.FLOAT64: 8,
    GGUFValueType.BOOL: 1,
}


def get_single(value_type, file):
    if value_type == GGUFValueType.STRING:
        value_length = struct.unpack("<Q", file.read(8))[0]
        value = file.read(value_length)
        try:
            value = value.decode('utf-8')
        except Exception:
            pass
    else:
        type_str = _simple_value_packing.get(value_type)
        bytes_length = value_type_info.get(value_type)
        value = struct.unpack(type_str, file.read(bytes_length))[0]

    return value


def load_metadata(model_file):
    """Load GGUF metadata with full validation and safe parsing."""
    model_file = Path(model_file)

    # ── File existence check ───────────────────────────────────────────────────
    if not model_file.exists():
        print(f"[warn] metadata_gguf: file not found: {model_file}")
        return {}

    # ── File size check ────────────────────────────────────────────────────────
    MIN_VALID_SIZE = 1024  # 1 KB minimum for a real GGUF
    try:
        file_size = model_file.stat().st_size
    except Exception as e:
        print(f"[warn] metadata_gguf: cannot stat {model_file.name}: {e}")
        return {}

    if file_size < MIN_VALID_SIZE:
        print(f"[warn] metadata_gguf: file too small ({file_size} bytes): {model_file.name}")
        try:
            model_file.unlink()
            print(f"[info] metadata_gguf: deleted corrupt file: {model_file.name}")
        except Exception:
            pass
        return {}

    # ── Parse GGUF ─────────────────────────────────────────────────────────────
    metadata = {}
    try:
        with open(model_file, 'rb') as file:
            # Magic number — must be 'GGUF'
            magic_bytes = file.read(4)
            if len(magic_bytes) < 4:
                print(f"[error] metadata_gguf: could not read header: {model_file.name}")
                return {}

            GGUF_MAGIC = struct.unpack("<I", magic_bytes)[0]
            EXPECTED_MAGIC = 0x46554747  # b'GGUF'
            if GGUF_MAGIC != EXPECTED_MAGIC:
                print(f"[error] metadata_gguf: bad magic 0x{GGUF_MAGIC:08X} in {model_file.name}")
                return {}

            # Version
            version = struct.unpack("<I", file.read(4))[0]

            # Tensor count and KV count
            if version == 1:
                tensor_count = struct.unpack("<Q", file.read(8))[0]
                kv_count = struct.unpack("<Q", file.read(8))[0]
            else:
                tensor_count = struct.unpack("<Q", file.read(8))[0]
                kv_count = struct.unpack("<Q", file.read(8))[0]

            # Read key-value metadata pairs
            for _ in range(kv_count):
                # Key
                key_length = struct.unpack("<Q", file.read(8))[0]
                key = file.read(key_length).decode('utf-8')

                # Value type
                value_type = GGUFValueType(struct.unpack("<I", file.read(4))[0])

                # Value
                if value_type == GGUFValueType.ARRAY:
                    array_type = GGUFValueType(struct.unpack("<I", file.read(4))[0])
                    array_length = struct.unpack("<Q", file.read(8))[0]
                    value = [get_single(array_type, file) for _ in range(array_length)]
                else:
                    value = get_single(value_type, file)

                metadata[key] = value

    except Exception as e:
        print(f"[error] metadata_gguf: failed to parse {model_file.name}: {e}")
        return {}

    return metadata
