def test_vyapaar_adapters_import():
    import vyapaar_adapters

    assert vyapaar_adapters.__version__ == "0.1.0"
    assert len(vyapaar_adapters.BROKER_ADAPTERS) == 7
