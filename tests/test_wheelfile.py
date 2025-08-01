# coding: utf-8
from __future__ import unicode_literals

import sys
from zipfile import ZipFile, ZIP_DEFLATED

import pytest

from wheel.cli import WheelError
from wheel.util import native, as_bytes
from wheel.wheelfile import WheelFile


@pytest.fixture
def wheel_path(tmpdir):
    return str(tmpdir.join('test-1.0-py2.py3-none-any.whl'))


@pytest.mark.parametrize(
    "filename",
    [
        "foo-2-py3-none-any.whl",
        "foo-2-py2.py3-none-manylinux_2_17_x86_64.manylinux2014_x86_64.whl",
    ],
)
def test_wheelfile_re(filename, tmpdir):
    # Regression test for #208 and #485
    path = tmpdir.join(filename)
    with WheelFile(str(path), 'w') as wf:
        assert wf.parsed_filename.group('namever') == 'foo-2'


@pytest.mark.parametrize('filename', [
    'test.whl',
    'test-1.0.whl',
    'test-1.0-py2.whl',
    'test-1.0-py2-none.whl',
    "test-1.0-py 2-none-any.whl",
    'test-1.0-py2-none-any'
])
def test_bad_wheel_filename(filename):
    exc = pytest.raises(WheelError, WheelFile, filename)
    exc.match('^Bad wheel filename {!r}$'.format(filename))


def test_missing_record(wheel_path):
    with ZipFile(wheel_path, 'w') as zf:
        zf.writestr(native('hello/héllö.py'), as_bytes('print("Héllö, w0rld!")\n'))

    exc = pytest.raises(WheelError, WheelFile, wheel_path)
    exc.match("^Missing test-1.0.dist-info/RECORD file$")


def test_unsupported_hash_algorithm(wheel_path):
    with ZipFile(wheel_path, 'w') as zf:
        zf.writestr(native('hello/héllö.py'), as_bytes('print("Héllö, w0rld!")\n'))
        zf.writestr(
            'test-1.0.dist-info/RECORD',
            as_bytes('hello/héllö.py,sha000=bv-QV3RciQC2v3zL8Uvhd_arp40J5A9xmyubN34OVwo,25'))

    exc = pytest.raises(WheelError, WheelFile, wheel_path)
    exc.match("^Unsupported hash algorithm: sha000$")


@pytest.mark.parametrize('algorithm, digest', [
    ('md5', '4J-scNa2qvSgy07rS4at-Q'),
    ('sha1', 'QjCnGu5Qucb6-vir1a6BVptvOA4')
], ids=['md5', 'sha1'])
def test_weak_hash_algorithm(wheel_path, algorithm, digest):
    hash_string = '{}={}'.format(algorithm, digest)
    with ZipFile(wheel_path, 'w') as zf:
        zf.writestr(native('hello/héllö.py'), as_bytes('print("Héllö, w0rld!")\n'))
        zf.writestr('test-1.0.dist-info/RECORD',
                    as_bytes('hello/héllö.py,{},25'.format(hash_string)))

    exc = pytest.raises(WheelError, WheelFile, wheel_path)
    exc.match(r"^Weak hash algorithm \({}\) is not permitted by PEP 427$".format(algorithm))


@pytest.mark.parametrize('algorithm, digest', [
    ('sha256', 'bv-QV3RciQC2v3zL8Uvhd_arp40J5A9xmyubN34OVwo'),
    ('sha384', 'cDXriAy_7i02kBeDkN0m2RIDz85w6pwuHkt2PZ4VmT2PQc1TZs8Ebvf6eKDFcD_S'),
    ('sha512', 'kdX9CQlwNt4FfOpOKO_X0pn_v1opQuksE40SrWtMyP1NqooWVWpzCE3myZTfpy8g2azZON_'
               'iLNpWVxTwuDWqBQ')
], ids=['sha256', 'sha384', 'sha512'])
def test_testzip(wheel_path, algorithm, digest):
    hash_string = '{}={}'.format(algorithm, digest)
    with ZipFile(wheel_path, 'w') as zf:
        zf.writestr(native('hello/héllö.py'), as_bytes('print("Héllö, world!")\n'))
        zf.writestr('test-1.0.dist-info/RECORD',
                    as_bytes('hello/héllö.py,{},25'.format(hash_string)))

    with WheelFile(wheel_path) as wf:
        wf.testzip()


def test_testzip_missing_hash(wheel_path):
    with ZipFile(wheel_path, 'w') as zf:
        zf.writestr(native('hello/héllö.py'), as_bytes('print("Héllö, world!")\n'))
        zf.writestr('test-1.0.dist-info/RECORD', '')

    with WheelFile(wheel_path) as wf:
        exc = pytest.raises(WheelError, wf.testzip)
        exc.match(native("^No hash found for file 'hello/héllö.py'$"))


def test_testzip_bad_hash(wheel_path):
    with ZipFile(wheel_path, 'w') as zf:
        zf.writestr(native('hello/héllö.py'), as_bytes('print("Héllö, w0rld!")\n'))
        zf.writestr(
            'test-1.0.dist-info/RECORD',
            as_bytes('hello/héllö.py,sha256=bv-QV3RciQC2v3zL8Uvhd_arp40J5A9xmyubN34OVwo,25'))

    with WheelFile(wheel_path) as wf:
        exc = pytest.raises(WheelError, wf.testzip)
        exc.match(native("^Hash mismatch for file 'hello/héllö.py'$"))


def test_write_str(wheel_path):
    with WheelFile(wheel_path, 'w') as wf:
        wf.writestr(native('hello/héllö.py'), as_bytes('print("Héllö, world!")\n'))
        wf.writestr(native('hello/h,ll,.py'), as_bytes('print("Héllö, world!")\n'))

    with ZipFile(wheel_path, 'r') as zf:
        infolist = zf.infolist()
        assert len(infolist) == 3
        assert infolist[0].filename == native('hello/héllö.py')
        assert infolist[0].file_size == 25
        assert infolist[1].filename == native('hello/h,ll,.py')
        assert infolist[1].file_size == 25
        assert infolist[2].filename == 'test-1.0.dist-info/RECORD'

        record = zf.read('test-1.0.dist-info/RECORD')
        assert record.replace(b'SHA256=', b'sha256=') == as_bytes(
            'hello/héllö.py,sha256=bv-QV3RciQC2v3zL8Uvhd_arp40J5A9xmyubN34OVwo,25\n'
            '"hello/h,ll,.py",sha256=bv-QV3RciQC2v3zL8Uvhd_arp40J5A9xmyubN34OVwo,25\n'
            'test-1.0.dist-info/RECORD,,\n')


def test_timestamp(tmpdir_factory, wheel_path, monkeypatch):
    # An environment variable can be used to influence the timestamp on
    # TarInfo objects inside the zip.  See issue #143.
    build_dir = tmpdir_factory.mktemp('build')
    for filename in ('one', 'two', 'three'):
        build_dir.join(filename).write(filename + '\n')

    # The earliest date representable in TarInfos, 1980-01-01
    monkeypatch.setenv(native('SOURCE_DATE_EPOCH'), native('315576060'))

    with WheelFile(wheel_path, 'w') as wf:
        wf.write_files(str(build_dir))

    with ZipFile(wheel_path, 'r') as zf:
        for info in zf.infolist():
            assert info.date_time[:3] == (1980, 1, 1)
            assert info.compress_type == ZIP_DEFLATED


@pytest.mark.skipif(sys.platform == 'win32',
                    reason='Windows does not support UNIX-like permissions')
def test_attributes(tmpdir_factory, wheel_path):
    # With the change from ZipFile.write() to .writestr(), we need to manually
    # set member attributes.
    build_dir = tmpdir_factory.mktemp('build')
    files = (('foo', 0o644), ('bar', 0o755))
    for filename, mode in files:
        path = build_dir.join(filename)
        path.write(filename + '\n')
        path.chmod(mode)

    with WheelFile(wheel_path, 'w') as wf:
        wf.write_files(str(build_dir))

    with ZipFile(wheel_path, 'r') as zf:
        for filename, mode in files:
            info = zf.getinfo(filename)
            assert info.external_attr == (mode | 0o100000) << 16
            assert info.compress_type == ZIP_DEFLATED

        info = zf.getinfo('test-1.0.dist-info/RECORD')
        permissions = (info.external_attr >> 16) & 0o777
        assert permissions == 0o664
