def test_server_module_imports() -> None:
    from petromcp.server import app, build_app

    assert app is not None
    custom = build_app(allowed_paths=[])
    assert custom is not None
