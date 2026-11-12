def test_tantra_adapters_import():
    import tantra_adapters

    assert tantra_adapters.__version__ == "0.1.0"
    assert len(tantra_adapters.BROKER_ADAPTERS) == 7
