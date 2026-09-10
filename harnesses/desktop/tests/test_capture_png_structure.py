"""Bounded container probes; no desktop calls."""
import importlib.util
import io
from pathlib import Path
import struct
import zlib
import pytest
from PIL import Image
spec=importlib.util.spec_from_file_location('png_capture',Path(__file__).parents[1]/'desktop.py')
D=importlib.util.module_from_spec(spec);spec.loader.exec_module(D)

def png(width=2,height=2):
    out=io.BytesIO();Image.new('RGB',(width,height)).save(out,format='PNG');return out.getvalue()

def chunk(kind,payload):
    return struct.pack('>I',len(payload))+kind+payload+struct.pack('>I',zlib.crc32(kind+payload)&0xffffffff)

@pytest.mark.parametrize('width,height',[(2,2),(17000,1),(5001,5000)])
def test_duplicate_ihdr_rejected_before_decode(tmp_path,width,height):
    data=png();header=chunk(b'IHDR',struct.pack('>IIBBBBB',width,height,8,2,0,0,0))
    path=tmp_path/'duplicate.png';path.write_bytes(data[:33]+header+data[33:])
    with pytest.raises(ValueError,match='duplicate IHDR'):D.verified_capture_bytes(path)

def test_valid_snapshot(tmp_path):
    path=tmp_path/'good.png';data=png();path.write_bytes(data)
    assert D.verified_capture_bytes(path)==data

@pytest.mark.parametrize('extra',[chunk(b'ABCD',b''),chunk(b'PLTE',b'abc')])
def test_illegal_critical_chunk_after_idat(tmp_path,extra):
    data=png();path=tmp_path/'bad.png';path.write_bytes(data[:-12]+extra+data[-12:])
    with pytest.raises(ValueError):D.verified_capture_bytes(path)
