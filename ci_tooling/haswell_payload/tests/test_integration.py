import sys
from pathlib import Path
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import integrate


class IntegrationTests(unittest.TestCase):
    def test_native_fixes_are_wired_without_replacing_upstream_passes(self):
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary)
            legacy = source / "Sources/LegacyMetal"
            adapter = legacy / "IntelAdapter"
            adapter.mkdir(parents=True)
            (legacy / "Tests").mkdir()
            (adapter / "intelatomics.cpp").write_text(
                "static int hookedRun(void *self, LLVMModuleRef module) {\n"
                "    upstreamAllFixes(module);\n"
                "    int result = passManagerRun(self, module);\n}\n"
            )
            (adapter / "libLLVM3802.tbd").write_text("symbols: [ _LLVMStructGetTypeAtIndex ]\n")
            (legacy / "build.sh").write_text("buildAllUpstreamPayloads\nshasum -a 256 MetalOldCompat.dylib\n")
            integrate.apply(source)
            text = (adapter / "intelatomics.cpp").read_text()
            self.assertIn("upstreamAllFixes(module)", text)
            self.assertIn("haswellSimulatorRepairs(module)", text)
            self.assertIn("HaswellSimulatorCompat.h", text)
            self.assertTrue((adapter / "HaswellTargetInfoCompat.cpp").is_file())
            build = (legacy / "build.sh").read_text()
            self.assertIn("buildAllUpstreamPayloads", build)
            self.assertIn("@loader_path/HaswellTargetInfoCompat.dylib", build)
            with self.assertRaises(RuntimeError):
                integrate.apply(source)


if __name__ == "__main__":
    unittest.main()
