// Integrated with the PR #22 AIR adapter. Layout-preserving additions only.
#pragma once
#include "HaswellLocalProfile.h"

extern "C" int LLVMVerifyModule(LLVMModuleRef, int, char **);

static unsigned haswellPrivateHalf2Words(LLVMModuleRef module) {
    if (!haswellLocalProfile()) return 0;
    if (const char *setting = getenv("INTEL_HASWELL_HALF2_WORD"); setting && !strcmp(setting, "0")) return 0;
    LLVMContextRef context = LLVMGetModuleContext(module);
    LLVMTypeRef word = LLVMInt32TypeInContext(context), pointer = LLVMPointerType(word, 0);
    LLVMBuilderRef builder = LLVMCreateBuilderInContext(context);
    unsigned changed = 0;
    for (LLVMValueRef function = LLVMGetFirstFunction(module); function; function = LLVMGetNextFunction(function))
        for (LLVMBasicBlockRef block = LLVMGetFirstBasicBlock(function); block; block = LLVMGetNextBasicBlock(block))
            for (LLVMValueRef inst = LLVMGetFirstInstruction(block), next; inst; inst = next) {
                next = LLVMGetNextInstruction(inst);
                bool load = LLVMIsALoadInst(inst), store = !load && LLVMIsAStoreInst(inst);
                if (!load && !store) continue;
                LLVMValueRef value = load ? inst : LLVMGetOperand(inst, 0);
                LLVMTypeRef type = LLVMTypeOf(value);
                if (LLVMGetTypeKind(type) != 13 || LLVMGetVectorSize(type) != 2 || LLVMGetTypeKind(LLVMGetElementType(type)) != 1) continue;
                LLVMValueRef address = LLVMGetOperand(inst, load ? 0 : 1);
                if (LLVMGetPointerAddressSpace(LLVMTypeOf(address)) != 0) continue;
                LLVMPositionBuilderBefore(builder, inst);
                LLVMValueRef wordAddress = LLVMBuildBitCast(builder, address, pointer, "haswell.half2.word.ptr");
                LLVMValueRef access;
                if (load) {
                    access = LLVMBuildLoad(builder, wordAddress, "haswell.half2.word");
                    LLVMReplaceAllUsesWith(inst, LLVMBuildBitCast(builder, access, type, "haswell.half2"));
                } else {
                    access = LLVMBuildStore(builder, LLVMBuildBitCast(builder, value, word, "haswell.half2.word"), wordAddress);
                }
                LLVMSetVolatile(access, 1);
                unsigned alignment = LLVMGetAlignment(inst);
                LLVMSetAlignment(access, alignment ? alignment : 4);
                LLVMInstructionEraseFromParent(inst);
                changed++;
            }
    LLVMDisposeBuilder(builder);
    return changed;
}

static unsigned haswellNullTextureFallback(LLVMModuleRef module) {
    if (!haswellLocalProfile()) return 0;
    if (const char *setting = getenv("INTEL_HASWELL_NULL_TEXTURE"); setting && !strcmp(setting, "0")) return 0;
    LLVMValueRef function = LLVMGetNamedFunction(module, "space::rasterizeMeshVertex");
    if (!function) return 0;
    unsigned changed = 0;
    for (LLVMBasicBlockRef block = LLVMGetFirstBasicBlock(function); block; block = LLVMGetNextBasicBlock(block))
        for (LLVMValueRef inst = LLVMGetFirstInstruction(block), next; inst; inst = next) {
            next = LLVMGetNextInstruction(inst);
            if (!LLVMIsACallInst(inst) || strcmp(LLVMGetValueName(LLVMGetCalledValue(inst)), "air.sample_texture_2d.v4f16")) continue;
            LLVMValueRef texture = LLVMGetOperand(inst, 0);
            if (!LLVMIsACallInst(texture) || strcmp(LLVMGetValueName(LLVMGetCalledValue(texture)), "air.get_null_texture_2d")) continue;
            LLVMReplaceAllUsesWith(inst, LLVMConstNull(LLVMTypeOf(inst)));
            LLVMInstructionEraseFromParent(inst);
            if (!LLVMGetFirstUse(texture)) LLVMInstructionEraseFromParent(texture);
            changed++;
        }
    return changed;
}

static unsigned haswellSimulatorRepairs(LLVMModuleRef module) {
    unsigned words = haswellPrivateHalf2Words(module), nulls = haswellNullTextureFallback(module);
    if (words || nulls) {
        char *error = nullptr;
        int invalid = LLVMVerifyModule(module, 2, &error); // ReturnStatusAction
        if (invalid) {
            fprintf(stderr, "[haswell-local] invalid AIR after simulator repair: %s\n", error ? error : "unknown");
            if (error) LLVMDisposeMessage(error);
            abort(); // Never pass a partially transformed module to code generation.
        }
        if (error) LLVMDisposeMessage(error);
        if (getenv("INTELTEX_LOG")) fprintf(stderr, "[haswell-local] %u private half2 word access(es), %u exact null texture fallback(s)\n", words, nulls);
    }
    return words | (nulls << 16);
}

#ifdef INTELTEX_INTERPOSE
extern "C" unsigned HaswellSimulatorRepairForTesting(LLVMModuleRef module) {
    return haswellSimulatorRepairs(module);
}
#endif
