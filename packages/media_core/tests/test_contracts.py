def test_media_core_contracts_import():
    from media_core import LayoutEngine, RenderAdapter, TTSAdapter
    assert LayoutEngine and RenderAdapter and TTSAdapter

