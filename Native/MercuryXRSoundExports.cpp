// SPDX-License-Identifier: GPL-3.0-or-later
#include "XRSoundDLL.h"
#include "VesselXRSoundEngine.h"
#include "Production/NativeAbi.h"
#include "Production/ModuleBootstrap.h"
#include <cstring>

// The existing XRSound engine owns this interface and its vessel lifetime.
// Clients and the plugin must use the same admitted native SDK and C++ ABI.
extern "C" ORBITER_NATIVE_EXPORT XRSoundEngine10*
OrbiterNativeXRSoundVessel(OBJHANDLE vessel,const char* sdk,const char* abi) noexcept
{
    if(!XRSoundDLL::s_pInstance || !sdk || !abi ||
       std::strcmp(sdk,ORBITER_NATIVE_SDK_BUILD) || std::strcmp(abi,ORBITER_NATIVE_CPP_ABI)) return nullptr;
    try {return XRSoundDLL::GetXRSoundEngineInstance(vessel,true);}
    catch(...) {return nullptr;}
}
