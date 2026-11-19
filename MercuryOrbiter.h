// SPDX-License-Identifier: GPL-3.0-or-later
#pragma once

#ifdef MERCURY_NATIVE_ORBITER
#include "NativeVesselAPI.h"
#include "DrawAPI.h"
#include "Production/NativeVesselFactory.h"
#include "Production/NativeRenderApi.h"
#include "Production/NativeInterpreterSdk.h"
#include "Production/FlightKeys.h"
#else
#include <Orbitersdk.h>
#endif

#include <algorithm>
#include <cmath>
#include <cstdarg>
#include <cstdio>
#include <cstring>
#include <cstdint>
#include <fstream>
#include <type_traits>

#ifndef _WIN32
#include <strings.h>
using DWORD = oapi::UInt32;
using UINT = oapi::UInt;
using WORD = oapi::UInt16;
using BYTE = unsigned char;
using RECT = oapi::SdkRectangle;
inline constexpr bool TRUE=true, FALSE=false;
#define DLLCLBK extern "C"
#define _stricmp strcasecmp
#define _strnicmp strncasecmp
#define stricmp strcasecmp
#define strnicmp strncasecmp
#define sscanf_s std::sscanf
template<class A, class B> constexpr auto min(A a, B b)
{ using C=std::common_type_t<A,B>; return std::min(C(a),C(b)); }
template<class A, class B> constexpr auto max(A a, B b)
{ using C=std::common_type_t<A,B>; return std::max(C(a),C(b)); }
inline double normangle(double angle)
{ double a=std::fmod(angle,PI2); return a>=PI?a-PI2:(a < -PI?a+PI2:a); }
#endif

#ifdef MERCURY_NATIVE_ORBITER
inline void oapiWriteLogV(const char* format,...)
{
    char line[4096];
    va_list args;
    va_start(args,format);
    std::vsnprintf(line,sizeof(line),format,args);
    va_end(args);
    oapiWriteLog(line);
}
inline bool oapiIsVessel(OBJHANDLE vessel)
{
    for (oapi::UInt32 i=0;i<oapiGetVesselCount();++i)
        if (oapiGetVesselByIndex(i)==vessel) return true;
    return false;
}
inline OBJHANDLE oapiGetBaseByName(OBJHANDLE planet,const char* name)
{
    for (oapi::UInt32 i=0;i<oapiGetBaseCount(planet);++i) {
        auto base=oapiGetBaseByIndex(planet,i);
        char candidate[256]{};
        oapiGetObjectName(base,candidate,sizeof(candidate)-1);
        if (!_stricmp(candidate,name)) return base;
    }
    return nullptr;
}
void oapiGetBaseEquPos(OBJHANDLE base,double* longitude,double* latitude,double* radius=nullptr);
#endif
inline unsigned MercuryAddMesh(VESSEL& vessel,MESHHANDLE mesh,const VECTOR3& offset)
{ return vessel.AddMesh(mesh,&offset); }
