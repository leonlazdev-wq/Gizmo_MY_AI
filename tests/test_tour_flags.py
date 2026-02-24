from modules.feature_flags import get_flags, set_flag
from modules.tour import get_tour_state, mark_tour_completed


def test_tour_state_roundtrip():
    session_id = 'tour_s1'
    assert get_tour_state(session_id) is False
    mark_tour_completed(session_id)
    assert get_tour_state(session_id) is True


def test_feature_flag_roundtrip():
    session_id = 'flags_s1'
    set_flag(session_id, 'canary_auto_agent', True)
    flags = get_flags(session_id)
    assert flags.get('canary_auto_agent') is True
