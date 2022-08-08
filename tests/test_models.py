from echo_agent.models import ConnectionInfo


def test_connection_info_default_list():
    info = ConnectionInfo("conn_id", "did", "verkey", "their_vk", "endpoint")
    assert isinstance(info.routing_keys, list)
    assert not info.routing_keys
    info.routing_keys.append("test")
    assert info.routing_keys

    info = ConnectionInfo("conn_id", "did", "verkey", "their_vk", "endpoint")
    assert not info.routing_keys
