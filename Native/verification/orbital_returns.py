"""Mission references for the linked Mercury insertion and recovery replays."""
from dataclasses import dataclass
import re


@dataclass(frozen=True)
class Mission:
    ship: str
    historical_sequence_met: float
    perigee_km: float
    apogee_km: float
    period_s: int


# NASA SP-4012 vol. II, tables 2-33 through 2-35. Recovery limits are
# regression tolerances against the original scenario's coordinates.
MISSIONS = {
    'aurora7': Mission('MA-7', 4*3600 + 32*60 + 36.5, 160.84, 268.55, 5312),
    'sigma7': Mission('MA-8', 8*3600 + 51*60 + 30, 161.0, 283.04, 5335),
    'faith7': Mission('MA-9', 33*3600 + 58*60 + 59, 161.42, 266.99, 5325),
}
CHECKPOINT_MET = {name: int(m.historical_sequence_met) - 30 for name, m in MISSIONS.items()}
FLIGHT_HZ = 60
RECOVERY_LIMIT_KM = 50


def sequence_met(mission, coast):
    reference = MISSIONS[mission]
    met = CHECKPOINT_MET[mission]
    log = (coast/'console.log').read_text(errors='replace')
    clocks = re.findall(rf'^Mercury recovery clock {reference.ship} MET {met} sequence (\d+):(\d+):(\d+)$', log, re.M)
    if not clocks:
        raise ValueError(f'{coast}: missing {reference.ship} panel recommendation at MET {met}')
    hours, minutes, seconds = map(int, clocks[-1])
    command = hours * 3600 + minutes * 60 + seconds
    if minutes >= 60 or seconds >= 60 or command <= met or abs(command - reference.historical_sequence_met) > 60:
        raise ValueError(f'{coast}: no upcoming solution on the historical pass at MET {met}: {clocks[-1]}')
    return command
