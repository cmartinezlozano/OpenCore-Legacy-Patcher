"""Add the local Haswell fixes to the pinned, complete PatcherSupportPkg PR."""
from pathlib import Path
import shutil


def apply(source):
    here = Path(__file__).resolve().parent
    legacy = source / "Sources/LegacyMetal"
    adapter = legacy / "IntelAdapter"
    for path in (here / "native").iterdir():
        shutil.copy2(path, adapter / path.name)
    for path in (here / "tests").iterdir():
        if path.is_file() and path.suffix in (".cpp", ".py") and not path.name.startswith("test_"):
            shutil.copy2(path, legacy / "Tests" / path.name)
    cpp = adapter / "intelatomics.cpp"
    text = cpp.read_text()
    marker = "static int hookedRun(void *self, LLVMModuleRef module) {"
    if text.count(marker) != 1 or 'HaswellSimulatorCompat.h' in text:
        raise RuntimeError("Unexpected or already integrated Intel adapter")
    text = text.replace(marker, '#include "HaswellSimulatorCompat.h"\n\n' + marker)
    marker = "    int result = passManagerRun(self, module);"
    if text.count(marker) != 1:
        raise RuntimeError("Unexpected pass manager hook")
    cpp.write_text(text.replace(marker, "    if (module && !ivyBridgePlugin) haswellSimulatorRepairs(module);\n" + marker))
    tbd = adapter / "libLLVM3802.tbd"
    text = tbd.read_text()
    marker = "_LLVMStructGetTypeAtIndex ]"
    if text.count(marker) != 1:
        raise RuntimeError("Unexpected LLVM import list")
    tbd.write_text(text.replace(marker, "_LLVMStructGetTypeAtIndex, _LLVMVerifyModule ]"))
    build = legacy / "build.sh"
    text = build.read_text()
    marker = "shasum -a 256 MetalOldCompat.dylib"
    if text.count(marker) != 1:
        raise RuntimeError("Unexpected upstream payload builder")
    addition = r'''# Native MacBookPro11,2 / Tahoe target-info repair, on payload copies only.
clang++ -arch x86_64 -mmacosx-version-min=13.0 -std=c++17 -dynamiclib -O2 -Wall \
    -install_name @rpath/HaswellTargetInfoCompat.dylib \
    "$HERE/IntelAdapter/HaswellTargetInfoCompat.cpp" -o "$B/HaswellTargetInfoCompat.dylib"
GPU25="$UB/13.2.1-25/System/Library/PrivateFrameworks/GPUCompiler.framework/Versions/31001/Libraries"
cp "$GPU25/libGPUCompilerImpl.dylib" "$B/libGPUCompilerImpl-tahoe.unsigned"
codesign --remove-signature "$B/libGPUCompilerImpl-tahoe.unsigned"
python3 -I "$HERE/tools/add_weak_dylib.py" "$B/libGPUCompilerImpl-tahoe.unsigned" \
    "$GPU25/libGPUCompilerImpl.dylib" @loader_path/HaswellTargetInfoCompat.dylib
cp "$B/HaswellTargetInfoCompat.dylib" "$GPU25/"
codesign -f -s - "$GPU25/libGPUCompilerImpl.dylib" "$GPU25/HaswellTargetInfoCompat.dylib"
'''
    build.write_text(text.replace(marker, addition + "\n" + marker))
