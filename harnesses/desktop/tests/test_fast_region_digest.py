"""Fast hashing preserves content-bound target identity, never cached identity."""
import importlib.util
import pathlib
import pytest
from PIL import Image

SPEC = importlib.util.spec_from_file_location('fast_desktop', pathlib.Path(__file__).parents[1] / 'desktop.py')
DESKTOP = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(DESKTOP)

@pytest.mark.parametrize('mode', ['L', 'LA', 'RGB', 'RGBA'])
@pytest.mark.parametrize('compress', [0, 1, 9])
def test_same_digest_as_reference(tmp_path, mode, compress):
    channels = len(mode)
    image = Image.frombytes(mode, (61, 47), bytes((i * 37 + i // 13) % 256 for i in range(61 * 47 * channels)))
    path = tmp_path / 'screen.png'
    image.save(path, compress_level=compress)
    for region in ([0, 0, 61, 47], [7, 11, 1, 1], [13, 17, 20, 23]):
        assert DESKTOP.png_region_digest(path, region) == DESKTOP.png_region_digest_python(path, region)

@pytest.mark.parametrize('region', [[-1,0,1,1], [0,0,0,1], [0,0,11,1], [True,0,1,1], [0,0,1], [0,0,1.1,1]])
def test_bad_region_fails(tmp_path, region):
    path = tmp_path / 'screen.png'
    Image.new('RGB', (10,10)).save(path)
    with pytest.raises(ValueError):
        DESKTOP.png_region_digest(path, region)

def test_same_path_new_pixels_not_cached(tmp_path):
    path = tmp_path / 'screen.png'
    Image.new('RGB', (10,10), 'red').save(path)
    before = DESKTOP.png_region_digest(path, [0,0,10,10])
    Image.new('RGB', (10,10), 'blue').save(path)
    assert before != DESKTOP.png_region_digest(path, [0,0,10,10])
