#pragma once

#ifndef MERCURY_NATIVE_ORBITER
int FRAME_HORIZON = 0;
#endif

void ProjectMercury::VersionDependentTouchdown(VECTOR3 touch1, VECTOR3 touch2, VECTOR3 touch3, VECTOR3 touch4, double stiff, double damp, double mu)
{
#ifdef MERCURY_NATIVE_ORBITER
    const TOUCHDOWNVTX points[] = {
        {touch1, stiff, damp, mu, mu}, {touch2, stiff, damp, mu, mu},
        {touch3, stiff, damp, mu, mu}, {touch4, stiff, damp, mu, mu}
    };
    SetTouchdownPoints(points, 4);
#else
    SetTouchdownPoints(touch1, touch2, touch3);
#endif
}

inline void ProjectMercury::VersionDependentPanelClick(int id, const RECT& pos, int texidx, int draw_event, int mouse_event, PANELHANDLE hPanel, const RECT& texpos, int bkmode)
{
	oapiRegisterPanelArea(id, pos, texidx, draw_event, mouse_event);
}

void ProjectMercury::VersionDependentPadHUD(oapi::Sketchpad* skp, double simt, int* yIndexUpdate, char* cbuf, VESSEL* v)
{
	// Empty, not supported
}

inline double ProjectMercury::normangle(double angle)
{
	double a = fmod(angle, PI2);
	return (a >= PI ? a - PI2 : a < -PI ? a + PI2 : a);
}

inline void ProjectMercury::oapiWriteLogV(const char* format, ...)
{
	char string[256];
	va_list va; // variable list
    va_start (va, format);
    vsprintf (string, format, va);
    va_end (va);
	
	oapiWriteLog(string);
}

inline double ProjectMercury::GetGroundspeed(void)
{
	return GetAirspeed();
}

inline double ProjectMercury::GetAnimation(UINT anim)
{
	return -1.0;
}

inline void ProjectMercury::GetGroundspeedVector(int frame, VECTOR3& v)
{
	#ifdef MERCURY_NATIVE_ORBITER
	oapiGetAirspeedVector(GetHandle(), static_cast<REFFRAME>(frame), &v);
#else
	oapiGetAirspeedVector(GetHandle(), &v);
#endif
}

inline double ProjectMercury::length2(VECTOR3 vec)
{
	return length(vec) * length(vec);
}

inline void ProjectMercury::GetAirspeedVector(int frame, VECTOR3& v)
{
	#ifdef MERCURY_NATIVE_ORBITER
	oapiGetAirspeedVector(GetHandle(), static_cast<REFFRAME>(frame), &v);
#else
	oapiGetAirspeedVector(GetHandle(), &v);
#endif
}



