def test_package_importable() -> None:
    import petromcp

    assert petromcp.__version__
