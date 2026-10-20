import io
import json
import struct
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from localcall import native_host
from scripts.install_native_host import install

class NativeTests(unittest.TestCase):
    def test_framing_roundtrip(self):
        stream=io.BytesIO()
        native_host.write_message(stream, {'action':'start'})
        stream.seek(0)
        self.assertEqual(native_host.read_message(stream), {'action':'start'})
    def test_rejects_bad_frames(self):
        for raw in [b'', b'abc', struct.pack('@I',5000), struct.pack('@I',5)+b'{}']:
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                native_host.read_message(io.BytesIO(raw))
    def test_installer_limits_origins_and_quotes_paths(self):
        with tempfile.TemporaryDirectory(prefix="LocalCall space '") as tmp:
            root=Path(tmp)/'project';root.mkdir()
            home=Path(tmp)/'home'
            install(['a'*32],root,home)
            manifest=json.loads((home/'Library/Application Support/BraveSoftware/Brave-Browser/NativeMessagingHosts/org.localcall.launcher.json').read_text())
            self.assertEqual(manifest['allowed_origins'],['chrome-extension://'+'a'*32+'/'])
            self.assertTrue(Path(manifest['path']).is_file())
            self.assertEqual(Path(manifest['path']).stat().st_mode & 0o777,0o700)
            with self.assertRaises(ValueError):install(['*'],root,home)
    def test_reuses_existing_server_without_launching(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(native_host,'ready',return_value='secret'), patch.object(native_host.subprocess,'Popen') as spawn:
            self.assertEqual(native_host.start_backend(Path(tmp)),{'ok':True,'token':'secret'})
            spawn.assert_not_called()
    def test_startup_uses_detached_fixed_command(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(native_host,'ready',side_effect=[None,'secret']), patch.object(native_host.subprocess,'Popen') as spawn:
            self.assertTrue(native_host.start_backend(Path(tmp))['ok'])
            args,kw=spawn.call_args
            self.assertEqual(args[0][1:],['-m','localcall.server','--port','8765'])
            self.assertTrue(kw['start_new_session'])
            self.assertEqual(kw['stdin'],native_host.subprocess.DEVNULL)

    def test_real_background_start_and_reuse(self):
        import shutil
        import socket
        import subprocess
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            shutil.copytree(native_host.ROOT/'localcall',root/'localcall',ignore=shutil.ignore_patterns('__pycache__'))
            with socket.socket() as sock:
                sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
            children=[]
            real_spawn=subprocess.Popen
            def spawn(*args,**kwargs):
                child=real_spawn(*args,**kwargs);children.append(child);return child
            try:
                with patch.object(native_host.subprocess,'Popen',side_effect=spawn):
                    first=native_host.start_backend(root,port)
                    second=native_host.start_backend(root,port)
                self.assertEqual(first,second)
                self.assertEqual(len(children),1)
                self.assertTrue(first['token'])
            finally:
                for child in children:
                    child.terminate();child.wait(timeout=10)
