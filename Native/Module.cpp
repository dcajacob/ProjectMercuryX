// SPDX-License-Identifier: GPL-3.0-or-later
#include "MercuryOrbiter.h"
#include "MercurySound.h"

extern "C" VESSEL* ovcInit(OBJHANDLE,int);
extern "C" void ovcExit(VESSEL*);

namespace {
void Destroy(VESSEL* vessel)
{
    MercurySoundRelease(vessel->GetHandle());
    ovcExit(vessel);
}
using Factory=orbiter::native::VesselFactory<ovcInit,Destroy>;
const OrbiterNativeModuleDescriptor descriptor{
    sizeof(OrbiterNativeModuleDescriptor),ORBITER_NATIVE_BOOTSTRAP_VERSION,
    sizeof(void*),ORBITER_NATIVE_VESSEL,MERCURY_MODULE_NAME,
    ORBITER_NATIVE_SDK_BUILD,ORBITER_NATIVE_CPP_ABI,Factory::initialize,Factory::shutdown
};
}
extern "C" ORBITER_NATIVE_EXPORT const OrbiterNativeModuleDescriptor* ORBITER_NATIVE_CALL
OrbiterNativeQuery(std::uint32_t version) noexcept
{
    return version==ORBITER_NATIVE_BOOTSTRAP_VERSION?&descriptor:nullptr;
}
