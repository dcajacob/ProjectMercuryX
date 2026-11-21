"""Elapsed time of the pilot's retrosequence command, in seconds after liftoff.

Nominal times follow NASA SP-4012 vol. II, tables 2-33 through 2-35.
Mercury's normal 30-second sequence delay precedes the first motor firing.
"""

RETROSEQUENCE_MET = {
    'aurora7': 4 * 3600 + 32 * 60 + 36.5,
    'sigma7': 8 * 3600 + 51 * 60 + 30,
    'faith7': 33 * 3600 + 58 * 60 + 59,
}

PRE_RETRO_SECONDS = 300
