#!/usr/bin/env python3
"""latent transport 回归测试。"""

import os
import sys

import numpy as np
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from scripts.latent_transport import (
    build_transport_blob,
    decode_transport_payload,
    save_decoded_npz,
    unpack_transport_frame,
)


def test_float32_raw_roundtrip(tmp_path):
    rng = np.random.default_rng(0)
    latent = rng.standard_normal((1, 32, 32, 32)).astype(np.float32)
    input_path = tmp_path / 'latent_float32.npz'
    np.savez(input_path, latent=latent)

    blob, meta, stats = build_transport_blob(
        str(input_path),
        job_id='float32_case',
        payload_codec='float32-raw',
    )
    unpacked_meta, payload_bytes = unpack_transport_frame(blob)
    decoded = decode_transport_payload(unpacked_meta, payload_bytes)

    assert meta['payload_codec'] == 'float32-raw'
    assert unpacked_meta['shape'] == [1, 32, 32, 32]
    assert stats['payload_bytes'] == latent.nbytes
    assert decoded.storage_format == 'latent'
    np.testing.assert_array_equal(decoded.latent, latent)

    output_path = tmp_path / 'float32_roundtrip.npz'
    save_decoded_npz(decoded, output_path)
    with np.load(output_path) as saved:
        np.testing.assert_array_equal(saved['latent'], latent)


def test_webp_lossless_roundtrip(tmp_path):
    rng = np.random.default_rng(1)
    quant = rng.integers(0, 256, size=(32, 32, 32), dtype=np.uint8)
    scale = np.float32(0.0625)
    zero_point = np.float32(127.0)
    input_path = tmp_path / 'latent_quant.npz'
    np.savez(input_path, quant=quant, scale=scale, zero_point=zero_point)

    blob, meta, stats = build_transport_blob(
        str(input_path),
        job_id='webp_case',
        payload_codec='webp-lossless',
    )
    unpacked_meta, payload_bytes = unpack_transport_frame(blob)
    decoded = decode_transport_payload(unpacked_meta, payload_bytes)
    expected_latent = np.expand_dims((quant.astype(np.float32) - zero_point) * scale, axis=0)

    assert meta['payload_codec'] == 'webp-lossless'
    assert decoded.storage_format == 'quant'
    assert stats['payload_bytes'] < stats['latent_bytes']
    np.testing.assert_array_equal(decoded.latent, expected_latent)

    output_path = tmp_path / 'webp_roundtrip.npz'
    save_decoded_npz(decoded, output_path)
    with np.load(output_path) as saved:
        np.testing.assert_array_equal(saved['quant'], np.expand_dims(quant, axis=0))
        np.testing.assert_array_equal(saved['scale'], np.asarray(scale, dtype=np.float32))
        np.testing.assert_array_equal(saved['zero_point'], np.asarray(zero_point, dtype=np.float32))


def test_webp_lossless_can_skip_latent_sha_check(tmp_path):
    rng = np.random.default_rng(2)
    quant = rng.integers(0, 256, size=(32, 32, 32), dtype=np.uint8)
    input_path = tmp_path / 'latent_quant_skip_sha.npz'
    np.savez(
        input_path,
        quant=quant,
        scale=np.float32(0.125),
        zero_point=np.float32(120.0),
    )

    blob, _, _ = build_transport_blob(
        str(input_path),
        job_id='webp_skip_sha',
        payload_codec='webp-lossless',
    )
    meta, payload_bytes = unpack_transport_frame(blob)
    tampered_meta = dict(meta)
    tampered_meta['latent_sha256'] = '0' * 64

    with pytest.raises(RuntimeError, match='latent_sha256 不匹配'):
        decode_transport_payload(tampered_meta, payload_bytes, verify_latent_sha=True)

    decoded = decode_transport_payload(
        tampered_meta,
        payload_bytes,
        verify_latent_sha=False,
    )
    assert decoded.storage_format == 'quant'
    assert decoded.latent.shape == (1, 32, 32, 32)
