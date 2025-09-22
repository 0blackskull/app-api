from __future__ import annotations
from typing import Optional, Any, List
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut, GeocoderUnavailable
from app.agents.tools import get_panchanga, compatibility_ashtakoota
from app import crud
import json

_geolocator = Nominatim(user_agent="ask-stellar")


def _get_lat_lon(city_name: str) -> tuple[Optional[float], Optional[float]]:
    if not city_name:
        return None, None
    try:
        location = _geolocator.geocode(city_name, timeout=30)
        if location:
            return location.latitude, location.longitude
    except (GeocoderTimedOut, GeocoderUnavailable):
        pass
    return None, None


def compute_ashtakoota_raw(user: User, counterpart: Any, compatibility_type: Optional[str]) -> Optional[dict]:
    """
    Compute raw Ashtakoota dict for user vs counterpart (User or Partner) based on compatibility_type.
    Returns None if insufficient data.
    """
    if compatibility_type not in {"love", "friendship"}:
        return None

    # Validate birth details
    if not user.city_of_birth or not user.time_of_birth:
        return None
    if not getattr(counterpart, 'city_of_birth', None) or not getattr(counterpart, 'time_of_birth', None):
        return None

    p_lat, p_lon = _get_lat_lon(user.city_of_birth)
    o_lat, o_lon = _get_lat_lon(getattr(counterpart, 'city_of_birth'))
    if not all([p_lat, p_lon, o_lat, o_lon]):
        return None

    user_details = get_panchanga(
        birth_date=user.time_of_birth.strftime('%Y-%m-%d'),
        birth_time=user.time_of_birth.strftime('%H:%M'),
        timezone='Asia/Kolkata',
        longitude=p_lon,
        latitude=p_lat,
    )
    other_details = get_panchanga(
        birth_date=getattr(counterpart, 'time_of_birth').strftime('%Y-%m-%d'),
        birth_time=getattr(counterpart, 'time_of_birth').strftime('%H:%M'),
        timezone='Asia/Kolkata',
        longitude=o_lon,
        latitude=o_lat,
    )

    user_gender = getattr(user, 'gender', None)
    other_gender = getattr(counterpart, 'gender', None)

    def run_ak(boy_rashi, boy_nak, boy_pada, girl_rashi, girl_nak, girl_pada):
        return compatibility_ashtakoota(
            boy_rashi=boy_rashi,
            boy_nakshatra=boy_nak,
            boy_pada=boy_pada,
            girl_rashi=girl_rashi,
            girl_nakshatra=girl_nak,
            girl_pada=girl_pada,
        )

    hetero_love = (
        compatibility_type == 'love'
        and user_gender in {'male', 'female'}
        and other_gender in {'male', 'female'}
        and user_gender != other_gender
    )

    if hetero_love:
        if user_gender == 'male':
            ak = run_ak(
                user_details['moon_rashi'], user_details['nakshatra'], user_details['pada'],
                other_details['moon_rashi'], other_details['nakshatra'], other_details['pada']
            )
        else:
            ak = run_ak(
                other_details['moon_rashi'], other_details['nakshatra'], other_details['pada'],
                user_details['moon_rashi'], user_details['nakshatra'], user_details['pada']
            )
    else:
        a_first = run_ak(
            user_details['moon_rashi'], user_details['nakshatra'], user_details['pada'],
            other_details['moon_rashi'], other_details['nakshatra'], other_details['pada']
        )
        a_swap = run_ak(
            other_details['moon_rashi'], other_details['nakshatra'], other_details['pada'],
            user_details['moon_rashi'], user_details['nakshatra'], user_details['pada']
        )
        ak = a_first if a_first.get('total', 0) >= a_swap.get('total', 0) else a_swap

    if compatibility_type == 'friendship' and isinstance(ak, dict) and 'scores' in ak:
        try:
            scores = ak.get('scores', {})
            yoni_score = float(scores.get('Yoni', 0) or 0)
            bhakoot_score = float(scores.get('Bhakoot', 0) or 0)
            scores['Bhakoot'] = min(7.0, bhakoot_score + yoni_score)
            scores['Yoni'] = 0
            if 'explanation' in ak:
                ak['explanation']['Yoni'] = 'Not applicable for friendship. Yoni folded under emotional closeness.'
                ak['explanation']['Bhakoot'] = 'Bhakoot (Emotional): Includes Yoni-derived closeness for friendship.'
                ak['explanation']['Vashya'] = 'Vashya (Mutual Influence): Based on Rashi mutual influence for friendship compatibility.'
            ak['total'] = sum(float(v or 0) for v in scores.values())
        except Exception:
            pass
    return ak


def compute_ashtakoota_raw_json_for_context(
    db,
    current_user_id: str,
    participant_user_ids: List[str] | None,
    participant_partner_ids: List[str] | None,
    compatibility_type: Optional[str],
) -> Optional[str]:
    """Resolve final context and return JSON string cache or None (no computation)."""
    if compatibility_type not in {"love", "friendship"}:
        return None
    uids = participant_user_ids or []
    pids = participant_partner_ids or []
    if len(uids) + len(pids) != 1:
        return None

    main_user = crud.get_user(db, current_user_id)
    if not main_user:
        return None

    counterpart = None
    if uids:
        other_uid = str(uids[0])
        if other_uid != current_user_id:
            counterpart = crud.get_user(db, other_uid)
    elif pids:
        counterpart = crud.get_partner(db, pids[0])

    if not counterpart:
        return None

    ak = compute_ashtakoota_raw(main_user, counterpart, compatibility_type)
    return json.dumps(ak) if ak is not None else None 