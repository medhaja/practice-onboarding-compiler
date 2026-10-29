import pytest

from onboarding.compiler import compile_packet, load_packet


@pytest.fixture
def clean():
    """The clean practice's packet and a fresh copy of its compiled config."""
    packet = load_packet("p06")
    return packet, compile_packet(packet)
