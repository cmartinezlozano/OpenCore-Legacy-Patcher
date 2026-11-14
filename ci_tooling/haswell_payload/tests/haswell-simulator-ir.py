#!/usr/bin/env python3
"""Check the simulator additions against synthetic AIR, without a system install."""
import ctypes as c
import json
from pathlib import Path
import sys

llvm = c.CDLL('/System/Library/PrivateFrameworks/GPUCompiler.framework/Versions/3802/Libraries/libLLVM.dylib', mode=c.RTLD_GLOBAL)
adapter = c.CDLL(str(Path(sys.argv[1]).resolve()))
ptr = c.c_void_p


def api(name, arguments, result):
    function = getattr(llvm, name)
    function.argtypes, function.restype = arguments, result
    return function


context = api('LLVMContextCreate', [], ptr)
buffer = api('LLVMCreateMemoryBufferWithMemoryRangeCopy', [c.c_char_p, c.c_size_t, c.c_char_p], ptr)
parse = api('LLVMParseIRInContext', [ptr, ptr, c.POINTER(ptr), c.POINTER(ptr)], c.c_int)
verify = api('LLVMVerifyModule', [ptr, c.c_int, c.POINTER(ptr)], c.c_int)
printer = api('LLVMPrintModuleToString', [ptr], ptr)
dispose = api('LLVMDisposeMessage', [ptr], None)
adapter.HaswellSimulatorRepairForTesting.argtypes = [ptr]
adapter.HaswellSimulatorRepairForTesting.restype = c.c_uint

half2 = '''
define <2 x half> @private_half2(i32 %index, <2 x half> %input) {
  %array = alloca [4 x <2 x half>], align 4
  %p0 = getelementptr [4 x <2 x half>], [4 x <2 x half>]* %array, i32 0, i32 0
  %p1 = getelementptr [4 x <2 x half>], [4 x <2 x half>]* %array, i32 0, i32 1
  %p2 = getelementptr [4 x <2 x half>], [4 x <2 x half>]* %array, i32 0, i32 2
  %p3 = getelementptr [4 x <2 x half>], [4 x <2 x half>]* %array, i32 0, i32 3
  store <2 x half> %input, <2 x half>* %p0, align 4
  store <2 x half> %input, <2 x half>* %p1, align 4
  store <2 x half> %input, <2 x half>* %p2, align 4
  store <2 x half> %input, <2 x half>* %p3, align 4
  %bounded = and i32 %index, 3
  %pointer = getelementptr [4 x <2 x half>], [4 x <2 x half>]* %array, i32 0, i32 %bounded
  %value = load <2 x half>, <2 x half>* %pointer, align 4
  ret <2 x half> %value
}
'''
null = '''
%struct._texture_2d_t = type opaque
%struct._sampler_t = type opaque
declare %struct._texture_2d_t addrspace(1)* @air.get_null_texture_2d()
declare <4 x half> @air.sample_texture_2d.v4f16(%struct._texture_2d_t addrspace(1)*, %struct._sampler_t addrspace(2)*, <2 x float>, i1, <2 x i32>, i1, float, i32)
define <4 x half> @"space::rasterizeMeshVertex"() {
  %texture = call %struct._texture_2d_t addrspace(1)* @air.get_null_texture_2d()
  %value = call <4 x half> @air.sample_texture_2d.v4f16(%struct._texture_2d_t addrspace(1)* %texture, %struct._sampler_t addrspace(2)* undef, <2 x float> zeroinitializer, i1 true, <2 x i32> zeroinitializer, i1 false, float 0.0, i32 0)
  ret <4 x half> %value
}
'''
nonnull = null.replace('@"space::rasterizeMeshVertex"()', '@"space::rasterizeMeshVertex"(%struct._texture_2d_t addrspace(1)* %texture)').replace('  %texture = call %struct._texture_2d_t addrspace(1)* @air.get_null_texture_2d()\n', '')
results = []
for name, ir, expected in (
    ('private-half2-word-accesses', half2, 5),
    ('exact-null-texture-fallback', null, 1 << 16),
    ('other-shader-unchanged', null.replace('space::rasterizeMeshVertex', 'space::otherVertex'), 0),
    ('bound-texture-unchanged', nonnull, 0),
):
    data = ir.encode()
    module, error = ptr(), ptr()
    assert parse(context(), buffer(data, len(data), name.encode()), c.byref(module), c.byref(error)) == 0
    assert verify(module, 2, c.byref(error)) == 0
    count = adapter.HaswellSimulatorRepairForTesting(module)
    assert count == expected, (name, count, expected)
    assert verify(module, 2, c.byref(error)) == 0
    text_pointer = printer(module)
    text = c.string_at(text_pointer).decode()
    dispose(text_pointer)
    if name == 'private-half2-word-accesses':
        assert text.count('store volatile i32') == 4
        assert text.count('load volatile i32') == 1
        assert 'define <2 x half> @private_half2(i32 %index, <2 x half> %input)' in text
    if name == 'exact-null-texture-fallback':
        assert 'ret <4 x half> zeroinitializer' in text
        assert 'call <4 x half> @air.sample_texture_2d' not in text
    if name in ('other-shader-unchanged', 'bound-texture-unchanged'):
        assert 'call <4 x half> @air.sample_texture_2d' in text
    results.append({'test': name, 'passed': True, 'rewrites': count})
print(json.dumps(results, indent=2))
