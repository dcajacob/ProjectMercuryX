// SPDX-License-Identifier: GPL-3.0-or-later
#include "MercuryOrbiter.h"
#include "Base.h"
void oapiGetBaseEquPos(OBJHANDLE handle,double* longitude,double* latitude,double* radius)
{
    auto* base=static_cast<Base*>(handle);
    base->EquPos(*longitude,*latitude);
    if(radius) *radius=oapiGetSize(oapiGetBasePlanet(handle));
}
